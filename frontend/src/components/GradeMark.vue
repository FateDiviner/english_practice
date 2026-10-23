<script setup>
defineProps({
  type: {
    type: String,
    default: 'correct',
    validator: (value) => ['correct', 'wrong'].includes(value),
  },
  size: { type: Number, default: 34 },
})
</script>

<template>
  <svg
    class="grade-mark"
    :class="`grade-mark--${type}`"
    :width="size"
    :height="size"
    viewBox="0 0 40 40"
    fill="none"
    aria-hidden="true"
  >
    <template v-if="type === 'correct'">
      <path d="M7 21.5C11 22.5 13.5 25 17.2 31C20.5 22.5 25.8 14.2 34 8.3" />
      <path d="M8.5 20.2C12.3 22.3 14.6 24.5 17.1 28.8" opacity="0.45" />
    </template>
    <template v-else>
      <path
        d="M20.3 5.8C10.9 4.8 4.7 10.3 5.4 19.7C6 28.7 11.9 34.8 21.2 34.1C30.3 33.4 35.4 27.4 34.5 18.1C33.8 10.7 29.6 6.4 20.3 5.8Z"
      />
      <path d="M13.5 25.5C17.5 17.7 22.8 13.4 28.7 11.1" opacity="0.8" />
      <path d="M15.4 14.2C18.1 20.6 22.6 25 28.4 27.7" opacity="0.55" />
    </template>
  </svg>
</template>

<style scoped>
.grade-mark path {
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.4;
}

.grade-mark--correct {
  color: var(--color-success);
}

.grade-mark--wrong {
  color: var(--color-error);
}
</style>
