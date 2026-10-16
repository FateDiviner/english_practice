import { Card, Empty, Space, Statistic, Tag, Tooltip, Typography } from "@arco-design/web-react";
import type { DailyStat, RecentSession, StatsOverview } from "@/types";

/** 柱状图几何：静态尺寸，绝不使用 height 插值动画（AGENTS.md 动效守则） */
const BAR_MAX_WIDTH = 24;
const BAR_MAX_HEIGHT = 72;
const CHART_GAP = 2;
const RECENT_LIMIT = 3;

const MODE_LABEL: Record<string, string> = {
  normal: "默写",
  wrong_book: "错题",
  review: "复习",
};

/** 近 N 天练习量柱状图：单序列，颜色取自设计 Token，深浅色自动适配 */
function TrendChart({ daily }: { daily: DailyStat[] }) {
  const peak = Math.max(...daily.map((day) => day.words), 0);
  const total = daily.reduce((sum, day) => sum + day.words, 0);
  const today = daily[daily.length - 1]?.date ?? "";

  if (peak === 0) {
    return (
      <Empty
        description="完成一次练习后，这里会显示近 7 天趋势"
        style={{ marginTop: 8 }}
      />
    );
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: CHART_GAP, height: BAR_MAX_HEIGHT }}>
        {daily.map((day) => {
          // words 为 0 时不画柱子，避免"零高度"柱与基准线粘连
          const height =
            day.words > 0 ? Math.max(6, Math.round((day.words / peak) * BAR_MAX_HEIGHT)) : 0;
          return (
            <Tooltip key={day.date} content={`${day.date}：练习 ${day.words} 词 · 正确率 ${day.accuracy}%`}>
              <div
                role="img"
                aria-label={`${day.date} 练习 ${day.words} 词，正确率 ${day.accuracy}%`}
                style={{
                  flex: 1,
                  alignSelf: "flex-end",
                  maxWidth: BAR_MAX_WIDTH,
                  height,
                  background: "var(--color-primary)",
                  borderTopLeftRadius: 4,
                  borderTopRightRadius: 4,
                }}
              />
            </Tooltip>
          );
        })}
      </div>
      <div style={{ height: 1, background: "var(--border-color)" }} />
      <div style={{ display: "flex", gap: CHART_GAP, marginTop: 6 }}>
        {daily.map((day) => (
          <Typography.Text
            key={day.date}
            style={{
              flex: 1,
              maxWidth: BAR_MAX_WIDTH,
              textAlign: "center",
              fontSize: 11,
              color: "var(--text-3)",
              whiteSpace: "nowrap",
            }}
          >
            {day.date === today ? "今天" : day.date.slice(5).replace("-", "/")}
          </Typography.Text>
        ))}
      </div>
      <Typography.Text type="secondary" style={{ display: "block", marginTop: 8, fontSize: 12 }}>
        近 7 天共 {total} 词，峰值 {peak} 词
      </Typography.Text>
    </div>
  );
}

function RecentList({ recent }: { recent: RecentSession[] }) {
  const items = recent.slice(0, RECENT_LIMIT);
  if (items.length === 0) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        最近练习
      </Typography.Text>
      <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
        {items.map((item, index) => (
          <div
            key={`${item.date}-${index}`}
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
              alignItems: "baseline",
              justifyContent: "space-between",
              padding: "6px 10px",
              borderRadius: "var(--border-radius-md)",
              background: "var(--bg-subtle)",
            }}
          >
            <Space size={8} align="baseline" wrap>
              <Typography.Text style={{ fontSize: 13 }}>{item.wordbook_title}</Typography.Text>
              <Tag size="small" color={item.mode === "review" ? "green" : "arcoblue"}>
                {MODE_LABEL[item.mode] ?? item.mode}
              </Tag>
            </Space>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {item.total} 词 · 正确率 {item.accuracy}%
            </Typography.Text>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 学习看板：连续打卡、今日进度、近 7 天趋势与最近练习 */
export default function LearningBoard({ overview }: { overview: StatsOverview }) {
  const { today, totals, consecutive_days: streak, checked_in_today: checkedIn } = overview;

  return (
    <Card
      className="card"
      title="学习看板"
      style={{ marginBottom: 20 }}
      bodyStyle={{ paddingTop: 12 }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 24,
        }}
      >
        <div>
          <Space size={12} align="baseline" wrap>
            <Statistic
              value={streak}
              suffix="天"
              title="连续打卡"
              styleValue={{ fontSize: 40, fontWeight: 600, color: "var(--text-1)" }}
            />
            <Tag size="small" color={checkedIn ? "green" : "gray"}>
              {checkedIn ? "[今天已打卡]" : "[今天还没打卡]"}
            </Tag>
          </Space>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 20,
              marginTop: 16,
            }}
          >
            <Statistic
              value={today.words}
              suffix="词"
              title="今天练习"
              styleValue={{ fontSize: 22, fontWeight: 600, color: "var(--text-1)" }}
            />
            <Statistic
              value={today.accuracy}
              precision={1}
              suffix="%"
              title="今天正确率"
              styleValue={{ fontSize: 22, fontWeight: 600, color: "var(--text-1)" }}
            />
            <Statistic
              value={totals.mastered}
              suffix={` / ${totals.practiced}`}
              title="已掌握"
              styleValue={{ fontSize: 22, fontWeight: 600, color: "var(--text-1)" }}
            />
          </div>

          <Typography.Text
            type="secondary"
            style={{ display: "block", marginTop: 12, fontSize: 12 }}
          >
            学习中 {totals.learning} · 错题 {totals.wrong} · 统计口径为 UTC 自然日
          </Typography.Text>
        </div>

        <div>
          <Typography.Text style={{ fontSize: 13, color: "var(--text-2)" }}>
            近 7 天练习量
          </Typography.Text>
          <div style={{ marginTop: 10 }}>
            <TrendChart daily={overview.daily} />
          </div>
          <RecentList recent={overview.recent} />
        </div>
      </div>
    </Card>
  );
}
