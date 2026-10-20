import { useEffect, useState } from "react";

/**
 * 媒体查询钩子。
 *
 * 刻意用 JS 判断而不是让两端都渲染再靠 CSS 隐藏：表格这类重 DOM 的结构
 * 两端都渲染会让首屏明显变慢，而用 JS 判断的代价只是断点变化时闪一下。
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const list = window.matchMedia(query);
    const listener = (event: MediaQueryListEvent) => setMatches(event.matches);
    setMatches(list.matches);
    list.addEventListener("change", listener);
    return () => list.removeEventListener("change", listener);
  }, [query]);

  return matches;
}

/** 断点与 global.css 的 768px 保持一致，改一处必须同步改另一处 */
export const MOBILE_QUERY = "(max-width: 767px)";

export function useIsMobile(): boolean {
  return useMediaQuery(MOBILE_QUERY);
}
