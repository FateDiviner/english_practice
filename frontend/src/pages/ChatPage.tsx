import { useCallback, useEffect, useRef, useState } from "react";
import {
  Button,
  Card,
  Empty,
  Input,
  Message,
  Modal,
  Space,
  Tag,
  Tooltip,
  Typography,
} from "@arco-design/web-react";
import {
  IconBulb,
  IconMessage,
  IconRefresh,
  IconSend,
  IconStop,
  IconDelete,
} from "@arco-design/web-react/icon";
import type { ChatMessage, ChatPreset, FeedbackBlock } from "@/types";
import { clearMessages, fetchMessages, streamChat } from "@/api/chat";
import { toMessage } from "@/api/client";

interface PresetItem {
  key: ChatPreset;
  label: string;
  hint: string;
}

const PRESETS: PresetItem[] = [
  { key: "explain_word", label: "Explain a word", hint: "深度讲解刚才默写错的词" },
  { key: "grammar_check", label: "Grammar check", hint: "分析我这个句子的语法" },
  { key: "free_chat", label: "Free conversation", hint: "关于日常兴趣的英文闲聊" },
];

/** 实时纠错卡片：对应 AGENTS.md 的 [语法指正] / [地道表达] */
function FeedbackCard({ feedback }: { feedback: FeedbackBlock }) {
  return (
    <div
      style={{
        marginTop: 8,
        padding: "10px 12px",
        borderRadius: "var(--border-radius-md)",
        background: "var(--color-primary-soft)",
        borderLeft: "3px solid var(--color-primary)",
      }}
    >
      {feedback.grammar && (
        <div style={{ marginBottom: feedback.polish.length ? 8 : 0 }}>
          <Tag size="small" color="arcoblue" style={{ marginRight: 8 }}>
            [语法指正]
          </Tag>
          <Typography.Text style={{ fontSize: 14 }}>{feedback.grammar}</Typography.Text>
        </div>
      )}
      {feedback.polish.length > 0 && (
        <div>
          <Tag size="small" color="green" style={{ marginRight: 8 }}>
            [地道表达]
          </Tag>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            {feedback.polish.map((item) => (
              <li key={item} style={{ fontSize: 14 }}>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** AI 英语对话助教：SSE 流式输出 + 实时纠错 */
export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [streamFeedback, setStreamFeedback] = useState<FeedbackBlock | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const abortRef = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  // 记住最近一次请求，供失败后一键重试
  const retryRef = useRef<{ content: string; preset: ChatPreset | null } | null>(null);
  const contextRef = useRef<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const history = await fetchMessages();
      setMessages(history);
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
    // 从默写页带过来的上下文（最近拼错的词）
    const fromStorage = sessionStorage.getItem("ep_chat_context");
    if (fromStorage) {
      contextRef.current = fromStorage;
      sessionStorage.removeItem("ep_chat_context");
    }
    return () => abortRef.current?.abort();
  }, [loadHistory]);

  // 新内容到达时自动滚到底部
  useEffect(() => {
    const node = listRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, streamText]);

  const send = useCallback(
    async (content: string, preset: ChatPreset | null) => {
      const text = content.trim();
      if (!text || streaming) return;

      retryRef.current = { content: text, preset };
      setLastError(null);
      setStreamText("");
      setStreamFeedback(null);
      setStreaming(true);
      setInput("");

      const optimistic: ChatMessage = {
        id: Date.now(),
        role: "user",
        content: text,
        feedback: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimistic]);

      const controller = new AbortController();
      abortRef.current = controller;

      await streamChat(
        { content: text, preset, context: contextRef.current, signal: controller.signal },
        {
          onDelta: (delta) => setStreamText((prev) => prev + delta),
          onDone: (payload) => {
            setMessages((prev) => [
              ...prev,
              {
                id: payload.message_id,
                role: "assistant",
                content: payload.content,
                feedback: payload.feedback,
                created_at: payload.created_at,
              },
            ]);
            setStreamText("");
            setStreamFeedback(null);
            setStreaming(false);
            contextRef.current = null;
          },
          onError: (message, retryable) => {
            setStreaming(false);
            setStreamText("");
            setLastError(message);
            if (retryable) {
              Message.warning({ content: `${message}，可点击重试`, duration: 4000 });
            } else {
              Message.error({ content: message });
            }
          },
        }
      );
    },
    [streaming]
  );

  const handleStop = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setStreamText("");
    setLastError("已中止生成");
  };

  const handleRetry = () => {
    const request = retryRef.current;
    if (!request || streaming) return;
    // 重试时移除上一条乐观用户消息，避免重复气泡
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === "user" && last.content === request.content) {
        return prev.slice(0, -1);
      }
      return prev;
    });
    void send(request.content, request.preset);
  };

  const handleClear = () => {
    Modal.confirm({
      title: "清空对话记录",
      content: "清空后历史消息将无法恢复，确定继续吗？",
      okText: "确认清空",
      cancelText: "取消",
      onOk: async () => {
        try {
          await clearMessages();
          setMessages([]);
          Message.success({ content: "对话记录已清空" });
        } catch (error) {
          Message.error({ content: toMessage(error) });
        }
      },
    });
  };

  const askPreset = (preset: ChatPreset) => {
    const label = PRESETS.find((item) => item.key === preset)?.label ?? "";
    void send(label, preset);
  };

  return (
    <div className="anim-fade-up" style={{ maxWidth: 820, margin: "0 auto" }}>
      <Space
        size={16}
        style={{ width: "100%", justifyContent: "space-between", marginBottom: 12 }}
        wrap
      >
        <div>
          <Typography.Title heading={4} style={{ margin: 0 }}>
            AI 伴学
          </Typography.Title>
          <Typography.Text type="secondary">
            地道外教人设，语法问题会在回复中附带纠错区块
          </Typography.Text>
        </div>
        <Button
          className="focus-ring"
          size="small"
          icon={<IconDelete />}
          onClick={handleClear}
          disabled={messages.length === 0}
        >
          清空记录
        </Button>
      </Space>

      {/* 快捷 Prompt 药丸 */}
      <Space size={8} wrap style={{ marginBottom: 12 }}>
        {PRESETS.map((item) => (
          <Tooltip key={item.key} content={item.hint}>
            <Tag
              className="focus-ring"
              color="arcoblue"
              style={{ cursor: "pointer", padding: "4px 12px" }}
              onClick={() => askPreset(item.key)}
            >
              {item.label}
            </Tag>
          </Tooltip>
        ))}
      </Space>

      <Card
        className="card"
        style={{ height: "min(56vh, 520px)", display: "flex", flexDirection: "column" }}
      >
        <div
          ref={listRef}
          style={{ flex: 1, overflowY: "auto", padding: "4px 4px 12px" }}
          aria-live="polite"
        >
          {loading && (
            <Empty description="正在加载对话记录" style={{ marginTop: 60 }} />
          )}

          {!loading && messages.length === 0 && !streaming && (
            <Empty
              description="还没有对话，点上方药丸或直接输入开始练习"
              style={{ marginTop: 60 }}
            />
          )}

          {messages.map((message) => (
            <div
              key={`${message.role}-${message.id}`}
              style={{
                display: "flex",
                justifyContent:
                  message.role === "user" ? "flex-end" : "flex-start",
                marginBottom: 12,
              }}
            >
              <div
                style={{
                  maxWidth: "78%",
                  padding: "10px 14px",
                  borderRadius: "var(--border-radius-md)",
                  background:
                    message.role === "user"
                      ? "var(--color-primary)"
                      : "var(--bg-subtle)",
                  color: message.role === "user" ? "#fff" : "var(--text-1)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                <div style={{ fontSize: 14, lineHeight: 1.65 }}>{message.content}</div>
                {message.feedback && message.role === "assistant" && (
                  <FeedbackCard feedback={message.feedback} />
                )}
              </div>
            </div>
          ))}

          {streaming && (
            <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 12 }}>
              <div
                style={{
                  maxWidth: "78%",
                  padding: "10px 14px",
                  borderRadius: "var(--border-radius-md)",
                  background: "var(--bg-subtle)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {streamText || (
                  <Typography.Text type="secondary" style={{ fontSize: 14 }}>
                    正在思考…
                  </Typography.Text>
                )}
                <span
                  style={{
                    display: "inline-block",
                    width: 7,
                    height: 15,
                    marginLeft: 2,
                    background: "var(--color-primary)",
                    verticalAlign: "text-bottom",
                    animation: "ep-fade-up 900ms infinite alternate",
                  }}
                />
                {streamFeedback && <FeedbackCard feedback={streamFeedback} />}
              </div>
            </div>
          )}

          {lastError && !streaming && (
            <div
              style={{
                textAlign: "center",
                padding: "8px 0",
                display: "flex",
                gap: 10,
                justifyContent: "center",
                alignItems: "center",
              }}
            >
              <Typography.Text type="error" style={{ fontSize: 13 }}>
                {lastError}
              </Typography.Text>
              <Button
                size="small"
                className="focus-ring"
                icon={<IconRefresh />}
                onClick={handleRetry}
              >
                一键重试
              </Button>
            </div>
          )}
        </div>

        <div
          style={{
            borderTop: "1px solid var(--border-color)",
            paddingTop: 12,
            display: "flex",
            gap: 10,
            alignItems: "flex-end",
          }}
        >
          <Input.TextArea
            className="focus-ring"
            value={input}
            autoSize={{ minRows: 1, maxRows: 4 }}
            placeholder="输入英文句子，Enter 发送，Shift+Enter 换行"
            onChange={setInput}
            onPressEnter={(event) => {
              if (event.shiftKey || event.nativeEvent.isComposing) return;
              event.preventDefault();
              void send(input, null);
            }}
            disabled={streaming}
            aria-label="对话输入框"
          />

          {streaming ? (
            <Tooltip content="中止生成">
              <Button
                type="primary"
                status="danger"
                className="focus-ring"
                icon={<IconStop />}
                onClick={handleStop}
                aria-label="中止生成"
              />
            </Tooltip>
          ) : (
            <Tooltip content="发送（Enter）">
              <Button
                type="primary"
                className="focus-ring"
                icon={<IconSend />}
                onClick={() => void send(input, null)}
                disabled={!input.trim()}
                aria-label="发送消息"
              />
            </Tooltip>
          )}
        </div>
      </Card>

      <Typography.Text
        type="secondary"
        style={{ display: "block", marginTop: 10, fontSize: 12, textAlign: "center" }}
      >
        <IconMessage style={{ marginRight: 4 }} />
        回复经后端代理转发，密钥不落前端；断网或超时会提示并支持一键重试。
        <IconBulb style={{ marginLeft: 8, marginRight: 4 }} />
        纠错区块格式：[语法指正] / [地道表达]
      </Typography.Text>
    </div>
  );
}
