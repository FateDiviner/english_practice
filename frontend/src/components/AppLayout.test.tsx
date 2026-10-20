import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import AppLayout from "@/components/AppLayout";
import { useAuthStore } from "@/stores/auth";
import type { UserInfo } from "@/types";

const GUEST: UserInfo = {
  id: 9,
  username: "guest_demo",
  is_guest: true,
  role: "user" as const,
  status: "active" as const,
  active_wordbook_id: null,
  consecutive_days: 0,
  created_at: "2026-10-16T00:00:00",
};

const MEMBER: UserInfo = {
  ...GUEST,
  id: 10,
  username: "member_demo",
  is_guest: false,
};

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<div data-testid="page" />} />
        </Route>
        <Route path="/login" element={<div data-testid="login-page" />} />
      </Routes>
    </MemoryRouter>
  );
}

// Arco 的 Modal.confirm 走独立 portal，组件卸载不会带走它，
// 不清理的话上一个用例的弹窗会留到下一个用例里
afterEach(() => {
  document
    .querySelectorAll(".arco-modal, .arco-modal-mask, .arco-message")
    .forEach((node) => node.remove());
});

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({ user: GUEST, ready: true });
});

describe("游客数据风险提示", () => {
  it("游客身份常驻提示条", () => {
    renderLayout();

    const banner = screen.getByTestId("guest-banner");
    expect(banner.textContent).toContain("清缓存或换设备会全部丢失");
  });

  it("点知道了后本次会话不再显示", () => {
    renderLayout();

    fireEvent.click(screen.getByRole("button", { name: "知道了" }));

    expect(screen.queryByTestId("guest-banner")).toBeNull();
  });

  it("立即注册保存跳转登录页", () => {
    renderLayout();

    fireEvent.click(screen.getByRole("button", { name: "立即注册保存" }));

    expect(screen.getByTestId("login-page")).toBeTruthy();
  });

  it("正式账号不显示提示条", () => {
    useAuthStore.setState({ user: MEMBER });
    renderLayout();

    expect(screen.queryByTestId("guest-banner")).toBeNull();
  });

  it("提示条不占用键盘流：页面内容仍正常渲染", () => {
    renderLayout();

    expect(screen.getByTestId("page")).toBeTruthy();
    // 导航项在侧栏与底部 Tab Bar 各渲染一次，靠 CSS 在断点上二选一
    expect(screen.getAllByText("词书中心").length).toBeGreaterThan(0);
  });
});

describe("学习数据备份入口", () => {
  it("顶栏提供备份入口并可打开弹窗", async () => {
    renderLayout();

    fireEvent.click(screen.getAllByRole("button", { name: "学习数据备份" })[0]);

    expect(await screen.findByText("学习数据备份")).toBeTruthy();
    expect(screen.getByText(/换设备、换账号或误清浏览器数据/)).toBeTruthy();
  });

  it("正式账号同样可以备份", () => {
    useAuthStore.setState({ user: MEMBER });
    renderLayout();

    expect(screen.getAllByRole("button", { name: "学习数据备份" }).length).toBeGreaterThan(0);
  });
});
