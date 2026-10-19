import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/pages/DashboardPage";
import { fetchProgress, fetchWordbooks } from "@/api/wordbooks";
import { fetchReviewQueue, startPractice } from "@/api/practice";
import { fetchOverview } from "@/api/stats";
import type { ReviewQueue, StatsOverview, WordBook, WordBookProgress } from "@/types";

vi.mock("@/api/wordbooks", () => ({
  fetchWordbooks: vi.fn(),
  fetchProgress: vi.fn(),
  activateWordbook: vi.fn(),
}));

// 练习 store 也从该模块取接口，必须一并提供，否则 import 阶段就报 undefined
vi.mock("@/api/practice", () => ({
  fetchReviewQueue: vi.fn(),
  startPractice: vi.fn(),
  fetchHint: vi.fn(),
  submitAnswer: vi.fn(),
  finishPractice: vi.fn(),
}));

vi.mock("@/api/stats", () => ({
  fetchOverview: vi.fn(),
}));

const mockedFetchWordbooks = vi.mocked(fetchWordbooks);
const mockedFetchProgress = vi.mocked(fetchProgress);
const mockedFetchReviewQueue = vi.mocked(fetchReviewQueue);
const mockedStartPractice = vi.mocked(startPractice);
const mockedFetchOverview = vi.mocked(fetchOverview);

const BOOK: WordBook = {
  id: 1,
  code: "cet4",
  title: "CET-4 核心高频词",
  description: "大学英语四级高频词",
  difficulty: "四级",
  total_words: 100,
};

const PROGRESS: WordBookProgress = {
  wordbook_id: 1,
  total_words: 100,
  mastered: 10,
  learning: 20,
  wrong: 5,
  untouched: 65,
  accuracy: 82.5,
};

const STATS: StatsOverview = {
  consecutive_days: 3,
  checked_in_today: false,
  today: { date: "2026-10-16", sessions: 0, words: 0, correct: 0, accuracy: 0 },
  daily: [],
  recent: [],
  totals: { mastered: 0, learning: 0, wrong: 0, practiced: 0 },
};

const QUEUE: ReviewQueue = {
  wordbook_id: 1,
  total: 3,
  overdue: 2,
  due_today: 1,
  upcoming_7d: 7,
  preview: [],
};

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/practice" element={<div data-testid="practice-page" />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  mockedFetchWordbooks.mockResolvedValue([BOOK]);
  mockedFetchProgress.mockResolvedValue(PROGRESS);
  mockedFetchReviewQueue.mockResolvedValue(QUEUE);
  mockedFetchOverview.mockResolvedValue(STATS);
  mockedStartPractice.mockResolvedValue({
    session_id: "s-1",
    wordbook_id: 1,
    mode: "review",
    total: 2,
    clues: [],
  });
});

describe("学习看板", () => {
  it("进入词书中心即拉取看板概览", async () => {
    renderDashboard();

    expect(await screen.findByText("学习看板")).toBeTruthy();
    expect(mockedFetchOverview).toHaveBeenCalledTimes(1);
  });

  it("看板拉取失败时不影响词书列表", async () => {
    mockedFetchOverview.mockRejectedValue(new Error("boom"));
    renderDashboard();

    expect(await screen.findByText("词书中心")).toBeTruthy();
    expect(screen.queryByText("学习看板")).toBeNull();
  });
});

describe("今日复习入口", () => {
  it("按到期数量显示入口文案", async () => {
    renderDashboard();

    expect(await screen.findByRole("button", { name: /今日复习（3）/ })).toBeTruthy();
    expect(mockedFetchReviewQueue).toHaveBeenCalledWith(BOOK.id);
  });

  it("展示逾期与今日到期的拆分明细", async () => {
    renderDashboard();

    expect(
      await screen.findByText(/今日待复习 3（已过期 2 · 今日到期 1）/)
    ).toBeTruthy();
    expect(screen.getByText(/未来 7 天还有 7 个词到期/)).toBeTruthy();
  });

  it("没有到期词时禁用入口并给出解释", async () => {
    mockedFetchReviewQueue.mockResolvedValue({
      ...QUEUE,
      total: 0,
      overdue: 0,
      due_today: 0,
      upcoming_7d: 0,
    });
    renderDashboard();

    const button = await screen.findByRole("button", { name: /^今日复习$/ });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(true));
    expect(screen.queryByText(/今日待复习/)).toBeNull();
  });

  it("点击后以 review 模式开局并跳转练习页", async () => {
    renderDashboard();

    fireEvent.click(await screen.findByRole("button", { name: /今日复习（3）/ }));

    await waitFor(() =>
      expect(mockedStartPractice).toHaveBeenCalledWith(
        BOOK.id,
        expect.any(Number),
        "review"
      )
    );
    expect(await screen.findByTestId("practice-page")).toBeTruthy();
  });

  it("切换词书后按新词书重新统计", async () => {
    const second: WordBook = { ...BOOK, id: 2, title: "CET-6 核心高频词" };
    mockedFetchWordbooks.mockResolvedValue([BOOK, second]);
    renderDashboard();

    await screen.findByRole("button", { name: /今日复习（3）/ });
    mockedFetchReviewQueue.mockClear();

    fireEvent.click(screen.getByText(second.title));

    await waitFor(() => expect(mockedFetchReviewQueue).toHaveBeenCalledWith(2));
  });
});
