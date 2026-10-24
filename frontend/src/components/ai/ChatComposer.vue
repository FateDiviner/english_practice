<script setup>
import { ref } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  streaming: { type: Boolean, default: false },
  scene: { type: String, default: '' },
})

const emit = defineEmits(['send', 'stop', 'update:scene'])

const MAX_LENGTH = 2000
const draft = ref('')

const scenes = [
  { value: '', label: '自由对话' },
  { value: 'restaurant', label: '餐厅点餐' },
  { value: 'interview', label: '面试' },
  { value: 'travel', label: '旅行' },
  { value: 'campus', label: '校园' },
]

function submit() {
  const text = draft.value.trim()
  if (!text || props.disabled || props.streaming) return
  emit('send', text)
  draft.value = ''
}

function handleKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <form class="composer" @submit.prevent="submit">
    <div class="composer__toolbar">
      <label class="composer__scene">
        <span>场景</span>
        <select
          class="field-input"
          :value="scene"
          @change="emit('update:scene', $event.target.value)"
        >
          <option v-for="item in scenes" :key="item.value" :value="item.value">
            {{ item.label }}
          </option>
        </select>
      </label>
      <span class="composer__count">{{ draft.length }} / {{ MAX_LENGTH }}</span>
    </div>

    <textarea
      v-model="draft"
      class="composer__input"
      :maxlength="MAX_LENGTH"
      :disabled="disabled"
      rows="3"
      placeholder="用英文或中文提问，例如：abandon 是什么意思？"
      @keydown="handleKeydown"
    ></textarea>

    <div class="composer__actions">
      <p>Enter 发送，Shift + Enter 换行</p>
      <button v-if="streaming" class="secondary-button" type="button" @click="emit('stop')">
        停止生成
      </button>
      <button v-else class="primary-button" type="submit" :disabled="disabled || !draft.trim()">
        发送
      </button>
    </div>
  </form>
</template>

<style scoped>
.composer {
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

.composer__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.composer__scene {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.composer__scene .field-input {
  width: 132px;
  padding: 6px 8px;
  font-size: var(--font-size-xs);
}

.composer__count {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.composer__input {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-family-body);
  font-size: var(--font-size-md-sm);
  line-height: 1.8;
  resize: vertical;
}

.composer__input:focus {
  border-color: var(--color-primary);
  outline: none;
}

.composer__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 10px;
}

.composer__actions p {
  margin: 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

@media (max-width: 620px) {
  .composer__actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
