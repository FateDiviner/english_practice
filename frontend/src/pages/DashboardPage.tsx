import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Message,
  Progress,
  Radio,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
} from "@arco-design/web-react";
import { IconHistory, IconPlayArrow, IconRefresh } from "@arco-design/web-react/icon";
import type { ReviewQueue, StatsOverview, WordBook, WordBookProgress } from "@/types";
import { activateWordbook, fetchProgress, fetchWordbooks } from "@/api/wordbooks";
import { fetchReviewQueue } from "@/api/practice";
import { fetchOverview } from "@/api/stats";
import LearningBoard from "@/components/LearningBoard";
import { useAuthStore } from "@/stores/auth";
import { useAppStore } from "@/stores/app";
import { usePracticeStore, type PracticeMode } from "@/stores/practice";
import { toMessage } from "@/api/client";

/** 控制台 / 词书中心：选择激活词书并开始默写 */
export default function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const groupSize = useAppStore((state) => state.groupSize);
  const setGroupSize = useAppStore((state) => state.setGroupSize);
  const startPractice = usePracticeStore((state) => state.start);

  const [books, setBooks] = useState<WordBook[]>([]);
  const [progressMap, setProgressMap] = useState<Record<number, WordBookProgress>>({});
  const [activeId, setActiveId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [review, setReview] = useState<ReviewQueue | null>(null);
  const [stats, setStats] = useState<StatsOverview | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await fetchWordbooks();
      setBooks(list);
      const preferred = user?.active_wordbook_id ?? list[0]?.id ?? null;
      setActiveId(preferred);

      const entries = await Promise.all(
        list.map(async (book) => [book.id, await fetchProgress(book.id)] as const)
      );
      setProgressMap(Object.fromEntries(entries));
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, [user?.active_wordbook_id]);

  useEffect(() => {
    void load();
  }, [load]);

  // 学习看板为跨词书全局统计，只需在进入页面时拉取一次
  useEffect(() => {
    let cancelled = false;
    void fetchOverview()
      .then((overview) => {
        if (!cancelled) setStats(overview);
      })
      .catch((error: unknown) => {
        if (!cancelled) Message.error({ content: toMessage(error) });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // 今日待复习队列按激活词书统计，切换词书后重新拉取
  useEffect(() => {
    if (!activeId) {
      setReview(null);
      return;
    }
    let cancelled = false;
    void fetchReviewQueue(activeId)
      .then((queue) => {
        if (!cancelled) setReview(queue);
      })
      .catch((error: unknown) => {
        if (!cancelled) Message.error({ content: toMessage(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  const handleActivate = async (book: WordBook) => {
    setActiveId(book.id);
    try {
      await activateWordbook(book.id);
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const handleStart = async (mode: PracticeMode = "normal") => {
    if (!activeId) return;
    setStarting(true);
    try {
      await startPractice(activeId, mode);
      navigate("/practice");
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setStarting(false);
    }
  };

  const activeBook = books.find((book) => book.id === activeId) ?? null;
  const activeProgress = activeId ? progressMap[activeId] : undefined;

  return (
    <div className="anim-fade-up">
      {stats && <LearningBoard overview={stats} />}

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 20,
        }}
      >
        <div>
          <Typography.Title heading={4} style={{ margin: 0 }}>
            词书中心
          </Typography.Title>
          <Typography.Text type="secondary">
            选择一本词书即可开始默写，进度会自动持久化保存
          </Typography.Text>
        </div>

        <Space size={12} wrap>
          <Space size={6}>
            <Typography.Text type="secondary">每组词数</Typography.Text>
            <Select
              value={groupSize}
              onChange={setGroupSize}
              size="small"
              style={{ width: 96 }}
              className="focus-ring"
              options={[5, 10, 20, 30, 50].map((size) => ({
                label: `${size} 词`,
                value: size,
              }))}
            />
          </Space>
          <Button
            className="focus-ring"
            icon={<IconRefresh />}
            onClick={() => void load()}
            loading={loading}
          >
            刷新
          </Button>
        </Space>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: 16,
        }}
      >
        {books.map((book) => {
          const progress = progressMap[book.id];
          const isActive = book.id === activeId;
          const done = progress
            ? progress.mastered + progress.learning + progress.wrong
            : 0;
          const percent = progress && progress.total_words
            ? Math.round((done / progress.total_words) * 100)
            : 0;

          return (
            <Card
              key={book.id}
              className="card"
              hoverable
              style={{
                borderColor: isActive ? "var(--color-primary)" : undefined,
                borderWidth: isActive ? 2 : 1,
              }}
              onClick={() => void handleActivate(book)}
            >
              <Space
                size={8}
                style={{ width: "100%", justifyContent: "space-between" }}
                align="center"
              >
                <Tag color={isActive ? "arcoblue" : "gray"} size="small">
                  {isActive ? "激活中" : book.difficulty}
                </Tag>
                {isActive && <Tag color="green" size="small">当前</Tag>}
              </Space>

              <Typography.Title heading={6} style={{ margin: "10px 0 6px" }}>
                {book.title}
              </Typography.Title>
              <Typography.Text
                type="secondary"
                style={{ display: "block", minHeight: 44, fontSize: 13 }}
              >
                {book.description}
              </Typography.Text>

              <div style={{ margin: "12px 0 4px" }}>
                <Space size={8} style={{ width: "100%", justifyContent: "space-between" }}>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    共 {book.total_words} 词
                  </Typography.Text>
                  <Typography.Text style={{ fontSize: 12 }}>
                    {percent}%
                  </Typography.Text>
                </Space>
                <Progress
                  percent={percent}
                  showText={false}
                  size="small"
                  style={{ marginTop: 4 }}
                />
              </div>

              {progress && (
                <Space size={6} wrap style={{ marginTop: 6 }}>
                  <Tag color="green" size="small">已掌握 {progress.mastered}</Tag>
                  <Tag color="arcoblue" size="small">学习中 {progress.learning}</Tag>
                  <Tag color="red" size="small">错题 {progress.wrong}</Tag>
                  <Tag size="small">未学习 {progress.untouched}</Tag>
                </Space>
              )}
            </Card>
          );
        })}

        {loading && books.length === 0 && (
          <Typography.Text type="secondary">正在加载词书…</Typography.Text>
        )}
      </div>

      {activeBook && (
        <Card
          className="card"
          style={{ marginTop: 24 }}
          title={
            <Space>
              <span>开始练习</span>
              <Typography.Text type="secondary" style={{ fontWeight: 400 }}>
                {activeBook.title}
              </Typography.Text>
            </Space>
          }
        >
          <Space size={12} wrap>
            <Tooltip content="按释义与音标盲打拼写，答对自动切词">
              <Button
                type="primary"
                size="large"
                loading={starting}
                className="focus-ring"
                icon={<IconPlayArrow />}
                onClick={() => void handleStart("normal")}
              >
                开始默写（{groupSize} 词）
              </Button>
            </Tooltip>

            <Button
              size="large"
              className="focus-ring"
              loading={starting}
              disabled={!activeProgress || activeProgress.wrong === 0}
              onClick={() => void handleStart("wrong_book")}
            >
              错题专项重练
              {activeProgress ? `（${activeProgress.wrong}）` : ""}
            </Button>

            <Tooltip
              content={
                review && review.total > 0
                  ? `已过期 ${review.overdue} · 今日到期 ${review.due_today}`
                  : "暂无到期词，系统会按遗忘曲线自动安排"
              }
            >
              <Button
                size="large"
                className="focus-ring"
                icon={<IconHistory />}
                loading={starting}
                disabled={starting || !review || review.total === 0}
                onClick={() => void handleStart("review")}
              >
                {review && review.total > 0
                  ? `今日复习（${review.total}）`
                  : "今日复习"}
              </Button>
            </Tooltip>

            <Radio.Group
              type="button"
              size="small"
              value={groupSize}
              onChange={(value) => setGroupSize(value as number)}
            >
              {[5, 10, 20, 30].map((size) => (
                <Radio key={size} value={size}>
                  {size} 词
                </Radio>
              ))}
            </Radio.Group>
          </Space>

          {activeProgress && (
            <Typography.Text
              type="secondary"
              style={{ display: "block", marginTop: 12, fontSize: 13 }}
            >
              本词书正确率 {activeProgress.accuracy}% · 已掌握 {activeProgress.mastered} /{" "}
              {activeProgress.total_words}
            </Typography.Text>
          )}

          {review && review.total > 0 && (
            <Typography.Text
              type="secondary"
              style={{ display: "block", marginTop: 4, fontSize: 13 }}
            >
              今日待复习 {review.total}（已过期 {review.overdue} · 今日到期{" "}
              {review.due_today}）
              {review.upcoming_7d > 0
                ? `，未来 7 天还有 ${review.upcoming_7d} 个词到期`
                : ""}
            </Typography.Text>
          )}
        </Card>
      )}
    </div>
  );
}
