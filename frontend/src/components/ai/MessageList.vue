<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
})

const emit = defineEmits(['suggest'])

const suggestions = [
  'abandon 是什么意思？',
  '过去完成时怎么用？',
  '把这句话翻译成英文：今天天气很好',
  '我想练一段餐厅点餐口语',
]

const intentLabels = {
  EXPLAIN_WORD: '单词讲解',
  GRAMMAR: '语法',
  ORAL_PRACTICE: '口语',
  TRANSLATION: '翻译',
  GENERAL: '通用',
}

const scroller = ref(null)
let stickToBottom = true

function handleScroll() {
  const element = scroller.value
  if (!element) return
  stickToBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 80
}

const scrollKey = computed(() => {
  const last = props.messages[props.messages.length - 1]
  return last ? `${props.messages.length}:${last.content.length}` : '0:0'
})

watch(
  () => props.messages.length,
  () => {
    stickToBottom = true
  },
)

watch(scrollKey, async () => {
  await nextTick()
  if (!stickToBottom || !scroller.value) return
  scroller.value.scrollTop = scroller.value.scrollHeight
})

function metaLabel(meta) {
  if (!meta) return ''
  const intent = intentLabels[meta.intent] || meta.intent || '对话'
  const confidence = Number.isFinite(meta.confidence) ? ` · ${meta.confidence}%` : ''
  const fallback = meta.fallback_used ? ' · 规则回退' : ''
  return `${intent}${confidence}${fallback}`
}
</script>

<template>
  <div ref="scroller" class="message-list" @scroll="handleScroll">
    <div v-if="!messages.length" class="message-empty">
      <p class="eyebrow">A QUIET DESK</p>
      <h2>从一句话开始</h2>
      <p class="message-empty__copy">
        可以问单词、问语法、练口语，或者让我帮你翻译。对话会自动保存。
      </p>
      <div class="message-empty__prompts">
        <button
          v-for="prompt in suggestions"
          :key="prompt"
          class="secondary-button"
          type="button"
          @click="emit('suggest', prompt)"
        >
          {{ prompt }}
        </button>
      </div>
    </div>

    <article
      v-for="(message, index) in messages"
      :key="index"
      class="message"
      :class="`message--${message.role}`"
    >
      <p v-if="message.role === 'assistant' && message.meta" class="message__meta">
        {{ metaLabel(message.meta) }}
      </p>
      <p class="message__body">
        {{ message.content }}<span v-if="message.streaming" class="message__caret"></span>
      </p>
      <p v-if="message.stopped" class="message__note">已停止生成</p>
      <p v-if="message.failed" class="message__note message__note--error">回复中断，请重试</p>
    </article>
  </div>
</template>

<style scoped>
.message-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
  padding: 28px 6px;
}

.message-empty {
  display: grid;
  flex: 1;
  align-content: center;
  justify-items: start;
  max-width: 560px;
  margin: 0 auto;
  padding: 40px 0;
}

.message-empty h2 {
  margin-bottom: 10px;
  font-size: var(--font-size-xl);
}

.message-empty__copy {
  margin-bottom: 26px;
  color: var(--color-disabled);
  font-size: var(--font-size-md-sm);
  line-height: 1.9;
}

.message-empty__prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.message-empty__prompts .secondary-button {
  font-size: var(--font-size-xs);
}

.message {
  max-width: min(720px, 86%);
  padding: 14px 18px;
  border: 1px solid var(--color-border);
}

.message--assistant {
  align-self: flex-start;
  background: var(--color-surface);
}

.message--user {
  align-self: flex-end;
  border-color: color-mix(in srgb, var(--color-primary), transparent 60%);
  background: var(--color-background-muted);
}

.message__meta {
  margin: 0 0 8px;
  color: var(--color-accent);
  font-size: var(--font-size-xs);
  letter-spacing: 0.04em;
}

.message__body {
  margin: 0;
  color: var(--color-text);
  font-size: var(--font-size-md-sm);
  line-height: 1.9;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.message__caret {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 3px;
  background: var(--color-accent);
  vertical-align: text-bottom;
  animation: caret-blink 1s steps(2, start) infinite;
}

.message__note {
  margin: 8px 0 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.message__note--error {
  color: var(--color-danger);
}

@keyframes caret-blink {
  to {
    visibility: hidden;
  }
}

@media (max-width: 720px) {
  .message {
    max-width: 100%;
  }
}
</style>
