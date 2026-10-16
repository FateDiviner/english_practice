import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChatPage from "@/pages/ChatPage";
import { fetchMessages, streamChat } from "@/api/chat";
import { writeChatContext } from "@/utils/chatContext";
import type { ChatMessage } from "@/types";

vi.mock("@/api/chat", () => ({
  fetchMessages: vi.fn(),
  clearMessages: vi.fn(),
  streamChat: vi.fn(),
}));

const mockedFetchMessages = vi.mocked(fetchMessages);
const mockedStreamChat = vi.mocked(streamChat);

/** jsdom 不会由 key 自动推导 keyCode，这里显式给出，与真实浏览器行为一致 */
const ENTER = { key: "Enter", keyCode: 13 };

const assistantMessage: ChatMessage = {
  id: 7,
  role: "assistant",
  content: 'Nice try! You wrote "I am go to school yesterday".',
  feedback: {
    grammar: "yesterday 需要用过去式 went，且 go to school 前应为 was。",
    polish: ["I went to school yesterday.", "I was on my way to school."],
  },
  created_at: "2026-10-16T08:00:00.000Z",
};

beforeEach(() => {
  sessionStorage.clear();
  mockedFetchMessages.mockResolvedValue([]);
});

function mockStreamDone() {
  mockedStreamChat.mockImplementation(async (_options, handlers) => {
    handlers.onDone({
      message_id: 21,
      content: "Sure, let us look at that word.",
      feedback: null,
      created_at: "2026-10-16T08:00:00.000Z",
    });
  });
}

describe("AI 伴学对话框布局", () => {
  it("消息区挂在可滚动的 flex 链路上，卡片本身裁剪溢出", async () => {
    render(<ChatPage />);

    const list = await screen.findByTestId("chat-list");
    expect(list.getAttribute("role")).toBe("log");
    expect(list.style.overflowY).toBe("auto");
    expect(list.style.overflowX).toBe("hidden");
    expect(list.style.minHeight).toBe("0px");

    // 回归：flex 约束必须下沉到 .arco-card-body，否则列表拿不到高度约束，
    // 内容会撑破固定高度的卡片并溢出到对话框外。
    const body = document.querySelector(".arco-card-body") as HTMLElement;
    expect(body).not.toBeNull();
    expect(body.style.display).toBe("flex");
    expect(body.style.flexDirection).toBe("column");
    expect(body.style.minHeight).toBe("0px");

    const card = document.querySelector(".arco-card") as HTMLElement;
    expect(card.style.display).toBe("flex");
    expect(card.style.flexDirection).toBe("column");
    expect(card.style.overflow).toBe("hidden");
  });

  it("气泡行占满宽度并允许长文本断行", async () => {
    mockedFetchMessages.mockResolvedValue([assistantMessage]);
    render(<ChatPage />);

    const bubble = await screen.findByTestId("chat-bubble-assistant");
    const row = bubble.parentElement as HTMLElement;
    expect(row.style.width).toBe("100%");
    expect(row.style.minWidth).toBe("0px");
    expect(bubble.style.minWidth).toBe("0px");
    expect(bubble.style.overflowWrap).toBe("anywhere");
    expect(bubble.style.maxWidth).toBe("78%");
  });
});

describe("AI 伴学键盘流", () => {
  it("进入页面后输入框自动聚焦", async () => {
    render(<ChatPage />);

    const input = await screen.findByLabelText("对话输入框");
    await waitFor(() => expect(document.activeElement).toBe(input));
  });

  it("回车发送消息并交给 SSE 流式接口", async () => {
    mockedStreamChat.mockImplementation(async (_options, handlers) => {
      handlers.onDone({
        message_id: 11,
        content: "Sounds good!",
        feedback: null,
        created_at: "2026-10-16T08:01:00.000Z",
      });
    });

    render(<ChatPage />);
    const input = await screen.findByLabelText("对话输入框");

    fireEvent.change(input, { target: { value: "I go to school" } });
    fireEvent.keyDown(input, ENTER);

    await waitFor(() =>
      expect(mockedStreamChat).toHaveBeenCalledWith(
        expect.objectContaining({ content: "I go to school", preset: null }),
        expect.anything()
      )
    );
    expect(await screen.findByTestId("chat-bubble-user")).toBeTruthy();
  });

  it("Shift+Enter 只换行不发送", async () => {
    render(<ChatPage />);
    const input = await screen.findByLabelText("对话输入框");

    fireEvent.change(input, { target: { value: "line one" } });
    fireEvent.keyDown(input, { ...ENTER, shiftKey: true });

    expect(mockedStreamChat).not.toHaveBeenCalled();
  });
});

