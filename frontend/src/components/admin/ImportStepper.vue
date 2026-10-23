<script setup>
defineProps({
  current: { type: Number, default: 1 },
  steps: { type: Array, default: () => [] },
})
</script>

<template>
  <ol class="stepper" aria-label="导入步骤">
    <li
      v-for="(step, index) in steps"
      :key="step"
      class="stepper__item"
      :class="{
        'stepper__item--active': current === index + 1,
        'stepper__item--done': current > index + 1,
      }"
    >
      <span>{{ String(index + 1).padStart(2, '0') }}</span>
      <strong>{{ step }}</strong>
    </li>
  </ol>
</template>

<style scoped>
.stepper {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  margin: 26px 0 0;
  padding: 0;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  list-style: none;
}

.stepper__item {
  display: grid;
  gap: 3px;
  padding: 12px 10px;
  border-right: 1px solid var(--color-border);
  color: var(--color-disabled);
}

.stepper__item:last-child {
  border-right: 0;
}

.stepper__item span {
  font-family: var(--font-family-title);
  font-size: 9px;
  letter-spacing: 0.08em;
}

.stepper__item strong {
  font-size: var(--font-size-xs);
  font-weight: 500;
  white-space: nowrap;
}

.stepper__item--active {
  background: var(--color-surface);
  color: var(--color-text);
}

.stepper__item--active span {
  color: var(--color-accent);
}

.stepper__item--done {
  color: var(--color-success);
}

.stepper__item--done span {
  color: var(--color-success);
}

@media (max-width: 720px) {
  .stepper {
    grid-template-columns: repeat(5, minmax(90px, 1fr));
    overflow-x: auto;
  }
}
</style>
