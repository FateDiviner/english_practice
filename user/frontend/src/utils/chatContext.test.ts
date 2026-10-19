import { describe, expect, it, beforeEach } from "vitest";
import {
  CHAT_CONTEXT_KEY,
  clearChatContext,
  describeContext,
  readChatContext,
  writeChatContext,
  type ChatContext,
} from "@/utils/chatContext";

const CONTEXT: ChatContext = {
  word: "abandon",
  translation: "v. 放弃，遗弃",
  phonetic: "/əˈbændən/",
  typed: "abandn",
  source: "practice",
};

beforeEach(() => {
  sessionStorage.clear();
});

describe("上下文写入与读取", () => {
  it("写入后可以读回同一份内容", () => {
    writeChatContext(CONTEXT);

    expect(readChatContext()).toEqual(CONTEXT);
  });

  it("读取一次即焚，不会污染后续对话", () => {
    writeChatContext(CONTEXT);

    expect(readChatContext()).not.toBeNull();
    expect(readChatContext()).toBeNull();
    expect(sessionStorage.getItem(CHAT_CONTEXT_KEY)).toBeNull();
  });

  it("没有上下文时返回 null", () => {
    expect(readChatContext()).toBeNull();
  });

  it("兼容早期塞进去的纯字符串", () => {
    sessionStorage.setItem(CHAT_CONTEXT_KEY, "abandon");

    const context = readChatContext();

    expect(context?.word).toBe("abandon");
    expect(context?.source).toBe("practice");
  });

  it("损坏的 JSON 不会让页面崩掉", () => {
    sessionStorage.setItem(CHAT_CONTEXT_KEY, "{not json");

    expect(readChatContext()).not.toBeNull();
  });

  it("clearChatContext 可以主动丢弃", () => {
    writeChatContext(CONTEXT);
    clearChatContext();

    expect(readChatContext()).toBeNull();
  });
});

describe("describeContext 拼装", () => {
  it("带上词、释义、音标与错拼", () => {
    const text = describeContext(CONTEXT);

    expect(text).toContain("abandon");
    expect(text).toContain("v. 放弃，遗弃");
    expect(text).toContain("/əˈbændən/");
    expect(text).toContain("the learner typed: abandn");
    expect(text).toContain("recent misspelling");
  });

  it("错题本来源单独标注", () => {
    const text = describeContext({ ...CONTEXT, source: "wrong_book" });

    expect(text).toContain("wrong-book entry");
    expect(text).not.toContain("recent misspelling");
  });

  it("超长内容被截断，绝不触碰后端 500 字上限", () => {
    const long = describeContext({
      ...CONTEXT,
      example: "a".repeat(2000),
    });

    expect(long.length).toBeLessThanOrEqual(500);
    // 核心信息在前，截断只影响例句尾部
    expect(long).toContain("word: abandon");
  });

  it("缺省字段不会产生空的键值对", () => {
    const text = describeContext({ word: "ability", source: "wrong_book" });

    expect(text).not.toContain("meaning:");
    expect(text).not.toContain("example:");
    expect(text).toContain("ability");
  });
});