describe("AI 伴学纠错区块展示", () => {
  it("历史消息渲染 [语法指正] 与 [地道表达] 结构化区块", async () => {
    mockedFetchMessages.mockResolvedValue([assistantMessage]);
    render(<ChatPage />);

    expect(await screen.findByTestId("chat-bubble-assistant")).toBeTruthy();
    expect(await screen.findByTestId("chat-feedback")).toBeTruthy();
    expect(screen.getByText("[语法指正]")).toBeTruthy();
    expect(screen.getByText("[地道表达]")).toBeTruthy();
  });
});

describe("讲解对象", () => {
  it("从 sessionStorage 读入并展示词与释义", async () => {
    writeChatContext({
      word: "abandon",
      translation: "v. 放弃，遗弃",
      source: "wrong_book",
    });
    render(<ChatPage />);

    const bar = await screen.findByTestId("chat-context");
    expect(bar.textContent).toContain("当前讲解对象");
    expect(bar.textContent).toContain("abandon");
    expect(bar.textContent).toContain("v. 放弃，遗弃");
  });

  it("移除后不再显示，也不再随消息发送", async () => {
    writeChatContext({ word: "abandon", source: "wrong_book" });
    mockStreamDone();
    render(<ChatPage />);

    fireEvent.click(await screen.findByRole("button", { name: "移除讲解对象" }));
    expect(screen.queryByTestId("chat-context")).toBeNull();

    const input = await screen.findByLabelText("对话输入框");
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.keyDown(input, { key: "Enter", keyCode: 13 });

    await waitFor(() => expect(mockedStreamChat).toHaveBeenCalled());
    expect(mockedStreamChat.mock.calls[0][0].context).toBeNull();
  });

  it("带讲解对象时 explain_word 直接把词交给 AI", async () => {
    writeChatContext({ word: "abandon", source: "wrong_book" });
    mockStreamDone();
    render(<ChatPage />);

    fireEvent.click(await screen.findByText("Explain a word"));

    await waitFor(() =>
      expect(mockedStreamChat).toHaveBeenCalledWith(
        expect.objectContaining({ content: "abandon", preset: "explain_word" }),
        expect.anything()
      )
    );
    // 上下文随请求一起发给后端
    expect(mockedStreamChat.mock.calls[0][0].context).toContain("abandon");
  });

  it("没有讲解对象时 explain_word 仍发送预设文案", async () => {
    mockStreamDone();
    render(<ChatPage />);

    fireEvent.click(await screen.findByText("Explain a word"));

    await waitFor(() =>
      expect(mockedStreamChat).toHaveBeenCalledWith(
        expect.objectContaining({ content: "Explain a word" }),
        expect.anything()
      )
    );
    expect(mockedStreamChat.mock.calls[0][0].context).toBeNull();
  });
});

describe("历史按日分组", () => {
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

  it("今天的对话显示今天分隔", async () => {
    mockedFetchMessages.mockResolvedValue([
      {
        id: 1,
        role: "user",
        content: "hello",
        feedback: null,
        created_at: `${today}T08:00:00`,
      },
    ]);
    render(<ChatPage />);

    expect(await screen.findByText("今天")).toBeTruthy();
  });

  it("更早的对话显示昨天", async () => {
    mockedFetchMessages.mockResolvedValue([
      {
        id: 1,
        role: "user",
        content: "hello",
        feedback: null,
        created_at: `${yesterday}T08:00:00`,
      },
    ]);
    render(<ChatPage />);

    expect(await screen.findByText("昨天")).toBeTruthy();
  });

  it("同一天的多条消息只出现一个分隔", async () => {
    mockedFetchMessages.mockResolvedValue([
      {
        id: 1,
        role: "user",
        content: "hi",
        feedback: null,
        created_at: `${today}T08:00:00`,
      },
      {
        id: 2,
        role: "assistant",
        content: "hello there",
        feedback: null,
        created_at: `${today}T08:01:00`,
      },
    ]);
    render(<ChatPage />);

    expect((await screen.findAllByText("今天")).length).toBe(1);
  });
});
