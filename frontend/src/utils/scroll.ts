/**
 * 聊天视口滚动判定。
 * 抽成独立模块，便于脱离 React 直接单测，也避免页面组件混入额外具名导出。
 */

/** 贴底判定阈值（px）：距底部在此范围内才认为用户正在看最新内容 */
export const PIN_THRESHOLD = 64;

export interface ScrollBox {
  scrollHeight: number;
  scrollTop: number;
  clientHeight: number;
}

/** 是否贴着底部，用于决定流式输出是否跟随滚动 */
export function isNearBottom(node: ScrollBox, threshold: number = PIN_THRESHOLD): boolean {
  return node.scrollHeight - node.scrollTop - node.clientHeight <= threshold;
}
