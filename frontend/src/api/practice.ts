import { http } from "./client";
import type {
  HintResponse,
  PracticeStartResponse,
  ReviewQueue,
  SettlementResponse,
  SubmitResponse,
  WrongBookResponse,
} from "@/types";

/** 开启一组默写练习 */
export async function startPractice(
  wordbookId: number,
  size: number,
  mode: "normal" | "wrong_book" | "review" = "normal"
): Promise<PracticeStartResponse> {
  const { data } = await http.post<PracticeStartResponse>("/api/practice/start", {
    wordbook_id: wordbookId,
    size,
    mode,
  });
  return data;
}

/** 获取首字母提示 */
export async function fetchHint(sessionId: string, wordId: number): Promise<HintResponse> {
  const { data } = await http.post<HintResponse>("/api/practice/hint", {
    session_id: sessionId,
    word_id: wordId,
  });
  return data;
}

/** 提交一次拼写 */
export async function submitAnswer(
  sessionId: string,
  wordId: number,
  answer: string,
  skipped = false
): Promise<SubmitResponse> {
  const { data } = await http.post<SubmitResponse>("/api/practice/submit", {
    session_id: sessionId,
    word_id: wordId,
    answer,
    skipped,
  });
  return data;
}

/** 结算当前练习 */
export async function finishPractice(sessionId: string): Promise<SettlementResponse> {
  const { data } = await http.post<SettlementResponse>(
    `/api/practice/finish?session_id=${encodeURIComponent(sessionId)}`
  );
  return data;
}

/** 拉取错题本 */
export async function fetchWrongBook(): Promise<WrongBookResponse> {
  const { data } = await http.get<WrongBookResponse>("/api/practice/wrong-book");
  return data;
}

/** 拉取某词书今日的待复习队列 */
export async function fetchReviewQueue(wordbookId: number): Promise<ReviewQueue> {
  const { data } = await http.get<ReviewQueue>("/api/practice/review-queue", {
    params: { wordbook_id: wordbookId },
  });
  return data;
}
