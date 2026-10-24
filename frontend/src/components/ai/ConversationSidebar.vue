<script setup>
import { ref, watch } from 'vue'

import { formatDate } from '../../utils/format'

const props = defineProps({
  conversations: { type: Array, default: () => [] },
  currentId: { type: Number, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'create', 'delete', 'close'])
const confirmingId = ref(null)

watch(
  () => props.currentId,
  () => {
    confirmingId.value = null
  },
)

function confirmDelete(conversationId) {
  if (confirmingId.value === conversationId) {
    confirmingId.value = null
    emit('delete', conversationId)
    return
  }
  confirmingId.value = conversationId
}
</script>

<template>
  <aside class="conversation-sidebar" :class="{ 'conversation-sidebar--open': open }">
    <header class="conversation-sidebar__header">
      <div>
        <p class="eyebrow">CONVERSATIONS</p>
        <h2>对话记录</h2>
      </div>
      <button class="primary-button" type="button" @click="emit('create')">新建</button>
    </header>

    <button
      class="conversation-sidebar__close secondary-button"
      type="button"
      @click="emit('close')"
    >
      收起记录
    </button>

    <div v-if="loading" class="skeleton-stack" aria-label="正在载入对话">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <p v-else-if="error" class="inline-notice inline-notice--error" role="alert">{{ error }}</p>

    <p v-else-if="!conversations.length" class="conversation-sidebar__empty">
      还没有对话。写下第一句，这里会替你保存。
    </p>

    <ul v-else class="conversation-list">
      <li
        v-for="conversation in conversations"
        :key="conversation.id"
        class="conversation-item"
        :class="{ 'conversation-item--active': conversation.id === currentId }"
      >
        <button
          class="conversation-item__select"
          type="button"
          @click="emit('select', conversation.id)"
        >
          <strong>{{ conversation.title || '新对话' }}</strong>
          <small>
            {{ conversation.message_count }} 条 · {{ formatDate(conversation.updated_at, true) }}
          </small>
        </button>
        <button
          class="conversation-item__delete"
          type="button"
          :aria-label="`删除 ${conversation.title || '新对话'}`"
          @click.stop="confirmDelete(conversation.id)"
        >
          {{ confirmingId === conversation.id ? '确认' : '×' }}
        </button>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.conversation-sidebar {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 20px;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.conversation-sidebar__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.conversation-sidebar__header h2 {
  margin: 0;
  font-size: var(--font-size-lg);
}

.conversation-sidebar__header .primary-button {
  padding: 8px 14px;
  font-size: var(--font-size-xs);
}

.conversation-sidebar__close {
  display: none;
}

.conversation-sidebar__empty {
  margin: 0;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
  line-height: 1.9;
}

.conversation-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.conversation-item {
  display: flex;
  align-items: stretch;
  gap: 4px;
  border: 1px solid transparent;
  border-left: 2px solid transparent;
}

.conversation-item--active {
  border-left-color: var(--color-accent);
  background: var(--color-background-muted);
}

.conversation-item__select {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
  padding: 10px 8px;
  border: 0;
  background: transparent;
  text-align: left;
}

.conversation-item__select strong {
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-family-title);
  font-size: var(--font-size-sm);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversation-item__select small {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.conversation-item__delete {
  flex: 0 0 auto;
  padding: 0 8px;
  border: 0;
  background: transparent;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.conversation-item__delete:hover {
  color: var(--color-danger);
}

@media (max-width: 860px) {
  .conversation-sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 30;
    display: none;
    width: min(320px, 86vw);
    box-shadow: 8px 0 24px color-mix(in srgb, var(--color-text), transparent 88%);
  }

  .conversation-sidebar--open {
    display: flex;
  }

  .conversation-sidebar__close {
    display: block;
  }
}
</style>
