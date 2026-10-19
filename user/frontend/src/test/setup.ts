/**
 * Vitest 全局前置：补齐 jsdom 缺失的浏览器 API。
 * 主题与音色设置在模块加载时就会读 matchMedia，缺了会在 import 阶段直接抛错。
 */
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList,
});
