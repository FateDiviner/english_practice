<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  wordbooks: { type: Array, default: () => [] },
  isLoading: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  initialMode: { type: String, default: 'normal' },
  initialWordbookId: { type: [Number, String], default: '' },
})

const emit = defineEmits(['start'])
const countOptions = [10, 20, 50]
const form = reactive({
  mode: props.initialMode,
  wordbookId: props.initialWordbookId ? Number(props.initialWordbookId) : '',
  count: 10,
  strictMode: true,
})

watch(
  () => props.initialWordbookId,
  (value) => {
    if (value) form.wordbookId = Number(value)
  },
)

function start() {
  emit('start', {
    mode: form.mode,
    wordbookId: form.mode === 'normal' ? Number(form.wordbookId) : null,
    count: form.count,
    strictMode: form.strictMode,
  })
}
</script>

<template>
  <section class="setup surface">
    <div class="setup__heading">
      <p class="eyebrow">SET YOUR DESK</p>
      <h2>准备这一轮默写</h2>
      <p>先选练习范围，再决定题量与判分方式。</p>
    </div>

    <div class="mode-switch" role="group" aria-label="练习模式">
      <button
        type="button"
        :class="{ 'mode-switch__item--active': form.mode === 'normal' }"
        class="mode-switch__item"
        @click="form.mode = 'normal'"
      >
        按词书练习
      </button>
      <button
        type="button"
        :class="{ 'mode-switch__item--active': form.mode === 'wrong_only' }"
        class="mode-switch__item"
        @click="form.mode = 'wrong_only'"
      >
        错词专项
      </button>
    </div>

    <div v-if="form.mode === 'normal'" class="setup__field">
      <label class="field-label" for="practice-wordbook">选择词书</label>
      <select id="practice-wordbook" v-model="form.wordbookId" class="field-input">
        <option value="" disabled>请选择一本已发布词书</option>
        <option v-for="book in wordbooks" :key="book.id" :value="book.id">
          {{ book.name }} · {{ book.word_count }} 词
        </option>
      </select>
      <p v-if="!isLoading && !wordbooks.length" class="field-help">
        当前还没有已发布词书，可以先去词书架看看。
      </p>
    </div>
    <div v-else class="setup__wrong-note">
      <strong>只练习尚未解决的错词</strong>
      <span>答对两次后，这个词会从错词本中淡出。</span>
    </div>

    <fieldset class="setup__field setup__counts">
      <legend class="field-label">题量</legend>
      <button
        v-for="count in countOptions"
        :key="count"
        type="button"
        :class="{ 'count-option--active': form.count === count }"
        class="count-option"
        @click="form.count = count"
      >
        {{ count }} 题
      </button>
    </fieldset>

    <label class="strict-toggle">
      <input v-model="form.strictMode" type="checkbox" />
      <span>
        <strong>严格拼写</strong>
        <small>忽略大小写与首尾空格，英美拼写都算正确。</small>
      </span>
    </label>

    <p v-if="errorMessage" class="inline-notice inline-notice--error" role="alert">
      {{ errorMessage }}
    </p>

    <button
      class="primary-button setup__start"
      type="button"
      :disabled="isLoading || (form.mode === 'normal' && !form.wordbookId)"
      @click="start"
    >
      {{ isLoading ? '正在准备…' : '开始这一轮' }}
    </button>
  </section>
</template>

<style scoped>
.setup {
  max-width: 760px;
  margin: 30px auto 0;
  padding: 32px;
}

.setup__heading h2 {
  margin-bottom: 7px;
  font-size: var(--font-size-lg);
}

.setup__heading > p:last-child {
  margin-bottom: 24px;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin-bottom: 26px;
  border-bottom: 1px solid var(--color-border);
}

.mode-switch__item {
  padding: 11px 12px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.mode-switch__item--active {
  border-bottom-color: var(--color-accent);
  color: var(--color-text);
  font-weight: 600;
}

.setup__field {
  display: grid;
  gap: 8px;
  margin-bottom: 24px;
}

.setup__wrong-note {
  display: grid;
  gap: 3px;
  margin-bottom: 24px;
  padding: 13px 15px;
  border-left: 2px solid var(--color-accent);
  background: var(--color-background-muted);
  font-size: var(--font-size-sm);
}

.setup__wrong-note span {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.setup__counts {
  grid-template-columns: repeat(3, 1fr);
  border: 0;
  padding: 0;
}

.setup__counts legend {
  margin-bottom: 8px;
}

.count-option {
  min-height: 40px;
  border: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.count-option:hover {
  border-color: var(--color-border-hover);
}

.count-option--active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: var(--color-surface);
}

.strict-toggle {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 14px 0 20px;
  border-top: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
}

.strict-toggle input {
  margin-top: 4px;
  accent-color: var(--color-primary);
}

.strict-toggle strong,
.strict-toggle small {
  display: block;
}

.strict-toggle small {
  margin-top: 2px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.setup .inline-notice {
  margin-bottom: 18px;
}

.setup__start {
  width: 100%;
}

@media (max-width: 560px) {
  .setup {
    padding: 22px 18px;
  }

  .setup__counts {
    grid-template-columns: 1fr;
  }
}
</style>
