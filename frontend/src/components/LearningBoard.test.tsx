import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import LearningBoard from "@/components/LearningBoard";
import type { DailyStat, RecentSession, StatsOverview } from "@/types";

function daily(words: number[]): DailyStat[] {
  const base = new Date("2026-10-16T00:00:00.000Z");
  return words.map((count, index) => {
    const day = new Date(base.getTime() - (words.length - 1 - index) * 86400000);
    return {
      date: day.toISOString().slice(0, 10),
      sessions: count > 0 ? 1 : 0,
      words: count,
      correct: count,
      accuracy: count > 0 ? 100 : 0,
    };
  });
}

function overview(overrides: Partial<StatsOverview> = {}): StatsOverview {
  return {
    consecutive_days: 4,
    checked_in_today: true,
    today: { date: "2026-10-16", sessions: 1, words: 12, correct: 11, accuracy: 91.7 },
    daily: daily([0, 10, 0, 20, 0, 15, 12]),
    recent: [],
    totals: { mastered: 30, learning: 40, wrong: 5, practiced: 75 },
    ...overrides,
  };
}

describe("学习看板", () => {
  it("展示连续打卡与今日进度", () => {
    render(<LearningBoard overview={overview()} />);

    expect(screen.getByText("连续打卡")).toBeTruthy();
    expect(screen.getByText("[今天已打卡]")).toBeTruthy();
    // Statistic 会把整数与小数拆到不同节点，只能按容器断言
    expect(screen.getByText("连续打卡").parentElement?.textContent).toContain("4天");
    expect(screen.getByText("今天正确率").parentElement?.textContent).toContain("91.7%");
    expect(screen.getByText("今天练习").parentElement?.textContent).toContain("12词");
  });

  it("未打卡时给出明确状态", () => {
    render(<LearningBoard overview={overview({ checked_in_today: false, consecutive_days: 0 })} />);

    expect(screen.getByText("[今天还没打卡]")).toBeTruthy();
  });

  it("柱状图为每天提供可读的无障碍标签", () => {
    render(<LearningBoard overview={overview()} />);

    const bars = screen.getAllByRole("img");
    expect(bars).toHaveLength(7);
    expect(bars[6].getAttribute("aria-label")).toContain("练习 12 词");
    expect(bars[0].getAttribute("aria-label")).toContain("练习 0 词");
  });

  it("今天单独标注而不是重复日期", () => {
    render(<LearningBoard overview={overview()} />);

    expect(screen.getByText("今天")).toBeTruthy();
    expect(screen.getByText("10/10")).toBeTruthy();
  });

  it("近 7 天无练习时给出空态而不是空白图表", () => {
    render(<LearningBoard overview={overview({ daily: daily([0, 0, 0, 0, 0, 0, 0]) })} />);

    expect(screen.getByText(/完成一次练习后/)).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("最近练习最多展示三条", () => {
    const recent: RecentSession[] = Array.from({ length: 5 }, (_, index) => ({
      date: "2026-10-16",
      wordbook_id: 1,
      wordbook_title: "CET-4 核心高频词",
      mode: index === 0 ? "review" : "normal",
      total: 10,
      correct: 9,
      accuracy: 90,
      duration_ms: 60000,
    }));
    render(<LearningBoard overview={overview({ recent })} />);

    expect(screen.getByText("最近练习")).toBeTruthy();
    expect(screen.getAllByText("CET-4 核心高频词")).toHaveLength(3);
    expect(screen.getByText("复习")).toBeTruthy();
  });

  it("无练习记录时不渲染最近练习区块", () => {
    render(<LearningBoard overview={overview({ recent: [] })} />);

    expect(screen.queryByText("最近练习")).toBeNull();
  });
});
