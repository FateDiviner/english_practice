<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  height: { type: Number, default: 190 },
})

const WIDTH = 620
const PADDING_X = 24
const PADDING_Y = 22
const MIN_POINT_GAP = 2

const chart = computed(() => {
  const values = props.items.map((item) => Number(item.answered) || 0)
  const maxValue = Math.max(1, ...values)
  const usableWidth = WIDTH - PADDING_X * 2
  const usableHeight = props.height - PADDING_Y * 2
  const step = values.length > 1 ? Math.max(MIN_POINT_GAP, usableWidth / (values.length - 1)) : 0
  const points = values.map((value, index) => ({
    x: PADDING_X + step * index,
    y: PADDING_Y + usableHeight - (value / maxValue) * usableHeight,
    value,
  }))
  return {
    points,
    polyline: points.map((point) => `${point.x},${point.y}`).join(' '),
    maxValue,
  }
})

const labels = computed(() => {
  if (!props.items.length) return []
  const indexes = [0, Math.floor((props.items.length - 1) / 2), props.items.length - 1]
  return [...new Set(indexes)].map((index) => ({ ...props.items[index], index }))
})

const gridLines = [0.25, 0.5, 0.75, 1]
</script>

<template>
  <div class="line-chart">
    <svg
      v-if="items.length"
      :viewBox="`0 0 ${WIDTH} ${height}`"
      role="img"
      aria-label="每日练习量趋势"
    >
      <line
        v-for="ratio in gridLines"
        :key="ratio"
        x1="24"
        x2="596"
        :y1="22 + (height - 44) * ratio"
        :y2="22 + (height - 44) * ratio"
        class="line-chart__grid"
      />
      <polyline :points="chart.polyline" class="line-chart__line" />
      <circle
        v-for="(point, index) in chart.points"
        :key="index"
        :cx="point.x"
        :cy="point.y"
        r="3"
        class="line-chart__point"
      >
        <title>{{ items[index].date }}：{{ point.value }} 题</title>
      </circle>
      <text
        v-for="label in labels"
        :key="`label-${label.index}`"
        :x="chart.points[label.index]?.x || 24"
        :y="height - 2"
        class="line-chart__label"
      >
        {{ label.date.slice(5) }}
      </text>
    </svg>
    <div v-else class="line-chart__empty">
      <span>第一条趋势线，等你写下今天的练习。</span>
    </div>
    <p v-if="items.length" class="line-chart__caption">单日峰值 {{ chart.maxValue }} 题</p>
  </div>
</template>

<style scoped>
.line-chart {
  position: relative;
  min-height: 190px;
}

.line-chart svg {
  display: block;
  width: 100%;
  overflow: visible;
}

.line-chart__grid {
  stroke: var(--color-border);
  stroke-dasharray: 3 5;
  stroke-width: 1;
}

.line-chart__line {
  fill: none;
  stroke: var(--color-primary);
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}

.line-chart__point {
  fill: var(--color-accent);
  stroke: var(--color-surface);
  stroke-width: 1.5;
}

.line-chart__label {
  fill: var(--color-disabled);
  font-family: var(--font-family-body);
  font-size: 11px;
  text-anchor: middle;
}

.line-chart__empty {
  display: grid;
  min-height: 190px;
  place-items: center;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.line-chart__caption {
  margin: 8px 0 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  text-align: right;
}
</style>
