import { create } from "zustand";
import type { UserInfo } from "@/types";
import {
  fetchMe,
  guestLogin,
  login as apiLogin,
  register as apiRegister,
} from "@/api/auth";
import { clearGuestId, clearToken, getToken } from "@/api/client";

interface AuthState {
  user: UserInfo | null;
  /** 是否已完成启动时的登录态恢复 */
  ready: boolean;
  pending: boolean;
  init: () => Promise<void>;
  login: (username: string, password: string) => Promise<UserInfo>;
  register: (username: string, password: string) => Promise<UserInfo>;
  guest: () => Promise<UserInfo>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  ready: false,
  pending: false,

  init: async () => {
    if (!getToken()) {
      set({ user: null, ready: true });
      return;
    }
    try {
      const user = await fetchMe();
      set({ user, ready: true });
    } catch {
      clearToken();
      clearGuestId();
      set({ user: null, ready: true });
    }
  },

  login: async (username, password) => {
    set({ pending: true });
    try {
      const data = await apiLogin(username, password);
      set({ user: data.user });
      return data.user;
    } finally {
      set({ pending: false });
    }
  },

  register: async (username, password) => {
    set({ pending: true });
    try {
      const data = await apiRegister(username, password);
      set({ user: data.user });
      return data.user;
    } finally {
      set({ pending: false });
    }
  },

  guest: async () => {
    set({ pending: true });
    try {
      const data = await guestLogin();
      set({ user: data.user });
      return data.user;
    } finally {
      set({ pending: false });
    }
  },

  logout: () => {
    clearToken();
    clearGuestId();
    set({ user: null });
  },
}));
