import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Message,
  Progress,
  Space,
  Tag,
  Tooltip,
  Typography,
} from "@arco-design/web-react";
import {
  IconBulb,
  IconCheck,
  IconClose,
  IconRight,
  IconSound,
  IconSkipNext,
  IconRefresh,
} from "@arco-design/web-react/icon";
import type { DiffCell } from "@/types";
import { usePracticeStore } from "@/stores/practice";
import { usePracticeHotkeys } from "@/hooks/usePracticeHotkeys";
import { useSpeech } from "@/hooks/useSpeech";
import { writeChatContext } from "@/utils/chatContext";

/** 答对后自动切词的等待时长（AGENTS.md 规范：600~800ms） */
const AUTO_ADVANCE_MS = 700;

/** 三种练习模式的标签与配色，页面上必须一眼可辨 */
const MODE_LABEL: Record<string, string> = {
  normal: "[默写练习]",
  wrong_book: "[错题重练]",
  review: "[今日复习]",
};

const MODE_COLOR: Record<string, string> = {
  normal: "arcoblue",
  wrong_book: "red",
  review: "green",
};

/**
 * 逐字符比对结果渲染。
 *
 * 后端返回的是单条交错序列（错误字符与漏写字符交替），
 * 直接铺开会读成 "zazbzaznzdon" 这种无从辨认的串。
 * 这里按状态拆成两行，分别还原"你输入了什么"与"正确拼写是什么"：
 *   - typed  取 same / wrong / extra  -> 精确还原用户输入
 *   - answer 取 same / missing        -> 精确还原标准答案
 */
function DiffText({ cells }: { cells: DiffCell[] }) {
  const typed = cells.filter(
    (cell) => cell.status === "same" || cell.status === "wrong" || cell.status === "extra"
  );
  const answer = cells.filter(
    (cell) => cell.status === "same" || cell.status === "missing"
  );

  const row = (label: string, items: DiffCell[], rowKey: string) => (
    <div
      key={rowKey}
      style={{ display: "flex", gap: 12, alignItems: "baseline", flexWrap: "wrap" }}
    >
      <span
        style={{
          fontSize: 13,
          color: "var(--text-3)",
          minWidth: 60,
          flexShrink: 0,
        }}
      >
        {label}
      </span>
      <span
        className="phonetic-display"
        style={{
          fontSize: 21,
          letterSpacing: "0.06em",
          wordBreak: "break-all",
        }}
      >
        {items.map((cell, index) => (
          <span key={`${cell.status}-${index}`} className={`diff-${cell.status}`}>
            {cell.char}
          </span>
        ))}
      </span>
    </div>
  );

  return (
    <div style={{ display: "grid", gap: 8 }}>
      {row("你的输入", typed, "typed")}
      {row("正确拼写", answer, "answer")}
    </div>
  );
}

