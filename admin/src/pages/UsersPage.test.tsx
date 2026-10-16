import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import UsersPage from "@/pages/UsersPage";
import type { AdminUserOut } from "@/types";
import { deleteUser, fetchUsers, updateUser } from "@/api/users";

vi.mock("@/api/users", () => ({
  fetchUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deleteUser: vi.fn(),
}));

const mockedFetchUsers = vi.mocked(fetchUsers);
const mockedUpdateUser = vi.mocked(updateUser);
const mockedDeleteUser = vi.mocked(deleteUser);

const SELF: AdminUserOut = { id: 1, username: "root", is_guest: false, role: "admin", status: "active",
  active_wordbook_id: null, consecutive_days: 0, created_at: "2026-10-16T00:00:00",
  last_practiced_at: null, practice_count: 0 };
const OTHER: AdminUserOut = { ...SELF, id: 2, username: "bob", role: "user", status: "banned" };

beforeEach(() => {
  mockedFetchUsers.mockResolvedValue({ total: 2, items: [SELF, OTHER] });
  mockedUpdateUser.mockResolvedValue({ id: 2, role: "user", status: "active" });
  mockedDeleteUser.mockResolvedValue({ affected_rows: 3 });
});

describe("用户管理", () => {
  it("渲染用户列表", async () => {
    render(<UsersPage currentUser={SELF} />);

    expect(await screen.findByText("bob")).toBeTruthy();
    expect(screen.getByText("[已封禁]")).toBeTruthy();
    expect(screen.getByText("管理员")).toBeTruthy();
  });

  it("不能对自己的行执行操作", async () => {
    render(<UsersPage currentUser={SELF} />);

    await screen.findByText("bob");
    const selfRow = screen.getByText("root").closest("tr") as HTMLElement;
    const buttons = selfRow.querySelectorAll("button");

    Array.from(buttons).forEach((button) => {
      expect((button as HTMLButtonElement).disabled).toBe(true);
    });
  });

  it("封禁他人需要二次确认", async () => {
    render(<UsersPage currentUser={SELF} />);

    const bobRow = (await screen.findByText("bob")).closest("tr") as HTMLElement;
    const banButton = Array.from(bobRow.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("启用")
    ) as HTMLButtonElement;

    fireEvent.click(banButton);

    // 未确认前不得调用接口
    expect(mockedUpdateUser).not.toHaveBeenCalled();
    expect(await screen.findByText("解除封禁？")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "确认" }));

    await waitFor(() => expect(mockedUpdateUser).toHaveBeenCalledWith(2, { status: "active" }));
  });

  it("删除同样需要二次确认", async () => {
    render(<UsersPage currentUser={SELF} />);

    const bobRow = (await screen.findByText("bob")).closest("tr") as HTMLElement;
    const deleteButton = Array.from(bobRow.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("删除")
    ) as HTMLButtonElement;

    fireEvent.click(deleteButton);
    expect(mockedDeleteUser).not.toHaveBeenCalled();

    fireEvent.click(await screen.findByRole("button", { name: "确认删除" }));

    await waitFor(() => expect(mockedDeleteUser).toHaveBeenCalledWith(2));
  });
});
