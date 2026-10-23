<script setup>
import { onBeforeUnmount, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
  description: { type: String, default: '' },
})

const emit = defineEmits(['close'])

function close() {
  emit('close')
}

function handleKeydown(event) {
  if (event.key === 'Escape') close()
}

watch(
  () => props.open,
  (isOpen) => {
    document.body.style.overflow = isOpen ? 'hidden' : ''
    if (isOpen) window.addEventListener('keydown', handleKeydown)
    else window.removeEventListener('keydown', handleKeydown)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="open" class="drawer-root">
        <button class="drawer-scrim" type="button" aria-label="关闭面板" @click="close"></button>
        <aside class="drawer-panel" role="dialog" aria-modal="true" :aria-label="title">
          <header class="drawer-header">
            <div>
              <p class="eyebrow">OFFICE DESK</p>
              <h2>{{ title }}</h2>
              <p v-if="description">{{ description }}</p>
            </div>
            <button class="drawer-close" type="button" aria-label="关闭" @click="close">
              <span aria-hidden="true">×</span>
            </button>
          </header>
          <div class="drawer-body">
            <slot />
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-root {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  justify-content: flex-end;
}

.drawer-scrim {
  position: absolute;
  inset: 0;
  border: 0;
  background: color-mix(in srgb, var(--color-text), transparent 55%);
}

.drawer-panel {
  position: relative;
  z-index: 1;
  width: min(520px, 92vw);
  height: 100%;
  overflow-y: auto;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: -8px 0 28px color-mix(in srgb, var(--color-text), transparent 88%);
}

.drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 30px 30px 22px;
  border-bottom: 1px solid var(--color-border);
}

.drawer-header h2 {
  margin-bottom: 6px;
  font-size: var(--font-size-xl);
}

.drawer-header p:last-child {
  margin-bottom: 0;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.drawer-close {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: transparent;
  color: var(--color-primary);
  font-size: var(--font-size-lg);
  line-height: 1;
}

.drawer-close:hover {
  border-color: var(--color-border-hover);
  background: var(--color-background-muted);
}

.drawer-body {
  padding: 26px 30px 40px;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 180ms ease;
}

.drawer-enter-active .drawer-panel,
.drawer-leave-active .drawer-panel {
  transition: transform 220ms ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .drawer-panel,
.drawer-leave-to .drawer-panel {
  transform: translateX(100%);
}
</style>
