import { useEffect, useRef } from "react";

export interface HotkeyMap {
  /** Enter：提交拼写 */
  onSubmit?: (event: KeyboardEvent) => void;
  /** Space / Ctrl+P：重播发音（仅在输入框内且非空格输入时触发） */
  onSpeak?: (event: KeyboardEvent) => void;
  /** Tab：显示提示 */
  onHint?: (event: KeyboardEvent) => void;
  /** Esc / Ctrl+Enter：跳过并查看答案 */
  onSkip?: (event: KeyboardEvent) => void;
}

/**
 * 绑定默写核心键盘流契约。
 * 监听挂在 window 上，保证输入框失焦后快捷键依然可用（全键盘零阻塞红线）。
 */
export function usePracticeHotkeys(map: HotkeyMap, enabled: boolean): void {
  const ref = useRef(map);
  ref.current = map;

  useEffect(() => {
    if (!enabled) return;

    const handler = (event: KeyboardEvent) => {
      const current = ref.current;
      const target = event.target as HTMLElement | null;
      const inInput =
        target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;

      // Space：输入框内默认输入空格，改为重播发音并阻止默认
      if (event.code === "Space" && inInput) {
        event.preventDefault();
        current.onSpeak?.(event);
        return;
      }
      // Ctrl+P：浏览器打印快捷键，重映射为发音
      if (event.ctrlKey && event.key.toLowerCase() === "p") {
        event.preventDefault();
        current.onSpeak?.(event);
        return;
      }
      if (event.key === "Tab") {
        event.preventDefault();
        current.onHint?.(event);
        return;
      }
      if (event.key === "Enter" && event.ctrlKey) {
        event.preventDefault();
        current.onSkip?.(event);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        current.onSkip?.(event);
        return;
      }
      if (event.key === "Enter" && !event.shiftKey && !event.ctrlKey) {
        event.preventDefault();
        current.onSubmit?.(event);
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled]);
}
