import { create } from "zustand";

export type ThemeMode = "light" | "dark";

interface AppState {
  /** 全局主题，跟随系统亦可手动覆盖 */
  theme: ThemeMode;
  /** 每组默写词数 */
  groupSize: number;
  /** 发音音色：英音 / 美音 */
  accent: "en-GB" | "en-US";
  /** 发音语速 */
  rate: number;
  setTheme: (theme: ThemeMode) => void;
  setGroupSize: (size: number) => void;
  setAccent: (accent: "en-GB" | "en-US") => void;
  setRate: (rate: number) => void;
}

const THEME_KEY = "ep_theme";
const GROUP_KEY = "ep_group_size";
const ACCENT_KEY = "ep_accent";

function readTheme(): ThemeMode {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function readGroupSize(): number {
  const raw = Number(localStorage.getItem(GROUP_KEY));
  return Number.isFinite(raw) && raw >= 5 && raw <= 50 ? raw : 10;
}

function readAccent(): "en-GB" | "en-US" {
  return localStorage.getItem(ACCENT_KEY) === "en-US" ? "en-US" : "en-GB";
}

export const useAppStore = create<AppState>((set) => ({
  theme: readTheme(),
  groupSize: readGroupSize(),
  accent: readAccent(),
  rate: 1,

  setTheme: (theme) => {
    localStorage.setItem(THEME_KEY, theme);
    set({ theme });
  },
  setGroupSize: (size) => {
    localStorage.setItem(GROUP_KEY, String(size));
    set({ groupSize: size });
  },
  setAccent: (accent) => {
    localStorage.setItem(ACCENT_KEY, accent);
    set({ accent });
  },
  setRate: (rate) => set({ rate }),
}));
