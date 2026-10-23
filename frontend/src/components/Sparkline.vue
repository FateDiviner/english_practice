<script setup>
import { computed } from 'vue'

const props = defineProps({
  values: { type: Array, default: () => [] },
  width: { type: Number, default: 96 },
  height: { type: Number, default: 28 },
})

const points = computed(() => {
  const numbers = props.values.map((value) => Number(value) || 0)
  if (numbers.length < 2) return ''
  const maximum = Math.max(1, ...numbers)
  const step = props.width / (numbers.length - 1)
  return numbers
    .map((value, index) => {
      const x = step * index
      const y = props.height - 3 - (value / maximum) * (props.height - 6)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})
</script>

<template>
  <svg
    class="sparkline"
    :width="width"
    :height="height"
    :viewBox="`0 0 ${width} ${height}`"
    fill="none"
    aria-hidden="true"
  >
    <polyline v-if="points" :points="points" />
    <line v-else x1="0" :y1="height - 3" :x2="width" :y2="height - 3" />
  </svg>
</template>

<style scoped>
.sparkline {
  display: block;
  overflow: visible;
}

.sparkline polyline,
.sparkline line {
  fill: none;
  stroke: var(--color-accent);
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.2;
  vector-effect: non-scaling-stroke;
}
</style>
