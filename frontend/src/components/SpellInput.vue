<script setup>
import { computed, ref } from 'vue'

import GradeMark from './GradeMark.vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  status: {
    type: String,
    default: 'default',
    validator: (value) => ['default', 'correct', 'wrong'].includes(value),
  },
  hint: { type: Object, default: null },
  ariaLabel: { type: String, default: '默写输入' },
})

const emit = defineEmits(['update:modelValue', 'submit'])
const inputRef = ref(null)

const placeholder = computed(() => {
  if (!props.hint?.length) return '在此写下拼写'
  const safeLength = Math.min(Number(props.hint.length) || 0, 60)
  return Array.from({ length: safeLength }, () => '_').join(' ')
})

function handleInput(event) {
  emit('update:modelValue', event.target.value)
}

function handleKeydown(event) {
  if (event.key === 'Enter' && !event.isComposing) {
    event.preventDefault()
    emit('submit')
  }
}

function focus() {
  inputRef.value?.focus()
}

defineExpose({ focus })
</script>

<template>
  <div class="spell-input" :class="`spell-input--${status}`">
    <label class="sr-only" :for="`spell-${ariaLabel}`">{{ ariaLabel }}</label>
    <input
      :id="`spell-${ariaLabel}`"
      ref="inputRef"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :aria-invalid="status === 'wrong'"
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
      @input="handleInput"
      @keydown="handleKeydown"
    />
    <GradeMark v-if="status === 'correct'" class="spell-input__mark" type="correct" :size="30" />
    <span
      v-if="status === 'wrong'"
      class="spell-input__mark spell-input__mark--wrong"
      aria-hidden="true"
    >
      <GradeMark type="wrong" :size="30" />
    </span>
    <span class="spell-input__line" aria-hidden="true"></span>
  </div>
</template>

<style scoped>
.spell-input {
  position: relative;
  width: 100%;
  padding-right: 42px;
}

input {
  width: 100%;
  padding: 10px 2px 12px;
  border: 0;
  border-radius: 0;
  outline: 0;
  background: transparent;
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-lg);
  letter-spacing: 0.08em;
}

input::placeholder {
  color: var(--color-disabled);
  font-family: var(--font-family-body);
  font-size: var(--font-size-sm);
  letter-spacing: 0.12em;
}

.spell-input__line {
  position: absolute;
  right: 42px;
  bottom: 4px;
  left: 0;
  height: 2px;
  background: var(--color-primary);
  transition: background-color 160ms ease;
}

.spell-input--correct .spell-input__line {
  background: var(--color-success);
}

.spell-input--wrong .spell-input__line {
  background: var(--color-error);
  clip-path: polygon(
    0 45%,
    8% 20%,
    16% 70%,
    24% 20%,
    32% 70%,
    40% 20%,
    48% 70%,
    56% 20%,
    64% 70%,
    72% 20%,
    80% 70%,
    88% 20%,
    100% 45%,
    100% 100%,
    0 100%
  );
}

.spell-input__mark {
  position: absolute;
  right: 0;
  bottom: 13px;
}

.spell-input__mark--wrong {
  color: var(--color-error);
}

input:disabled {
  color: var(--color-disabled);
}
</style>
