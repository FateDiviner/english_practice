import { render, screen, waitFor } from "@testing-library/react";
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
    // Arco 的 Modal / Message 走独立 portal，不清会泄漏到下一个用例
    document.querySelectorAll(".arco-modal, .arco-modal-mask, .arco-message").forEach((node) => {
      node.remove();
    });
  });

  it("管理员看得到全部管理入口", () => {
    useAuthStore.setState({ user: ADMIN, ready: true });
    renderAt("/");

    for (const label of ["用户管理", "词书管理", "知识库", "检索调试", "审计日志"]) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    // 原有的用户功能入口不能被挤掉
    expect(screen.getByText("词书中心")).toBeTruthy();
    expect(screen.getByText("AI 伴学")).toBeTruthy();
  });

  it("普通用户看不到任何管理入口", () => {
    useAuthStore.setState({ user: PLAIN, ready: true });
    renderAt("/");

    expect(screen.queryByText("用户管理")).toBeNull();
    expect(screen.queryByText("词书管理")).toBeNull();
    expect(screen.queryByText("审计日志")).toBeNull();
    expect(screen.getByText("词书中心")).toBeTruthy();
  });

  it("游客也拿不到管理入口", () => {
    useAuthStore.setState({ user: { ...PLAIN, is_guest: true }, ready: true });
    renderAt("/");
    expect(screen.queryByText("用户管理")).toBeNull();
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
