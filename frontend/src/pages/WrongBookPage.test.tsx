import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WrongBookPage from "@/pages/WrongBookPage";
import { fetchWrongBook } from "@/api/practice";
import { CHAT_CONTEXT_KEY } from "@/utils/chatContext";
import type { WrongBookItem } from "@/types";

vi.mock("@/api/practice", () => ({
  fetchWrongBook: vi.fn(),
  fetchReviewQueue: vi.fn(),
  startPractice: vi.fn(),
  fetchHint: vi.fn(),
  submitAnswer: vi.fn(),
  finishPractice: vi.fn(),
}));

const mockedFetchWrongBook = vi.mocked(fetchWrongBook);

const ITEM: WrongBookItem = {
  word_id: 11,
  wordbook_id: 1,
  word: "abandon",
  phonetic: "/əˈbændən/",
  translation: "v. 放弃，遗弃",
  wrong_count: 3,
  example_en: "He abandoned his car in the snow.",
  example_cn: "他把车丢弃在雪地里。",
  last_practiced: "2026-10-16T08:00:00",
};

function renderWrongBook() {
  return render(
    <MemoryRouter initialEntries={["/wrong-book"]}>
      <Routes>
        <Route path="/wrong-book" element={<WrongBookPage />} />
        <Route path="/chat" element={<div data-testid="chat-page" />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  mockedFetchWrongBook.mockResolvedValue({ total: 1, items: [ITEM] });
});

describe("错题本 AI 讲解", () => {
  it("每条错题都提供 AI 讲解入口", async () => {
    renderWrongBook();

    expect(await screen.findByRole("button", { name: /AI 讲解/ })).toBeTruthy();
  });

  it("点击后把词、释义、音标与例句写入上下文", async () => {
    renderWrongBook();

    fireEvent.click(await screen.findByRole("button", { name: /AI 讲解/ }));

    const raw = sessionStorage.getItem(CHAT_CONTEXT_KEY);
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw as string);
    expect(parsed.word).toBe("abandon");
    expect(parsed.translation).toBe("v. 放弃，遗弃");
    expect(parsed.phonetic).toBe("/əˈbændən/");
    expect(parsed.example).toBe("He abandoned his car in the snow.");
    expect(parsed.source).toBe("wrong_book");
  });

  it("点击后跳转伴学页", async () => {
    renderWrongBook();

    fireEvent.click(await screen.findByRole("button", { name: /AI 讲解/ }));

    expect(await screen.findByTestId("chat-page")).toBeTruthy();
  });

  it("发音按钮仍然可用，讲解入口不抢走它", async () => {
    renderWrongBook();

    const speak = await screen.findByRole("button", { name: /发音/ });
    expect(speak).toBeTruthy();
    expect(screen.getByRole("button", { name: /错题专项重练/ })).toBeTruthy();
  });

  it("空错题本不显示讲解入口", async () => {
    mockedFetchWrongBook.mockResolvedValue({ total: 0, items: [] });
    renderWrongBook();

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /AI 讲解/ })).toBeNull()
    );
  });
});
