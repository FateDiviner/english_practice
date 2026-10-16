import { create } from "zustand";
import type {
  HintResponse,
  PracticeStartResponse,
  SettlementResponse,
  SubmitResponse,
} from "@/types";
import { fetchHint, finishPractice, startPractice, submitAnswer } from "@/api/practice";
import { toMessage } from "@/api/client";
import { useAppStore } from "@/stores/app";

/** 练习模式：常规默写 / 错题重练 / 今日到期词复习 */
export type PracticeMode = "normal" | "wrong_book" | "review";

export type PracticePhase =
  | "idle"
  | "starting"
  | "running"
  | "correct"
  | "wrong"
  | "submitting"
  | "finished";

interface PracticeState {
  session: PracticeStartResponse | null;
  index: number;
  phase: PracticePhase;
  /** 最近一次提交的校验结果 */
  result: SubmitResponse | null;
  hint: HintResponse | null;
  error: string | null;
  settlement: SettlementResponse | null;

  start: (wordbookId: number, mode?: PracticeMode) => Promise<void>;
  submit: (answer: string, skipped?: boolean) => Promise<void>;
  revealHint: () => Promise<void>;
  /** 进入下一词；已是最后一词则自动结算 */
  advance: () => Promise<void>;
  reset: () => void;
}

export const usePracticeStore = create<PracticeState>((set, get) => ({
  session: null,
  index: 0,
  phase: "idle",
  result: null,
  hint: null,
  error: null,
  settlement: null,

  start: async (wordbookId: number, mode: PracticeMode = "normal") => {
    const groupSize = useAppStore.getState().groupSize;
    set({ phase: "starting", error: null, session: null, settlement: null });
    try {
      const session = await startPractice(wordbookId, groupSize, mode);
      set({
        session,
        index: 0,
        phase: "running",
        result: null,
        hint: null,
      });
    } catch (error) {
      set({ phase: "idle", error: toMessage(error) });
      throw error;
    }
  },

  submit: async (answer, skipped = false) => {
    const { session, index, phase } = get();
    if (!session || (phase !== "running" && phase !== "wrong")) return;

    const clue = session.clues[index];
    set({ phase: "submitting" });
    try {
      const result = await submitAnswer(session.session_id, clue.id, answer, skipped);
      set({
        result,
        phase: result.correct ? "correct" : "wrong",
        hint: null,
      });
    } catch (error) {
      // 网络异常：退回 running，用户可直接重按回车重试，绝不吞掉已输入内容
      set({ phase: "running", error: toMessage(error) });
    }
  },

  revealHint: async () => {
    const { session, index, hint, phase } = get();
    if (!session || hint || (phase !== "running" && phase !== "wrong")) return;
    try {
      const next = await fetchHint(session.session_id, session.clues[index].id);
      set({ hint: next });
    } catch (error) {
      set({ error: toMessage(error) });
    }
  },

  advance: async () => {
    const { session, index } = get();
    if (!session) return;

    if (index + 1 < session.clues.length) {
      set({ index: index + 1, phase: "running", result: null, hint: null });
      return;
    }

    set({ phase: "submitting" });
    try {
      const settlement = await finishPractice(session.session_id);
      set({ settlement, phase: "finished" });
    } catch (error) {
      set({ phase: "wrong", error: toMessage(error) });
    }
  },

  reset: () => {
    set({
      session: null,
      index: 0,
      phase: "idle",
      result: null,
      hint: null,
      error: null,
      settlement: null,
    });
  },
}));
