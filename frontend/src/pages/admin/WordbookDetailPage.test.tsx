import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WordbookDetailPage from "@/pages/admin/WordbookDetailPage";
import {
  createRelation,
  createWord,
  deleteRelation,
  deleteWord,
  exportWordbook,
  fetchAdminWords,
  fetchRelations,
  importWordsIntoBook,
  setWordStatus,
  updateWord,
} from "@/api/admin";
import type { AdminWord, ValidationIssue } from "@/types";

vi.mock("@/api/admin", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/admin")>();
  return {
    ...actual,
    fetchAdminWords: vi.fn(),
    createWord: vi.fn(),
    updateWord: vi.fn(),
    setWordStatus: vi.fn(),
    deleteWord: vi.fn(),
    importWordsIntoBook: vi.fn(),
    exportWordbook: vi.fn(),
    fetchRelations: vi.fn(),
    createRelation: vi.fn(),
    updateRelation: vi.fn(),
    deleteRelation: vi.fn(),
  };
});

const mockedFetchAdminWords = vi.mocked(fetchAdminWords);
const mockedImportWordsIntoBook = vi.mocked(importWordsIntoBook);
const mockedFetchRelations = vi.mocked(fetchRelations);
const mockedCreateRelation = vi.mocked(createRelation);
const mockedDeleteRelation = vi.mocked(deleteRelation);
const mockedCreateWord = vi.mocked(createWord);
const mockedUpdateWord = vi.mocked(updateWord);
const mockedSetWordStatus = vi.mocked(setWordStatus);
const mockedDeleteWord = vi.mocked(deleteWord);
const mockedExportWordbook = vi.mocked(exportWordbook);

const WORD: AdminWord = {
  id: 10,
  word: "abandon",
  phonetic: "/əˈbændən/",
  translation: "v. 放弃，遗弃",
  example_en: "They had to abandon the plan.",
  example_cn: "他们不得不放弃这个计划。",
  status: "active",
  sequence: 0,
};

const WORD_PAGE = {
  items: [WORD],
  total: 1,
  limit: 20,
  offset: 0,
};

const IMPORT_OK = {
  applied: true,
  books_created: 0,
  books_updated: 0,
  words_created: 2,
  words_updated: 0,
  words_total: 2,
  issues: [],
};

const ISSUES: ValidationIssue[] = [
  {
    rule: "phonetic_brackets",
    field: "words[1].phonetic",
    message: "[ephemeral] 音标未用 / / 包裹: oops",
  },
];

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/admin/wordbooks/1"]}>
      <Routes>
        <Route path="/admin/wordbooks/:bookId" element={<WordbookDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

function selectImportFile(content: string) {
  const file = new File([content], "words.json", { type: "application/json" });
  // Arco Upload 渲染全局唯一的 file input；页面只有一个批量导入入口
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  expect(input).not.toBeNull();
  fireEvent.change(input, { target: { files: [file] } });
}

describe("WordbookDetailPage 批量导入", () => {
  beforeEach(() => {
    mockedFetchAdminWords.mockResolvedValue(WORD_PAGE);
    mockedFetchRelations.mockResolvedValue([]);
    mockedCreateRelation.mockResolvedValue({} as never);
    mockedDeleteRelation.mockResolvedValue();
    mockedCreateWord.mockResolvedValue(WORD);
    mockedUpdateWord.mockResolvedValue(WORD);
    mockedSetWordStatus.mockResolvedValue(WORD);
    mockedDeleteWord.mockResolvedValue({});
    mockedExportWordbook.mockResolvedValue({ code: "cet4", words: [] });
  });

  it("导入词条数组调用新接口并刷新列表", async () => {
    renderPage();
    await screen.findByText("abandon");

    mockedImportWordsIntoBook.mockResolvedValue(IMPORT_OK);
    const payload = [
      {
        word: "abandon",
        phonetic: "/əˈbændən/",
        translation: "v. 放弃，遗弃",
        example_en: "They had to abandon the plan.",
        example_cn: "他们不得不放弃这个计划。",
      },
      {
        word: "ephemeral",
        phonetic: "/ɪˈfem(ə)rəl/",
        translation: "adj. 短暂的",
        example_en: "Fame is ephemeral.",
        example_cn: "名声是短暂的。",
      },
    ];
    selectImportFile(JSON.stringify(payload));

    await waitFor(() => {
      expect(mockedImportWordsIntoBook).toHaveBeenCalledWith(1, payload);
    });
    expect(await screen.findByText(/导入完成：新增词条 2 条/)).toBeTruthy();
    expect(mockedFetchAdminWords).toHaveBeenCalled();
  });

  it("导入单条对象也按数组处理", async () => {
    renderPage();
    await screen.findByText("abandon");

    mockedImportWordsIntoBook.mockResolvedValue(IMPORT_OK);
    const single = {
      word: "ephemeral",
      phonetic: "/ɪˈfem(ə)rəl/",
      translation: "adj. 短暂的",
      example_en: "Fame is ephemeral.",
      example_cn: "名声是短暂的。",
    };
    selectImportFile(JSON.stringify(single));

    await waitFor(() => {
      expect(mockedImportWordsIntoBook).toHaveBeenCalledWith(1, [single]);
    });
  });

  it("422 校验失败时结构化展示 issues", async () => {
    renderPage();
    await screen.findByText("abandon");

    const error = {
      detail: {
        message: "导入文件校验未通过，共 1 处问题，未写入任何数据",
        issues: ISSUES,
      },
    };
    mockedImportWordsIntoBook.mockRejectedValue(error);

    const bad = [
      {
        word: "abandon",
        phonetic: "/əˈbændən/",
        translation: "v. 放弃，遗弃",
        example_en: "They had to abandon the plan.",
        example_cn: "他们不得不放弃这个计划。",
      },
      {
        word: "ephemeral",
        phonetic: "oops",
        translation: "adj. 短暂的",
        example_en: "Fame is ephemeral.",
        example_cn: "名声是短暂的。",
      },
    ];
    selectImportFile(JSON.stringify(bad));

    const panel = await screen.findByTestId("import-issues");
    expect(panel.textContent).toContain("导入文件校验未通过");
    expect(panel.textContent).toContain("words[1].phonetic");
    expect(panel.textContent).toContain("[ephemeral] 音标未用 / / 包裹: oops");
    // 校验失败不刷新列表
    expect(mockedFetchAdminWords).toHaveBeenCalledTimes(1);
  });
});
