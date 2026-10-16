import { describe, expect, it } from "vitest";
import { PIN_THRESHOLD, isNearBottom } from "@/utils/scroll";

describe("isNearBottom 滚动贴底判定", () => {
  const box = (scrollHeight: number, scrollTop: number, clientHeight: number) => ({
    scrollHeight,
    scrollTop,
    clientHeight,
  });

  it("完全贴底时返回 true", () => {
    expect(isNearBottom(box(1000, 600, 400))).toBe(true);
  });

  it("距底部在阈值内仍视为贴底", () => {
    expect(isNearBottom(box(1000, 1000 - 400 - 64, 400))).toBe(true);
    expect(isNearBottom(box(1000, 1000 - 400 - 63, 400))).toBe(true);
  });

  it("距底部超过阈值则判定为已离开底部", () => {
    expect(isNearBottom(box(1000, 1000 - 400 - 65, 400))).toBe(false);
    expect(isNearBottom(box(1000, 0, 400))).toBe(false);
  });

  it("内容未超出可视区（无需滚动）时恒为贴底", () => {
    expect(isNearBottom(box(200, 0, 400))).toBe(true);
  });

  it("阈值可覆盖", () => {
    expect(isNearBottom(box(1000, 0, 400), 600)).toBe(true);
    expect(isNearBottom(box(1000, 0, 400), 100)).toBe(false);
  });

  it("默认阈值为 64px，与贴底跟随策略一致", () => {
    expect(PIN_THRESHOLD).toBe(64);
  });
});
