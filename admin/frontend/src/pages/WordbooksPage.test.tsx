import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WordbooksPage from "@/pages/WordbooksPage";
import WordbookDetailPage from "@/pages/WordbookDetailPage";
import {
  exportWordbook,
  fetchWords,
  fetchWordbooks,
  importWordbooks,
  updateWordbook,
} from "@/api/words";
import { RequestError } from "@/api/client";
import type { WordbookAdminOut } from "@/types";

vi.mock("@/api/words", () => ({
  fetchWordbooks: vi.fn(),
  createWordbook: vi.fn(),
  updateWordbook: vi.fn(),
  fetchWords: vi.fn(),
  createWord: vi.fn(),
  updateWord: vi.fn(),
  setWordStatus: vi.fn(),
  deleteWord: vi.fn(),
  exportWordbook: vi.fn(),
  importWordbooks: vi.fn(),
}));

const mockedFetchWordbooks = vi.mocked(fetchWordbooks);
const mockedUpdateWordbook = vi.mocked(updateWordbook);
const mockedFetchWords = vi.mocked(fetchWords);
const mockedImport = vi.mocked(importWordbooks);
const mockedExport = vi.mocked(exportWordbook);

const BOOK: WordbookAdminOut = {
  id: 1,
  code: "cet4",
  title: "CET-4 核心高频词",
  description: "d",
  difficulty: "四级",
  status: "active",
  total_words: 147,
  archived_words: 3,
  active_users: 2,
};

// 标题必须与 BOOK 区分，否则两条记录同名会让 getByText 找到重复元素
const ARCHIVED_BOOK: WordbookAdminOut = {
  ...BOOK,
  id: 2,
  code: "old_book",
  title: "已归档的旧词书",
  total_words: 12,
  archived_words: 12,
  active_users: 0,
  status: "archived",
};

function renderWordbooks() {
  return render(
    <MemoryRouter initialEntries={["/wordbooks"]}>
      <Routes>
        <Route path="/wordbooks" element={<WordbooksPage />} />
        <Route path="/wordbooks/:bookId" element={<WordbookDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}


// Arco 的 Popconfirm / Modal 走独立 portal，组件卸载带不走，必须手动清理
afterEach(() => {
  // 显式清理：依赖隐式自动清理时，portal 与容器一旦残留就会让后续用例
  // 查到重复元素，报错看起来像组件渲染了两次
  cleanup();
  document
    .querySelectorAll(".arco-trigger, .arco-modal, .arco-message")
    .forEach((node) => node.remove());
});

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={["/wordbooks/1"]}>
      <Routes>
        <Route path="/wordbooks" element={<WordbooksPage />} />
        <Route path="/wordbooks/:bookId" element={<WordbookDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  mockedFetchWordbooks.mockResolvedValue([BOOK, ARCHIVED_BOOK]);
  mockedUpdateWordbook.mockResolvedValue({ ...BOOK, status: "archived" });
  mockedFetchWords.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 11,
        word: "abandon",
        phonetic: "/əˈbændən/",
        translation: "v. 放弃，遗弃",
        example_en: "He abandoned his car.",
        example_cn: "他把车丢下了。",
        sequence: 0,
        status: "active",
      },
    ],
  });
  mockedImport.mockResolvedValue({
    applied: true,
    books_created: 0,
    books_updated: 1,
    words_created: 5,
    words_updated: 3,
    words_total: 8,
    issues: [],
  });
  mockedExport.mockResolvedValue({ code: "cet4", words: [] });
});

describe("词书管理", () => {
  it("列表展示统计与下架状态", async () => {
    renderWordbooks();

    expect(await screen.findByText("CET-4 核心高频词")).toBeTruthy();
    expect(screen.getByText("147")).toBeTruthy();
    expect(screen.getByText("[已下架]")).toBeTruthy();
    expect(screen.getByText("已下架词")).toBeTruthy();
  });

  it("下架需要二次确认", async () => {
    renderWordbooks();

    await screen.findByText("CET-4 核心高频词");
    fireEvent.click(screen.getByRole("button", { name: "下架" }));

    expect(mockedUpdateWordbook).not.toHaveBeenCalled();
    expect(await screen.findByText(/下架该词书/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "确认" }));

    await waitFor(() =>
      expect(mockedUpdateWordbook).toHaveBeenCalledWith(1, { status: "archived" })
    );
  });

  it("已下架的词书提供上架入口", async () => {
    renderWordbooks();

    await screen.findByText("CET-4 核心高频词");
    expect(screen.getByRole("button", { name: "上架" })).toBeTruthy();
  });
});

describe("词条管理", () => {
  it("展示词条列表", async () => {
    renderDetail();
    await screen.findByText("abandon");

    expect(await screen.findByText("abandon")).toBeTruthy();
    // 顶部计数与分页摘要都会显示「共 N 条」，这里只要求它出现了
    expect((await screen.findAllByText(/共 1 条/)).length).toBeGreaterThan(0);
    expect(mockedFetchWords).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ limit: 20, offset: 0 })
    );
  });

  it("导入失败时逐条展示问题定位", async () => {
    mockedImport.mockRejectedValue(
      new RequestError("导入文件校验未通过", 422, {
        message: "导入文件校验未通过，共 1 处问题，未写入任何数据",
        issues: [
          {
            rule: "phonetic_brackets",
            field: "words[3].phonetic",
            message: "[abandon] 音标未用 / / 包裹: abandon",
          },
        ],
      })
    );
    renderDetail();
    await screen.findByText("abandon");
    await screen.findByText("abandon");

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(['{"code":"x"}'], "book.json", { type: "application/json" })] },
    });

    const issues = await screen.findByTestId("import-issues");
    expect(issues.textContent).toContain("共 1 处问题");
    expect(issues.textContent).toContain("words[3].phonetic");
    expect(issues.textContent).toContain("音标未用 / / 包裹");
  });

  it("导入成功给出词数统计", async () => {
    renderDetail();
    await screen.findByText("abandon");
    await screen.findByText("abandon");

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(['{"code":"cet4"}'], "book.json", { type: "application/json" })] },
    });

    await waitFor(() =>
      expect(screen.getByText(/导入完成：新增 5 词、更新 3 词/)).toBeTruthy()
    );
    expect(screen.queryByTestId("import-issues")).toBeNull();
  });

  it("损坏的 JSON 不会发请求", async () => {
    renderDetail();
    await screen.findByText("abandon");
    await screen.findByText("abandon");

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(["not json"], "bad.json", { type: "application/json" })] },
    });

    await waitFor(() =>
      expect(screen.getByText("文件不是有效的 JSON")).toBeTruthy()
    );
    expect(mockedImport).not.toHaveBeenCalled();
  });

  it("导出触发下载", async () => {
    const createObjectURL = vi.fn(() => "blob:test");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    renderDetail();
    await screen.findByText("abandon");
    await screen.findByText("abandon");

    fireEvent.click(screen.getByRole("button", { name: "导出 JSON" }));

    await waitFor(() => expect(mockedExport).toHaveBeenCalledWith(1));
    await waitFor(() => expect(click).toHaveBeenCalled());
  });
});
