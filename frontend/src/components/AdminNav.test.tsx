import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AppLayout from "@/components/AppLayout";
import AdminGuard from "@/components/AdminGuard";
import { useAuthStore } from "@/stores/auth";
import type { UserInfo } from "@/types";

const ADMIN: UserInfo = {
  id: 1,
  username: "root",
  is_guest: false,
  role: "admin",
  status: "active",
  active_wordbook_id: null,
  consecutive_days: 0,
  created_at: "2026-10-20T00:00:00",
};

const PLAIN: UserInfo = { ...ADMIN, id: 2, username: "learner", role: "user" };

vi.mock("@/api/user", () => ({ fetchBackup: vi.fn(), importBackup: vi.fn() }));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<div data-testid="home" />} />
          <Route element={<AdminGuard />}>
            <Route path="admin/users" element={<div data-testid="admin-users" />} />
          </Route>
        </Route>
        <Route path="/login" element={<div data-testid="login" />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("管理入口按角色显示", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    // 侧栏与底部 Tab Bar 会让同一文案渲染两次，跨用例残留会直接让
    // queryByText 判错，所以这里必须显式清干净
    cleanup();
    document.querySelectorAll(".arco-modal, .arco-modal-mask, .arco-message").forEach((node) => {
      node.remove();
    });
    useAuthStore.setState({ user: null, ready: true });
  });

  it("管理员看得到全部管理入口", () => {
    useAuthStore.setState({ user: ADMIN, ready: true });
    renderAt("/");

    for (const label of ["用户管理", "词书管理", "知识库", "检索调试", "审计日志"]) {
      // 侧栏与底部 Tab Bar 各渲染一次，CSS 在断点上二选一
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    // 原有的用户功能入口不能被挤掉
    expect(screen.getAllByText("词书中心").length).toBeGreaterThan(0);
    expect(screen.getAllByText("AI 伴学").length).toBeGreaterThan(0);
  });

  it("普通用户看不到任何管理入口", () => {
    useAuthStore.setState({ user: PLAIN, ready: true });
    renderAt("/");

    expect(screen.queryByText("用户管理")).toBeNull();
    expect(screen.queryByText("词书管理")).toBeNull();
    expect(screen.queryByText("审计日志")).toBeNull();
    expect(screen.getAllByText("词书中心").length).toBeGreaterThan(0);
  });

  it("游客也拿不到管理入口", () => {
    useAuthStore.setState({ user: { ...PLAIN, is_guest: true }, ready: true });
    renderAt("/");
    expect(screen.queryByText("用户管理")).toBeNull();
  });
});

describe("移动端底部 Tab Bar", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("侧栏与底部 Tab 各渲染一次，靠 CSS 在断点上二选一", () => {
    useAuthStore.setState({ user: PLAIN, ready: true });
    renderAt("/");

    const sidebar = document.querySelector(".sidebar");
    const tabbar = document.querySelector(".tabbar");
    expect(sidebar).toBeTruthy();
    expect(tabbar).toBeTruthy();
    // 两者都挂载，由 global.css 的 768px 断点决定显示哪一个；
    // 用 JS 媒体查询会在首屏闪一下，所以刻意不做
    expect(sidebar?.querySelectorAll(".sidebar-item").length).toBeGreaterThan(0);
    expect(tabbar?.querySelectorAll(".tabbar-item").length).toBeGreaterThan(0);
  });

  it("底部 Tab 不超过五项，否则 44px 触控目标会被挤破", () => {
    useAuthStore.setState({ user: ADMIN, ready: true });
    renderAt("/");
    const tabs = document.querySelectorAll(".tabbar .tabbar-item");
    expect(tabs.length).toBeLessThanOrEqual(5);
  });

  it("管理员的底部 Tab 多一个管理入口，普通用户没有", () => {
    useAuthStore.setState({ user: ADMIN, ready: true });
    const admin = renderAt("/");
    const labels = Array.from(
      document.querySelectorAll(".tabbar .tabbar-item span")
    ).map((node) => node.textContent);
    expect(labels).toContain("管理");
    cleanup();

    useAuthStore.setState({ user: PLAIN, ready: true });
    renderAt("/");
    const plainLabels = Array.from(
      document.querySelectorAll(".tabbar .tabbar-item span")
    ).map((node) => node.textContent);
    expect(plainLabels).not.toContain("管理");
    expect(plainLabels).toEqual(["词书中心", "默写练习", "错题本", "AI 伴学"]);
    admin.unmount?.();
  });

  it("管理页在移动端有二级导航，用户页没有", () => {
    useAuthStore.setState({ user: ADMIN, ready: true });
    renderAt("/admin/users");
    expect(document.querySelector('[aria-label="管理子导航"]')).toBeTruthy();

    cleanup();
    renderAt("/");
    expect(document.querySelector('[aria-label="管理子导航"]')).toBeNull();
  });
});

describe("AdminGuard 守卫", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("普通用户手敲管理地址被送回首页", () => {
    useAuthStore.setState({ user: PLAIN, ready: true });
    renderAt("/admin/users");
    expect(screen.getByTestId("home")).toBeTruthy();
    expect(screen.queryByTestId("admin-users")).toBeNull();
  });

  it("管理员可以进入", () => {
    useAuthStore.setState({ user: ADMIN, ready: true });
    renderAt("/admin/users");
    expect(screen.getByTestId("admin-users")).toBeTruthy();
  });

  it("未登录被送到登录页", () => {
    useAuthStore.setState({ user: null, ready: true });
    renderAt("/admin/users");
    expect(screen.getByTestId("login")).toBeTruthy();
  });

  it("后端仍是最终防线：前端隐藏入口不算权限", async () => {
    // 这条用例只是把这个约定钉在测试里，避免将来有人只改前端就以为做了权限
    useAuthStore.setState({ user: PLAIN, ready: true });
    renderAt("/admin/users");
    await waitFor(() => expect(screen.queryByTestId("admin-users")).toBeNull());
  });
});
