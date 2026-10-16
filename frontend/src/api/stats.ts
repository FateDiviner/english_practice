import { http } from "./client";
import type { StatsOverview } from "@/types";

/** 拉取学习看板概览（连续打卡、今日进度、近 N 天趋势与累计掌握） */
export async function fetchOverview(days = 7): Promise<StatsOverview> {
  const { data } = await http.get<StatsOverview>("/api/stats/overview", {
    params: { days },
  });
  return data;
}
