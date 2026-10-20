import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ResponsiveList from "@/components/ResponsiveList";
import { MOBILE_QUERY } from "@/hooks/useMediaQuery";

interface Row {
  id: number;
  name: string;
}

const ROWS: Row[] = [
  { id: 1, name: "第一条" },
  { id: 2, name: "第二条" },
];

const COLUMNS = [{ title: "名称", dataIndex: "name" }];

function mockViewport(mobile: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: query === MOBILE_QUERY ? mobile : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
  );
}

describe("ResponsiveList", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("宽屏渲染表格", () => {
    mockViewport(false);
    render(
      <ResponsiveList
        rowKey="id"
        data={ROWS}
        columns={COLUMNS}
        renderCard={(row) => <div>{row.name}</div>}
      />
    );
    expect(screen.queryByTestId("record-cards")).toBeNull();
    expect(screen.getByText("第一条")).toBeTruthy();
  });

  it("窄屏渲染卡片而不是表格", () => {
    // 8 列表格在手机上只能横向滚动，扫一眼要拖好几次
    mockViewport(true);
    render(
      <ResponsiveList
        rowKey="id"
        data={ROWS}
        columns={COLUMNS}
        renderCard={(row) => <div>{row.name}</div>}
      />
    );
    expect(screen.getByTestId("record-cards")).toBeTruthy();
    expect(screen.getByText("第一条")).toBeTruthy();
    expect(screen.getByText("第二条")).toBeTruthy();
  });

  it("窄屏空数据给出可读的空态", () => {
    mockViewport(true);
    render(
      <ResponsiveList
        rowKey="id"
        data={[]}
        columns={COLUMNS}
        noDataElement="还没有词书"
        renderCard={(row) => <div>{row.name}</div>}
      />
    );
    expect(screen.getByText("还没有词书")).toBeTruthy();
  });

  it("断点常量与 global.css 保持一致", () => {
    // 改一处必须同步改另一处，否则 CSS 隐藏的和 JS 判断的会错位
    expect(MOBILE_QUERY).toBe("(max-width: 767px)");
  });
});
