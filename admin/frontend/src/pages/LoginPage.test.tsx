import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginPage from "@/pages/LoginPage";
import { login } from "@/api/auth";
import { getToken } from "@/api/client";
import type { AdminUserOut } from "@/types";

vi.mock("@/api/auth", () => ({
  login: vi.fn(),
  fetchMe: vi.fn(),
}));

const mockedLogin = vi.mocked(login);

const SELF: AdminUserOut = {
  id: 1,
  username: "root",
  is_guest: false,
  role: "admin",
  status: "active",
  active_wordbook_id: null,
  consecutive_days: 0,
  created_at: "2026-10-16T00:00:00",
  last_practiced_at: null,
  practice_count: 0,
};

beforeEach(() => {
  localStorage.clear();
});

describe("管理端登录", () => {
  it("管理员登录成功后保存令牌并回调", async () => {
    const onLoggedIn = vi.fn();
    mockedLogin.mockResolvedValue({
      access_token: "tok",
      token_type: "bearer",
      user: { ...SELF, username: "root", role: "admin" },
    });
    render(<LoginPage onLoggedIn={onLoggedIn} />);

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "root" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret123" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => expect(onLoggedIn).toHaveBeenCalled());
    expect(getToken()).toBe("tok");
  });

  it("普通管理员以外的账号不会进入", async () => {
    const onLoggedIn = vi.fn();
    mockedLogin.mockResolvedValue({
      access_token: "tok",
      token_type: "bearer",
      user: { ...SELF, id: 2, username: "bob", role: "user" },
    });
    render(<LoginPage onLoggedIn={onLoggedIn} />);

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "bob" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret123" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() =>
      expect(screen.getByText("该账号不是管理员")).toBeTruthy()
    );
    expect(onLoggedIn).not.toHaveBeenCalled();
    expect(getToken()).toBeNull();
  });

  it("登录失败时提示错误", async () => {
    const onLoggedIn = vi.fn();
    mockedLogin.mockRejectedValue(new Error("用户名或密码错误"));
    render(<LoginPage onLoggedIn={onLoggedIn} />);

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "x" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "y" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() =>
      expect(screen.getByText("用户名或密码错误")).toBeTruthy()
    );
    expect(onLoggedIn).not.toHaveBeenCalled();
  });
});
