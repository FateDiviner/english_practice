/** 全项目数据实体集中定义，严禁散落 any。 */

/** 单词本（词书）卡片 */
export interface WordBook {
  id: number;
  code: string;
  title: string;
  description: string;
  difficulty: string;
  total_words: number;
}

/** 词书学习进度 */
export interface WordBookProgress {
  wordbook_id: number;
  total_words: number;
  mastered: number;
  learning: number;
  wrong: number;
  untouched: number;
  accuracy: number;
}

/** 单词完整信息（结算复盘用） */
export interface Word {
  id: number;
  word: string;
  phonetic: string;
  translation: string;
  example_en: string;
  example_cn: string;
}

/** 用户信息 */
export interface UserInfo {
  id: number;
  username: string;
  is_guest: boolean;
  active_wordbook_id: number | null;
  consecutive_days: number;
  created_at: string;
}

/** 认证响应 */
export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
  migrated: boolean;
}

/** 默写线索 */
export interface WordClue {
  id: number;
  translation: string;
  phonetic: string;
  example_en_masked: string;
  example_cn: string;
  pos: string;
  /** 发音所需的文本，仅供 speechSynthesis 朗读使用 */
  speak: string;
}

/** 练习开场响应 */
export interface PracticeStartResponse {
  session_id: string;
  wordbook_id: number;
  mode: "normal" | "wrong_book" | "review";
  total: number;
  clues: WordClue[];
}

/** 逐字符比对单元 */
export interface DiffCell {
  char: string;
  status: "same" | "wrong" | "extra" | "missing";
}

/** 单次提交校验结果 */
export interface SubmitResponse {
  correct: boolean;
  answer: string;
  submitted: string;
  pos: string;
  phonetic: string;
  translation: string;
  diff: DiffCell[];
  message: string;
  wrong_count: number;
  answered: number;
  total: number;
}

/** 提示响应 */
export interface HintResponse {
  word_id: number;
  masked: string;
  first_letter: string;
  hint_level: number;
}

/** 结算条目 */
export interface SettlementItem {
  word_id: number;
  word: string;
  phonetic: string;
  translation: string;
  correct: boolean;
  submitted: string;
  skipped: boolean;
}

/** 练习结算 */
export interface SettlementResponse {
  session_id: string;
  wordbook_id: number;
  total: number;
  correct_count: number;
  wrong_count: number;
  accuracy: number;
  duration_ms: number;
  items: SettlementItem[];
}

/** 错题本条目 */
export interface WrongBookItem {
  word_id: number;
  wordbook_id: number;
  word: string;
  phonetic: string;
  translation: string;
  wrong_count: number;
  example_en: string;
  example_cn: string;
  last_practiced: string | null;
}

/** 错题本 */
export interface WrongBookResponse {
  total: number;
  items: WrongBookItem[];
}

/** 今日待复习队列的预览条目（刻意不含拼写，防止扫一眼就背过） */
export interface ReviewPreviewItem {
  word_id: number;
  translation: string;
  phonetic: string;
  status: "learning" | "mastered" | "wrong";
  wrong_count: number;
  next_review_at: string | null;
}

/** 某词书今日的复习压力：total = overdue + due_today */
export interface ReviewQueue {
  wordbook_id: number;
  total: number;
  overdue: number;
  due_today: number;
  upcoming_7d: number;
  preview: ReviewPreviewItem[];
}

/** 单日练习统计 */
export interface DailyStat {
  date: string;
  sessions: number;
  words: number;
  correct: number;
  accuracy: number;
}

/** 最近一次练习记录 */
export interface RecentSession {
  date: string;
  wordbook_id: number;
  wordbook_title: string;
  mode: "normal" | "wrong_book" | "review";
  total: number;
  correct: number;
  accuracy: number;
  duration_ms: number;
}

/** 累计学习状态（跨全部词书） */
export interface LearningTotals {
  mastered: number;
  learning: number;
  wrong: number;
  practiced: number;
}

/** 学习看板概览 */
export interface StatsOverview {
  consecutive_days: number;
  checked_in_today: boolean;
  today: DailyStat;
  /** 含今天在内按日升序，未练习日期补零 */
  daily: DailyStat[];
  recent: RecentSession[];
  totals: LearningTotals;
}

/** 备份中的单词记忆状态，用 wordbook.code + word 定位 */
export interface BackupWordRecord {
  wordbook: string;
  word: string;
  status: "learning" | "mastered" | "wrong";
  wrong_count: number;
  right_count: number;
  ease_stage: number;
  last_practiced: string | null;
  next_review_at: string | null;
}

/** 备份中的练习结算记录 */
export interface BackupSession {
  wordbook: string;
  mode: "normal" | "wrong_book" | "review";
  total: number;
  correct: number;
  wrong: number;
  duration_ms: number;
  practiced_on: string;
}

/** 备份中的对话记录，feedback 原样为 JSON 字符串 */
export interface BackupMessage {
  role: string;
  content: string;
  feedback: string | null;
  created_at: string;
}

/** 导出文件的统计摘要 */
export interface BackupSummary {
  words: number;
  sessions: number;
  messages: number;
  consecutive_days: number;
}

/** 一份完整的学习数据备份，可在账号之间搬运 */
export interface BackupFile {
  format: string;
  version: number;
  exported_at: string;
  summary: BackupSummary;
  word_records: BackupWordRecord[];
  sessions: BackupSession[];
  chat_messages: BackupMessage[];
  consecutive_days: number;
  last_checkin_date: string | null;
  active_wordbook: string | null;
}

/** 导入结果统计 */
export interface ImportResult {
  records_new: number;
  records_merged: number;
  sessions_added: number;
  sessions_skipped: number;
  messages_added: number;
  messages_skipped: number;
  words_unmatched: number;
  consecutive_days: number;
}

/** 实时纠错结构化区块 */
export interface FeedbackBlock {
  grammar: string;
  polish: string[];
}

/** 对话消息 */
export interface ChatMessage {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  feedback: FeedbackBlock | null;
  created_at: string;
}

/** 快捷 Prompt 指令 */
export type ChatPreset = "explain_word" | "grammar_check" | "free_chat";

/** 后端统一错误体 */
export interface ApiError {
  detail: string;
}