/** 单词音标默写练习：全键盘零阻塞核心场景 */
export default function PracticePage() {
  const navigate = useNavigate();
  const {
    session,
    index,
    phase,
    result,
    hint,
    error,
    settlement,
    submit,
    revealHint,
    advance,
    reset,
  } = usePracticeStore();
  const { speak, supported } = useSpeech();

  const [value, setValue] = useState("");
  const [shake, setShake] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clue = session?.clues[index] ?? null;
  const total = session?.total ?? 0;
  const running = Boolean(session) && phase !== "finished" && phase !== "idle";

  /* ---------------- 自动聚焦：页面加载与切词后输入框必须自动聚焦 ---------------- */
  const focusInput = useCallback(() => {
    // 等待 React 提交 DOM 后再聚焦，避免竞态导致焦点丢失
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  useEffect(() => {
    if (running) focusInput();
  }, [running, index, phase, focusInput]);

  /* ---------------- 答对：播放发音并延迟自动平滑切词 ---------------- */
  useEffect(() => {
    if (phase !== "correct" || !clue) return;

    if (supported) void speak(result?.answer ?? "");
    timerRef.current = setTimeout(() => {
      void advance();
    }, AUTO_ADVANCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [phase, clue, result, advance, speak, supported]);

  /* ---------------- 答错：触发轻量抖动动效 ---------------- */
  useEffect(() => {
    if (phase !== "wrong") return;
    setShake(true);
    const id = setTimeout(() => setShake(false), 320);
    return () => clearTimeout(id);
  }, [phase, index]);

  /* ---------------- 答错时把上下文交给伴学页 ---------------- */
  useEffect(() => {
    if (phase !== "wrong" || !result || !clue) return;
    writeChatContext({
      word: result.answer,
      translation: clue.translation,
      phonetic: clue.phonetic,
      typed: result.submitted,
      source: "practice",
    });
  }, [phase, result, clue]);

  /* ---------------- 新词切换时清空输入 ---------------- */
  useEffect(() => {
    setValue("");
  }, [index]);

  /* ---------------- 退出练习时清理 ---------------- */
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleSpeak = useCallback(() => {
    if (!clue) return;
    if (!supported) {
      Message.info({ content: "当前浏览器不支持语音合成" });
      return;
    }
    // 发音内容始终为标准拼写：未作答时朗读线索词，答错后朗读正确答案
    void speak(clue.speak);
  }, [clue, speak, supported]);

  const handleSubmit = useCallback(() => {
    if (!session || !clue) return;
    if (phase === "submitting" || phase === "starting") return;

    if (phase === "correct") {
      // 答对等待期按回车可立即切词，避免键盘流被计时器卡住
      if (timerRef.current) clearTimeout(timerRef.current);
      void advance();
      return;
    }

    if (phase === "wrong") {
      const typed = value.trim();
      if (typed && typed !== result?.submitted) {
        void submit(typed, false);
      } else {
        void advance();
      }
      return;
    }

    if (phase === "running") {
      if (!value.trim()) {
        Message.warning({ content: "请先输入拼写，或按 Esc 跳过" });
        focusInput();
        return;
      }
      void submit(value, false);
    }
  }, [session, clue, phase, value, result, submit, advance, focusInput]);

  const handleSkip = useCallback(() => {
    if (!session || phase === "submitting" || phase === "correct") return;
    // 已处于错误反馈态：答案已展示、错题已落库，此时跳过应直接切下一词。
    // 否则再次提交只会把状态又打回 wrong，用户会卡在原地无法推进。
    if (phase === "wrong") {
      void advance();
      return;
    }
    void submit(value, true);
  }, [session, phase, submit, value, advance]);

  const handleHint = useCallback(() => {
    if (!session) return;
    void revealHint();
    focusInput();
  }, [session, revealHint, focusInput]);

  usePracticeHotkeys(
    {
      onSubmit: handleSubmit,
      onSpeak: handleSpeak,
      onHint: handleHint,
      onSkip: handleSkip,
    },
    running && phase !== "submitting"
  );

  /* ---------------- 空态：直接访问 /practice 而未开局 ---------------- */
  if (!session) {
    return (
      <Card className="card" style={{ maxWidth: 520, margin: "48px auto" }}>
        <Typography.Title heading={5}>还没有进行中的练习</Typography.Title>
        <Typography.Text type="secondary">
          请先到词书中心选择一本词书，再开始默写。
        </Typography.Text>
        <div style={{ marginTop: 16 }}>
          <Button type="primary" className="focus-ring" onClick={() => navigate("/")}>
            前往词书中心
          </Button>
        </div>
      </Card>
    );
  }

  /* ---------------- 结算视图 ---------------- */
  if (phase === "finished" && settlement) {
    const minutes = Math.floor(settlement.duration_ms / 60000);
    const seconds = Math.round((settlement.duration_ms % 60000) / 1000);
    const wrongItems = settlement.items.filter((item) => !item.correct);

    return (
      <div className="anim-fade-up" style={{ maxWidth: 720, margin: "0 auto" }}>
        <Card className="card">
          <Space
            size={16}
            style={{ width: "100%", justifyContent: "space-between" }}
            align="center"
          >
            <Typography.Title heading={5} style={{ margin: 0 }}>
              本组练习结算
            </Typography.Title>
            <Tag color={settlement.accuracy >= 80 ? "green" : "orange"} size="small">
              {settlement.accuracy >= 80 ? "[完成]" : "[待巩固]"}
            </Tag>
          </Space>

          <div style={{ margin: "18px 0 6px" }}>
            <Progress
              percent={settlement.accuracy}
              size="default"
              color={settlement.accuracy >= 80 ? "green" : "orange"}
            />
          </div>

          <Space size={24} wrap style={{ margin: "12px 0 4px" }}>
            <Typography.Text>
              正确率 <b>{settlement.accuracy}%</b>
            </Typography.Text>
            <Typography.Text>
              正确 <b style={{ color: "var(--color-success)" }}>{settlement.correct_count}</b>
            </Typography.Text>
            <Typography.Text>
              错误 <b style={{ color: "var(--color-danger)" }}>{settlement.wrong_count}</b>
            </Typography.Text>
            <Typography.Text type="secondary">
              耗时 {minutes} 分 {seconds} 秒
            </Typography.Text>
          </Space>

          {wrongItems.length > 0 && (
            <>
              <Typography.Title heading={6} style={{ margin: "20px 0 10px" }}>
                错词复盘（已自动沉淀至错题本）
              </Typography.Title>
              <div style={{ display: "grid", gap: 8 }}>
                {wrongItems.map((item) => (
                  <div
                    key={item.word_id}
                    style={{
                      padding: "10px 12px",
                      borderRadius: "var(--border-radius-md)",
                      background: "var(--color-danger-soft)",
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 10,
                      alignItems: "baseline",
                    }}
                  >
                    <span className="word-display" style={{ fontSize: 20 }}>
                      {item.word}
                    </span>
                    <span className="phonetic-display">{item.phonetic}</span>
                    <Typography.Text type="secondary">{item.translation}</Typography.Text>
                    {item.skipped ? (
                      <Tag size="small" color="gray">[已跳过]</Tag>
                    ) : (
                      <Typography.Text type="error" style={{ fontSize: 13 }}>
                        你的输入：{item.submitted || "（空）"}
                      </Typography.Text>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          <Space size={12} style={{ marginTop: 24 }} wrap>
            <Button
              type="primary"
              className="focus-ring"
              onClick={() => navigate("/")}
            >
              返回词书中心
            </Button>
            {wrongItems.length > 0 && (
              <Button
                className="focus-ring"
                icon={<IconBulb />}
                onClick={() => navigate("/wrong-book")}
              >
                错题专项重练
              </Button>
            )}
            <Button
              className="focus-ring"
              icon={<IconRefresh />}
              onClick={() => {
                reset();
                navigate("/");
              }}
            >
              再来一组
            </Button>
          </Space>
        </Card>
      </div>
    );
  }

  if (!clue) return null;

  const progressPercent = Math.round(((phase === "correct" ? index + 1 : index) / total) * 100);

  /* ---------------- 主练习视图 ---------------- */
  return (
    <div className="anim-fade-up" style={{ maxWidth: 680, margin: "0 auto" }}>
      <Space
        size={12}
        style={{ width: "100%", justifyContent: "space-between", marginBottom: 12 }}
      >
        <Space size={8}>
          <Tag size="small" color={MODE_COLOR[session.mode] ?? "arcoblue"}>
            {MODE_LABEL[session.mode] ?? "[默写练习]"}
          </Tag>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {index + 1} / {total}
          </Typography.Text>
        </Space>
        <Button
          size="small"
          type="text"
          className="focus-ring"
          icon={<IconSkipNext />}
          onClick={() => navigate("/")}
        >
          退出练习
        </Button>
      </Space>

      <Progress percent={progressPercent} showText={false} size="small" />

      <Card className="card" style={{ marginTop: 16, padding: "28px 24px" }}>
        {/* 核心线索：释义 + 词性 + 音标 */}
        <div style={{ textAlign: "center" }}>
          <Typography.Title
            heading={3}
            style={{ margin: "0 0 10px", fontSize: 26, lineHeight: 1.4 }}
          >
            {clue.translation}
          </Typography.Title>

          <Space size={12} align="center" wrap style={{ justifyContent: "center" }}>
            {clue.pos && (
              <Tag size="small" color="gray" style={{ fontFamily: "var(--font-ipa)" }}>
                {clue.pos}
              </Tag>
            )}
            <span className="phonetic-display">{clue.phonetic}</span>
            <Tooltip content={`播放发音（Space / Ctrl+P）`}>
              <Button
                size="small"
                type="text"
                shape="circle"
                className="focus-ring"
                aria-label="播放发音"
                icon={<IconSound />}
                onClick={handleSpeak}
              />
            </Tooltip>
          </Space>
        </div>

        {/* 拼写输入框：自动聚焦，纯键盘盲打 */}
        <div style={{ marginTop: 26 }}>
          <input
            ref={inputRef}
            className={`focus-ring ${shake ? "anim-shake" : ""} ${
              phase === "correct" ? "anim-flash" : ""
            }`}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="输入英文拼写后按 Enter 提交"
            spellCheck={false}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            aria-label="单词拼写输入框"
            disabled={phase === "submitting"}
            style={{
              width: "100%",
              fontSize: 24,
              padding: "14px 16px",
              letterSpacing: "0.06em",
              textAlign: "center",
              color: "var(--text-1)",
              background: "var(--bg-subtle)",
              border: `2px solid ${
                phase === "correct"
                  ? "var(--color-success)"
                  : phase === "wrong"
                    ? "var(--color-danger)"
                    : "var(--border-color)"
              }`,
              borderRadius: "var(--border-radius-md)",
              outline: "none",
              transition: "border-color var(--duration-fast) ease",
              caretColor: "var(--color-primary)",
            }}
          />
        </div>

        {/* 首字母提示 */}
        {hint && (
          <div
            className="anim-fade-up"
            style={{ textAlign: "center", marginTop: 14 }}
            aria-live="polite"
          >
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              提示：
            </Typography.Text>
            <span
              className="word-display"
              style={{ fontSize: 24, marginLeft: 6, letterSpacing: "0.12em" }}
            >
              {hint.masked}
            </span>
          </div>
        )}

        {/* 校验反馈 */}
        <div style={{ marginTop: 18, minHeight: 92 }} aria-live="polite">
          {phase === "correct" && result && (
            <div
              className="anim-fade-up"
              style={{
                textAlign: "center",
                padding: "12px",
                borderRadius: "var(--border-radius-md)",
                background: "var(--color-success-soft)",
              }}
            >
              <Typography.Text style={{ color: "var(--color-success)" }}>
                <IconCheck style={{ marginRight: 6 }} />
                {result.message}
              </Typography.Text>
            </div>
          )}

          {(phase === "wrong" || (phase === "running" && result && !result.correct)) && (
            <div
              className="anim-fade-up"
              style={{
                padding: "14px",
                borderRadius: "var(--border-radius-md)",
                background: "var(--color-danger-soft)",
              }}
            >
              <Space size={8} align="center" style={{ marginBottom: 8 }}>
                <IconClose style={{ color: "var(--color-danger)" }} />
                <Typography.Text style={{ color: "var(--color-danger)" }}>
                  {result?.message ?? "[拼写错误]"}
                </Typography.Text>
              </Space>

              {result && result.diff.length > 0 && <DiffText cells={result.diff} />}


              <Typography.Text type="secondary" style={{ display: "block", fontSize: 13, marginTop: 6 }}>
                可原地订正后按 Enter 再次校验，或直接按 Enter 进入下一词。
              </Typography.Text>
            </div>
          )}
        </div>

        {error && (
          <Typography.Text type="error" style={{ display: "block", marginTop: 8, fontSize: 13 }}>
            {error}
          </Typography.Text>
        )}
      </Card>

      {/* 键盘操作提示条 */}
      <div
        style={{
          marginTop: 14,
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          justifyContent: "center",
        }}
      >
        {[
          ["Enter", "提交"],
          ["Space / Ctrl+P", "重播发音"],
          ["Tab", "显示提示"],
          ["Esc / Ctrl+Enter", "跳过并看答案"],
        ].map(([key, label]) => (
          <Tag key={key} size="small" style={{ fontFamily: "monospace" }}>
            {key} · {label}
          </Tag>
        ))}
      </div>

      <Space
        size={12}
        style={{ marginTop: 16, width: "100%", justifyContent: "center" }}
        wrap
      >
        <Button className="focus-ring" icon={<IconBulb />} onClick={handleHint}>
          提示
        </Button>
        <Button className="focus-ring" icon={<IconSound />} onClick={handleSpeak}>
          发音
        </Button>
        <Button className="focus-ring" icon={<IconRight />} onClick={handleSkip}>
          不会，看答案
        </Button>
      </Space>
    </div>
  );
}
