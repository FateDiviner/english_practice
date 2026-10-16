/**
 * 伴学上下文：让 AI 知道你正在练哪个词。
 *
 * 走 sessionStorage 而不是后端会话，是因为它是一次性的——从默写页或错题本
 * 跳过来时带一次，进入伴学页后交给用户自行决定是否保留。
 */

export interface ChatContext {
  word: string;
  translation?: string;
  phonetic?: string;
  /** 默写场景下用户实际拼成了什么 */
  typed?: string;
  /** 错题本场景下的英文例句（未挖空） */
  example?: string;
  /** practice: 默写答错 / wrong_book: 错题本条目 */
  source: "practice" | "wrong_book";
}

export const CHAT_CONTEXT_KEY = "ep_chat_context";

/** 后端 context 字段上限：ChatSendRequest.context 的 max_length */
const CONTEXT_LIMIT = 500;

export function writeChatContext(context: ChatContext): void {
  sessionStorage.setItem(CHAT_CONTEXT_KEY, JSON.stringify(context));
}

/** 读取并清除：读一次即焚，避免旧上下文污染后续对话 */
export function readChatContext(): ChatContext | null {
  const raw = sessionStorage.getItem(CHAT_CONTEXT_KEY);
  if (!raw) return null;
  sessionStorage.removeItem(CHAT_CONTEXT_KEY);

  try {
    const parsed = JSON.parse(raw) as ChatContext;
    if (parsed && typeof parsed.word === "string" && parsed.word.trim()) {
      return parsed;
    }
    return null;
  } catch {
    // 兼容早期直接塞纯字符串的写法
    return { word: raw, source: "practice" };
  }
}

export function clearChatContext(): void {
  sessionStorage.removeItem(CHAT_CONTEXT_KEY);
}

/** 拼成后端 context 文本；例句排最后，超长时截断也不会丢掉核心信息 */
export function describeContext(context: ChatContext): string {
  const parts = [`word: ${context.word}`];
  if (context.translation) parts.push(`meaning: ${context.translation}`);
  if (context.phonetic) parts.push(`pronunciation: ${context.phonetic}`);
  if (context.typed) parts.push(`the learner typed: ${context.typed}`);
  if (context.example) parts.push(`example: ${context.example}`);

  const kind =
    context.source === "wrong_book" ? "wrong-book entry" : "recent misspelling";
  return `The learner is asking about this ${kind}. ${parts.join("; ")}`.slice(
    0,
    CONTEXT_LIMIT
  );
}
