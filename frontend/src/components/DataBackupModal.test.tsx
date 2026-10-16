import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DataBackupModal from "@/components/DataBackupModal";
import { fetchBackup, importBackup } from "@/api/user";
import type { BackupFile, ImportResult } from "@/types";

vi.mock("@/api/user", () => ({
  fetchBackup: vi.fn(),
  importBackup: vi.fn(),
}));

const mockedFetchBackup = vi.mocked(fetchBackup);
const mockedImportBackup = vi.mocked(importBackup);

function makeBackup(overrides: Partial<BackupFile> = {}): BackupFile {
  return {
    format: "english-practice-backup",
    version: 1,
    exported_at: "2026-10-16T08:00:00Z",
    summary: { words: 2, sessions: 1, messages: 0, consecutive_days: 1 },
    word_records: [
      {
        wordbook: "cet4",
        word: "abandon",
        status: "wrong",
        wrong_count: 1,
        right_count: 0,
        ease_stage: 0,
        last_practiced: null,
        next_review_at: null,
      },
      {
        wordbook: "cet4",
        word: "ability",
        status: "learning",
        wrong_count: 0,
        right_count: 1,
        ease_stage: 1,
        last_practiced: null,
        next_review_at: null,
      },
    ],
    sessions: [
      {
        wordbook: "cet4",
        mode: "normal",
        total: 2,
        correct: 0,
        wrong: 2,
        duration_ms: 1000,
        practiced_on: "2026-10-16",
      },
    ],
    chat_messages: [],
    consecutive_days: 1,
    last_checkin_date: "2026-10-16",
    active_wordbook: "cet4",
    ...overrides,
  };
}

const RESULT: ImportResult = {
  records_new: 2,
  records_merged: 0,
  sessions_added: 1,
  sessions_skipped: 0,
  messages_added: 0,
  messages_skipped: 0,
  words_unmatched: 0,
  consecutive_days: 1,
};

const clickSpy = vi.fn();

function pickFile(content: string, name = "backup.json") {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File([content], name, { type: "application/json" });
  fireEvent.change(input, { target: { files: [file] } });
}

// Arco 的 Modal.confirm 走独立 portal，组件卸载不会带走它，
// 不清理的话上一个用例的弹窗会留到下一个用例里
afterEach(() => {
  document
    .querySelectorAll(".arco-modal, .arco-modal-mask, .arco-message")
    .forEach((node) => node.remove());
});

beforeEach(() => {
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:mock"),
  });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(clickSpy);
});

describe("导出备份", () => {
  it("导出时下载 JSON 文件", async () => {
    mockedFetchBackup.mockResolvedValue(makeBackup());
    render(<DataBackupModal visible onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /导出备份文件/ }));

    await waitFor(() => expect(mockedFetchBackup).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());
    expect((URL.createObjectURL as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(1);
  });

  it("导出失败时不触发下载", async () => {
    mockedFetchBackup.mockRejectedValue(new Error("boom"));
    render(<DataBackupModal visible onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /导出备份文件/ }));

    await waitFor(() => expect(mockedFetchBackup).toHaveBeenCalledTimes(1));
    expect(clickSpy).not.toHaveBeenCalled();
  });
});

describe("导入备份", () => {
  it("先预览条目数并要求确认", async () => {
    mockedImportBackup.mockResolvedValue(RESULT);
    render(<DataBackupModal visible onClose={vi.fn()} />);

    pickFile(JSON.stringify(makeBackup()));

    const confirm = await screen.findByRole("button", { name: "确认导入" });
    expect(screen.getByText(/2 个词、1 次练习、0 条对话/)).toBeTruthy();
    expect(mockedImportBackup).not.toHaveBeenCalled();

    fireEvent.click(confirm);

    await waitFor(() => expect(mockedImportBackup).toHaveBeenCalledTimes(1));
    expect(mockedImportBackup.mock.calls[0][0].format).toBe("english-practice-backup");
  });

  it("取消导入则不调用接口", async () => {
    render(<DataBackupModal visible onClose={vi.fn()} />);

    pickFile(JSON.stringify(makeBackup()));

    const cancel = await screen.findByRole("button", { name: "取消" });
    fireEvent.click(cancel);

    await waitFor(() => expect(mockedImportBackup).not.toHaveBeenCalled());
  });

  it("非本平台备份文件被拒绝", async () => {
    render(<DataBackupModal visible onClose={vi.fn()} />);

    pickFile(JSON.stringify({ format: "someone-elses", version: 1 }));

    await waitFor(() =>
      expect(screen.getByText(/不是本平台当前版本的备份文件/)).toBeTruthy()
    );
    expect(mockedImportBackup).not.toHaveBeenCalled();
  });

  it("损坏的 JSON 被拒绝", async () => {
    render(<DataBackupModal visible onClose={vi.fn()} />);

    pickFile("not json at all");

    await waitFor(() =>
      expect(screen.getByText(/文件不是有效的 JSON/)).toBeTruthy()
    );
    expect(mockedImportBackup).not.toHaveBeenCalled();
  });

  it("有词对不上时把跳过数量告诉用户", async () => {
    mockedImportBackup.mockResolvedValue({ ...RESULT, words_unmatched: 3 });
    render(<DataBackupModal visible onClose={vi.fn()} />);

    pickFile(JSON.stringify(makeBackup()));
    fireEvent.click(await screen.findByRole("button", { name: "确认导入" }));

    await waitFor(() =>
      expect(screen.getByText(/3 个词在当前词库中不存在，已跳过/)).toBeTruthy()
    );
  });

  it("导入失败时给出错误而不是静默", async () => {
    mockedImportBackup.mockRejectedValue(new Error("服务不可用"));
    render(<DataBackupModal visible onClose={vi.fn()} />);

    pickFile(JSON.stringify(makeBackup()));
    fireEvent.click(await screen.findByRole("button", { name: "确认导入" }));

    await waitFor(() => expect(screen.getByText("服务不可用")).toBeTruthy());
  });
});
