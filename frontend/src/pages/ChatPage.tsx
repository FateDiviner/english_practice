import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
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
  IconClose,
} from "@arco-design/web-react/icon";
import type {
  AgentEventPayload,
  AgentMetadata,
  ChatMessage,
  ChatPreset,
  ChatSource,
  FeedbackBlock,
  RagStatusPayload,
} from "@/types";
import { clearMessages, fetchMessages, streamChat } from "@/api/chat";
import {
  clearChatContext,
  describeContext,
  readChatContext,
  type ChatContext,
} from "@/utils/chatContext";
import { isNearBottom } from "@/utils/scroll";
import { toMessage } from "@/api/client";

/**
 * Arco TextArea 的 ref 句柄，结构等价于官方 RefTextAreaType。
 * 本地声明可避免依赖组件库的深层导入路径。
 */
type TextAreaHandle = {
  focus: () => void;
  blur: () => void;
  dom: HTMLTextAreaElement;
};

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
      data-testid="chat-feedback"
      style={{
        marginTop: 8,
        padding: "10px 12px",
        borderRadius: "var(--border-radius-md)",
        background: "var(--color-primary-soft)",
        borderLeft: "3px solid var(--color-primary)",
        overflowWrap: "anywhere",
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

/** 引用来源标签：让用户能自己核对 AI 说了什么依据 */
function SourceTags({ sources }: { sources: ChatSource[] }) {
  if (sources.length === 0) return null;
  return (
    <div
      data-testid="chat-sources"
      style={{
        marginTop: 8,
        paddingTop: 8,
        borderTop: "1px solid var(--border-color)",
        display: "flex",
        flexWrap: "wrap",
        gap: 4,
      }}
    >
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        引用：
      </Typography.Text>
      {sources.map((source) => (
        <Tooltip key={`${source.kind}-${source.index}`} content={source.label}>
          <Tag size="small" color="gray" style={{ maxWidth: 180 }}>
            [{source.index}] {source.label}
          </Tag>
        </Tooltip>
      ))}
    </div>
  );
}

/** Agent 规划、工具调用和降级状态条 */
function AgentStatusBar({ status }: { status: AgentEventPayload }) {
  let text = "";
  if (status.phase === "planning") {
    text = `[Agent 规划中] 第 ${status.round ?? 1} 轮`;
  } else if (status.phase === "tool_call") {
    const toolLabel = status.tool === "lookup_word" ? "查询单词" : "查询知识库";
    text = `[${toolLabel}] ${status.query ?? ""}`.trim();
  } else if (status.phase === "tool_result") {
    const toolLabel = status.tool === "lookup_word" ? "单词查询" : "知识库检索";
    text = status.success === false
      ? `[${toolLabel}失败]`
      : `[${toolLabel}完成] ${status.hits ?? 0} 条结果`;
  } else if (status.phase === "responding") {
    text = "[正在生成回答]";
  } else if (status.phase === "fallback") {
    text = "[已降级到标准问答]";
  }
  if (!text) return null;
  return (
    <div data-testid="chat-agent-status" style={{ marginBottom: 8 }}>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {text}
      </Typography.Text>
    </div>
  );
}

/** 历史消息中的简要 Agent 执行摘要 */
function AgentMetaTags({ metadata }: { metadata: AgentMetadata }) {
  if (metadata.mode !== "agent" && !metadata.fallback) return null;
  return (
    <div
      data-testid="chat-agent-meta"
      style={{
        marginTop: 8,
        display: "flex",
        flexWrap: "wrap",
        gap: 4,
      }}
    >
      <Tag size="small" color="gray">
        {metadata.fallback ? "[已降级]" : "[Agent]"}
      </Tag>
      {metadata.mode === "agent" && (
        <Tag size="small" color="gray">
          轮次 {metadata.rounds}
        </Tag>
      )}
      {metadata.tools.map((tool) => (
        <Tag key={tool} size="small" color="gray">
          {tool}
        </Tag>
      ))}
    </div>
  );
}

/** 检索阶段状态条：把生成前那 1~2 秒的等待显形 */
function RagStatusBar({ status }: { status: RagStatusPayload }) {
  if (status.phase === "retrieving") {
    return (
      <div data-testid="chat-rag-status" style={{ marginBottom: 8 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          正在检索知识库…
        </Typography.Text>
      </div>
    );
  }
  if (status.phase === "retrieved") {
    return (
      <div data-testid="chat-rag-status" style={{ marginBottom: 8 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          已命中 {status.hits ?? 0} 条资料
        </Typography.Text>
      </div>
    );
  }
  return null;
}

/** 单条消息气泡：用户靠右、AI 靠左 */
function MessageBubble({
  message,
  sources,
}: {
  message: ChatMessage;
  sources?: ChatSource[];
}) {
  return (
    <div
      style={{
        display: "flex",
        width: "100%",
        minWidth: 0,
        justifyContent: message.role === "user" ? "flex-end" : "flex-start",
        marginBottom: 12,
      }}
    >
      <div
        data-testid={`chat-bubble-${message.role}`}
        style={{
          maxWidth: "78%",
          minWidth: 0,
          padding: "10px 14px",
          borderRadius: "var(--border-radius-md)",
          background:
            message.role === "user"
              ? "var(--color-primary)"
              : "var(--bg-subtle)",
          color: message.role === "user" ? "#fff" : "var(--text-1)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          overflowWrap: "anywhere",
        }}
      >
        <div style={{ fontSize: 14, lineHeight: 1.65 }}>{message.content}</div>
        {message.feedback && message.role === "assistant" && (
          <FeedbackCard feedback={message.feedback} />
        )}
        {message.role === "assistant" && message.metadata && (
          <AgentMetaTags metadata={message.metadata} />
        )}
        {message.role === "assistant" && sources && <SourceTags sources={sources} />}
      </div>
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
  // 从默写页 / 错题本带过来的讲解对象
  const [context, setContext] = useState<ChatContext | null>(null);
  // 检索阶段的进展。生成开始前先推给前端，把那 1~2 秒的等待显形
  const [ragStatus, setRagStatus] = useState<RagStatusPayload | null>(null);
  // LangGraph 规划、工具调用与降级进度
  const [agentStatus, setAgentStatus] = useState<AgentEventPayload | null>(null);
  // 每条 AI 消息引用了哪些资料，key 是 message_id
  const [sourcesMap, setSourcesMap] = useState<Record<number, ChatSource[]>>({});

  const abortRef = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<TextAreaHandle>(null);
  // 贴底标记：用户向上翻阅历史时不再强行拉到底，避免流式输出打断阅读
  const pinnedRef = useRef(true);
  // 记住最近一次请求，供失败后一键重试
  const retryRef = useRef<{ content: string; preset: ChatPreset | null } | null>(null);
  const contextRef = useRef<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const history = await fetchMessages();
      setMessages(history);
      const restoredSources: Record<number, ChatSource[]> = {};
      for (const item of history) {
        if (item.metadata && item.metadata.sources.length > 0) {
          restoredSources[item.id] = item.metadata.sources;
        }
      }
      setSourcesMap(restoredSources);
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
    // 从默写页 / 错题本带过来的上下文（读一次即焚）
    const fromStorage = readChatContext();
    if (fromStorage) {
      setContext(fromStorage);
      contextRef.current = describeContext(fromStorage);
    }
    return () => abortRef.current?.abort();
  }, [loadHistory]);

  const handleScroll = useCallback(() => {
    const node = listRef.current;
    if (node) pinnedRef.current = isNearBottom(node);
  }, []);

  // 仅在贴底时跟随新内容滚动；向上翻阅历史则保持用户当前位置
  useEffect(() => {
    if (!pinnedRef.current) return;
    const node = listRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, streamText]);

  // 键盘流：进入页面与流式结束后输入框重新聚焦，随时可直接打字
  useEffect(() => {
    if (streaming) return;
    const raf = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(raf);
  }, [streaming]);

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
      // 主动发送视为回到贴底，恢复自动跟随
      pinnedRef.current = true;

      const optimistic: ChatMessage = {
        id: Date.now(),
        role: "user",
        content: text,
        feedback: null,
        metadata: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimistic]);

      const controller = new AbortController();
      abortRef.current = controller;

      await streamChat(
        { content: text, preset, context: contextRef.current, signal: controller.signal },
        {
          onAgent: (payload) => {
            setAgentStatus(payload);
          },
          onStatus: (payload) => {
            // retrieved 带来源，skipped 带原因；retrieving 之后若没等到
            // retrieved 就直接出 delta，说明检索降级了，状态条自然消失
            setRagStatus(payload);
          },
          onDelta: (delta) => {
            // 第一个字开始流式后，状态条就该让位给正文
            setRagStatus((current) =>
              current && current.phase === "retrieving" ? null : current
            );
            setAgentStatus(null);
            setStreamText((prev) => prev + delta);
          },
          onDone: (payload) => {
            setMessages((prev) => [
              ...prev,
              {
                id: payload.message_id,
                role: "assistant",
                content: payload.content,
                feedback: payload.feedback,
                metadata: payload.metadata,
                created_at: payload.created_at,
              },
            ]);
            const doneSources =
              payload.metadata?.sources.length ? payload.metadata.sources : payload.sources;
            if (doneSources.length > 0) {
              setSourcesMap((prev) => ({ ...prev, [payload.message_id]: doneSources }));
            }
            setStreamText("");
            setStreamFeedback(null);
            setRagStatus(null);
            setAgentStatus(null);
            setStreaming(false);
            contextRef.current = null;
          },
          onError: (message, retryable) => {
            setStreaming(false);
            setStreamText("");
            setRagStatus(null);
            setAgentStatus(null);
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
    setRagStatus(null);
    setAgentStatus(null);
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
    // 带着讲解对象时直接把词交给 AI，比发一句 "Explain a word" 更明确
    const content = preset === "explain_word" && context ? context.word : label;
    void send(content, preset);
  };

  const dropContext = () => {
    setContext(null);
    contextRef.current = null;
    clearChatContext();
  };

  /** 历史按日分组；日期口径与全项目一致，取 UTC 自然日 */
  const dayMarks = useMemo(() => {
    const now = new Date();
    return {
      today: now.toISOString().slice(0, 10),
      yesterday: new Date(now.getTime() - 86400000).toISOString().slice(0, 10),
    };
  }, []);

  const labelOf = (iso: string) => {
    const day = iso.slice(0, 10);
    if (day === dayMarks.today) return "今天";
    if (day === dayMarks.yesterday) return "昨天";
    return day;
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

      {context && (
        <div
          data-testid="chat-context"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexWrap: "wrap",
            marginBottom: 12,
            padding: "8px 12px",
            borderRadius: "var(--border-radius-md)",
            background: "var(--color-primary-soft)",
            borderLeft: "3px solid var(--color-primary)",
          }}
        >
          <Typography.Text style={{ fontSize: 13 }}>当前讲解对象</Typography.Text>
          <Tag size="small" color="arcoblue">
            {context.word}
          </Tag>
          {context.translation && (
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              {context.translation}
            </Typography.Text>
          )}
          <Button
            size="mini"
            type="text"
            className="focus-ring"
            icon={<IconClose />}
            aria-label="移除讲解对象"
            onClick={dropContext}
          >
            移除
          </Button>
        </div>
      )}

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

      {/*
        Card 的 style 落在外层 .arco-card，而消息区与输入区实际挂在 .arco-card-body 下。
        若只在外层开 flex，body 仍是普通 block，列表拿不到高度约束就不会滚动，
        内容会撑破卡片固定高度溢出到对话框外，因此 flex 约束必须经 bodyStyle 下沉一层。
      */}
      <Card
        className="card"
        style={{
          height: "clamp(320px, 56vh, 560px)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        bodyStyle={{
          flex: 1,
          minHeight: 0,
          display: "flex",
          flexDirection: "column",
          padding: "12px 16px 14px",
        }}
      >
        <div
          ref={listRef}
          data-testid="chat-list"
          role="log"
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            overflowX: "hidden",
            padding: "4px 4px 12px",
          }}
          aria-live="polite"
          onScroll={handleScroll}
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

          {messages.map((message, index) => {
            const label = labelOf(message.created_at);
            const previous = messages[index - 1];
            const showDivider = !previous || labelOf(previous.created_at) !== label;
            return (
              <Fragment key={`${message.role}-${message.id}`}>
                {showDivider && (
                  <div style={{ textAlign: "center", margin: "10px 0 12px" }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {label}
                    </Typography.Text>
                  </div>
                )}
                <MessageBubble
                  message={message}
                  sources={sourcesMap[message.id]}
                />
              </Fragment>
            );
          })}

          {agentStatus && <AgentStatusBar status={agentStatus} />}
          {ragStatus && <RagStatusBar status={ragStatus} />}

          {streaming && (
            <div
              data-testid="chat-streaming"
              style={{
                display: "flex",
                width: "100%",
                minWidth: 0,
                justifyContent: "flex-start",
                marginBottom: 12,
              }}
            >
              <div
                style={{
                  maxWidth: "78%",
                  minWidth: 0,
                  padding: "10px 14px",
                  borderRadius: "var(--border-radius-md)",
                  background: "var(--bg-subtle)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  overflowWrap: "anywhere",
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
            flexShrink: 0,
          }}
        >
          <Input.TextArea
            ref={inputRef}
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
