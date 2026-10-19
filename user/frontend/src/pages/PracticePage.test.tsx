import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PracticePage from "@/pages/PracticePage";
import { usePracticeStore } from "@/stores/practice";
import { submitAnswer } from "@/api/practice";
import { CHAT_CONTEXT_KEY } from "@/utils/chatContext";
import type { PracticeStartResponse, SubmitResponse } from "@/types";

vi.mock("@/api/practice", () => ({
  startPractice: vi.fn(),
  submitAnswer: vi.fn(),
  fetchHint: vi.fn(),
  finishPractice: vi.fn(),
  fetchReviewQueue: vi.fn(),
}));

const mockedSubmitAnswer = vi.mocked(submitAnswer);

const SESSION: PracticeStartResponse = {
  session_id: "s-1",
  wordbook_id: 1,
  mode: "normal",
  total: 1,
  clues: [
    {
      id: 11,
      translation: "v. 放弃，遗弃",
      phonetic: "/əˈbændən/",
      example_en_masked: "He ___ his car in the snow.",
      example_cn: "他把车丢弃在雪地里。",
      pos: "v.",
      speak: "abandon",
    },
  ],
};

const WRONG: SubmitResponse = {
  correct: false,
  answer: "abandon",
  submitted: "abandn",
  pos: "v.",
  phonetic: "/əˈbændən/",
  translation: "v. 放弃，遗弃",
  diff: [],
  message: "[拼写错误] 请对照正确拼写订正",
  wrong_count: 1,
  answered: 1,
  total: 1,
};

const CORRECT: SubmitResponse = { ...WRONG, correct: true, submitted: "abandon" };

function renderPractice() {
  return render(
    <MemoryRouter initialEntries={["/practice"]}>
      <Routes>
        <Route path="/practice" element={<PracticePage />} />
      </Routes>
    </MemoryRouter>
  );
}

function typeAndSubmit(text: string) {
  const input = screen.getByLabelText("单词拼写输入框");
  fireEvent.change(input, { target: { value: text } });
  fireEvent.keyDown(input, { key: "Enter", keyCode: 13 });
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  usePracticeStore.getState().reset();
  // 直接注入一场进行中的练习，绕开对开局接口的依赖
  usePracticeStore.setState({
    session: SESSION,
    index: 0,
    phase: "running",
    result: null,
    hint: null,
    error: null,
    settlement: null,
  });
});

describe("默写答错后的伴学上下文", () => {
  it("答错时把词、错拼与释义交给伴学页", async () => {
    mockedSubmitAnswer.mockResolvedValue(WRONG);
    renderPractice();

    typeAndSubmit("abandn");

    await waitFor(() =>
      expect(sessionStorage.getItem(CHAT_CONTEXT_KEY)).not.toBeNull()
    );
    const parsed = JSON.parse(sessionStorage.getItem(CHAT_CONTEXT_KEY) as string);
    expect(parsed.word).toBe("abandon");
    expect(parsed.typed).toBe("abandn");
    expect(parsed.translation).toBe("v. 放弃，遗弃");
    expect(parsed.phonetic).toBe("/əˈbændən/");
    expect(parsed.source).toBe("practice");
  });

  it("答对时不写入上下文", async () => {
    mockedSubmitAnswer.mockResolvedValue(CORRECT);
    renderPractice();

    typeAndSubmit("abandon");

    await waitFor(() =>
      expect(mockedSubmitAnswer).toHaveBeenCalledWith(
        expect.any(String),
        11,
        "abandon",
        false
      )
    );
    expect(sessionStorage.getItem(CHAT_CONTEXT_KEY)).toBeNull();
  });

  it("错误反馈区仍然给出订正提示", async () => {
    mockedSubmitAnswer.mockResolvedValue(WRONG);
    renderPractice();

    typeAndSubmit("abandn");

    expect(await screen.findByText(/请对照正确拼写订正/)).toBeTruthy();
    // 键盘流契约未被破坏：输入框仍在
    expect(screen.getByLabelText("单词拼写输入框")).toBeTruthy();
  });
});
