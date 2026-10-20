import { getToken, getGuestId } from "./client";
import { RequestError } from "./client";
import type {
  ChatMessage,
  ChatPreset,
  ChatSource,
  FeedbackBlock,
  RagStatusPayload,
} from "@/types";

/** 流式结束帧 */
export interface StreamDone {
  message_id: number;
  content: string;
  feedback: FeedbackBlock | null;
  /** 本次回答引用的资料来源，为空表示没走 RAG 或没命中 */
  sources: ChatSource[];
  created_at: string;
}

export interface StreamHandlers {
  onStart?: () => void;
  /** 检索阶段的进展。生成开始前推给前端，把等待显形 */
  onStatus?: (payload: RagStatusPayload) => void;
  onDelta: (delta: string) => void;
  onDone: (payload: StreamDone) => void;
  /** 网络中断 / 超时，retryable 决定是否展示一键重试 */
  onError: (message: string, retryable: boolean) => void;
}

export interface SendOptions {
  content: string;
  preset?: ChatPreset | null;
  context?: string | null;
  signal?: AbortSignal;
}

/** 拉取对话历史 */
export async function fetchMessages(): Promise<ChatMessage[]> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const guest = getGuestId();
  if (guest) headers["X-Guest-Id"] = guest;

  const response = await fetch("/api/chat/messages", { headers });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({ detail: "加载对话失败" }))) as {
      detail?: string;
    };
    throw new RequestError(body.detail ?? "加载对话失败", response.status, true);
  }
  return (await response.json()) as ChatMessage[];
}

/** 清空对话历史 */
export async function clearMessages(): Promise<void> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const guest = getGuestId();
  if (guest) headers["X-Guest-Id"] = guest;

  const response = await fetch("/api/chat/messages", {
    method: "DELETE",
    headers,
  });
  if (!response.ok) {
    throw new RequestError("清空对话失败", response.status, false);
  }
}

/**
 * 以 SSE 逐字流式发送消息。
 * 采用 fetch + ReadableStream 手工解析，支持 AbortController 随时中止。
 */
export async function streamChat(
  options: SendOptions,
  handlers: StreamHandlers
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const guest = getGuestId();
  if (guest) headers["X-Guest-Id"] = guest;

  let response: Response;
  try {
    response = await fetch("/api/chat/send", {
      method: "POST",
      headers,
      body: JSON.stringify({
        content: options.content,
        preset: options.preset ?? null,
        context: options.context ?? null,
      }),
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    handlers.onError("网络连接失败，请检查网络后重试", true);
    return;
  }

  if (!response.ok || !response.body) {
    const body = (await response.json().catch(() => ({ detail: "发送失败，请重试" }))) as {
      detail?: string;
    };
    handlers.onError(body.detail ?? "发送失败，请重试", true);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let separator = buffer.indexOf("\n\n");
      while (separator !== -1) {
        const block = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);
        handleBlock(block, handlers);
        separator = buffer.indexOf("\n\n");
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    handlers.onError("连接中断，请点击重试", true);
  }
}

/** 解析单个 SSE 数据帧 */
function handleBlock(block: string, handlers: StreamHandlers): void {
  const line = block.split("\n").find((item) => item.startsWith("data:"));
  if (!line) return;

  const raw = line.slice(5).trim();
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return;
  }

  const type = payload.type;
  if (type === "start") {
    handlers.onStart?.();
    return;
  }
  if (type === "status") {
    handlers.onStatus?.(payload as unknown as RagStatusPayload);
    return;
  }
  if (type === "delta") {
    handlers.onDelta(String(payload.delta ?? ""));
    return;
  }
  if (type === "error") {
    handlers.onError(String(payload.message ?? "生成失败，请重试"), Boolean(payload.retryable));
    return;
  }
  if (type === "done") {
    handlers.onDone({
      message_id: Number(payload.message_id ?? 0),
      content: String(payload.content ?? ""),
      feedback: (payload.feedback as FeedbackBlock | null) ?? null,
      sources: (payload.sources as ChatSource[] | undefined) ?? [],
      created_at: String(payload.created_at ?? new Date().toISOString()),
    });
  }
}
