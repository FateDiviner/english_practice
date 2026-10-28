<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  createAiSession,
  deleteAiSession,
  getAiSession,
  listAiSessions,
  streamAgentChat,
} from '../../api/ai'
import ChatComposer from '../../components/ai/ChatComposer.vue'
import ConversationSidebar from '../../components/ai/ConversationSidebar.vue'
import MessageList from '../../components/ai/MessageList.vue'
import { getErrorMessage } from '../../utils/errors'

const conversations = ref([])
const currentId = ref(null)
const messages = ref([])
const isLoadingSessions = ref(true)
const isLoadingMessages = ref(false)
const isStreaming = ref(false)
const sessionError = ref('')
const errorMessage = ref('')
const scene = ref('')
const sidebarOpen = ref(false)
let controller = null

const currentTitle = computed(
  () => conversations.value.find((item) => item.id === currentId.value)?.title || '新对话',
)

async function loadSessions() {
  isLoadingSessions.value = true
  sessionError.value = ''
  try {
    const result = await listAiSessions({ page: 1, pageSize: 50 })
    conversations.value = result.items || []
    const target = conversations.value[0]?.id ?? null
    if (target !== currentId.value) await selectConversation(target)
  } catch (error) {
    sessionError.value = getErrorMessage(error, '对话列表暂时无法读取。')
  } finally {
    isLoadingSessions.value = false
  }
}

async function selectConversation(conversationId) {
  if (isStreaming.value) stopStreaming()
  currentId.value = conversationId
  errorMessage.value = ''
  sidebarOpen.value = false

  if (conversationId == null) {
    messages.value = []
    scene.value = ''
    return
  }

  isLoadingMessages.value = true
  try {
    const detail = await getAiSession(conversationId)
    if (currentId.value !== conversationId) return
    messages.value = (detail.messages || []).map((item) => ({
      role: item.role,
      content: item.content,
    }))
    scene.value = detail.scene || ''
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '这段对话暂时打不开。')
  } finally {
    isLoadingMessages.value = false
  }
}

async function startNewConversation() {
  if (isStreaming.value) return
  errorMessage.value = ''
  try {
    const created = await createAiSession({ scene: scene.value || null })
    conversations.value = [created, ...conversations.value]
    currentId.value = created.id
    messages.value = []
    sidebarOpen.value = false
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '新对话没有创建成功。')
  }
}

async function refreshConversations() {
  try {
    const result = await listAiSessions({ page: 1, pageSize: 50 })
    conversations.value = result.items || []
  } catch {
    // 列表刷新失败不影响当前对话。
  }
}

async function sendMessage(text) {
  if (isStreaming.value) return
  if (currentId.value == null) {
    await startNewConversation()
    if (currentId.value == null) return
  }

  const conversationId = currentId.value
  errorMessage.value = ''
  messages.value.push({ role: 'user', content: text })
  const reply = reactive({ role: 'assistant', content: '', meta: null, streaming: true })
  messages.value.push(reply)

  isStreaming.value = true
  controller = new AbortController()
  try {
    await streamAgentChat({
      message: text,
      scene: scene.value || null,
      conversationId,
      signal: controller.signal,
      onMeta(data) {
        reply.meta = data
      },
      onDelta(data) {
        reply.content += data?.content || ''
      },
      onDone() {
        reply.streaming = false
      },
    })
    reply.streaming = false
  } catch (error) {
    reply.streaming = false
    if (error?.name === 'AbortError') {
      reply.stopped = true
    } else {
      reply.failed = true
      errorMessage.value = getErrorMessage(error, '对话没有完成，请重试。')
    }
  } finally {
    isStreaming.value = false
    controller = null
    await refreshConversations()
  }
}

function stopStreaming() {
  controller?.abort()
}

async function removeConversation(conversationId) {
  if (conversationId === currentId.value && isStreaming.value) stopStreaming()
  try {
    await deleteAiSession(conversationId)
    conversations.value = conversations.value.filter((item) => item.id !== conversationId)
    if (currentId.value !== conversationId) return

    currentId.value = null
    messages.value = []
    const nextId = conversations.value[0]?.id ?? null
    if (nextId != null) await selectConversation(nextId)
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '对话没有删除成功。')
  }
}

onMounted(loadSessions)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="app-page ai-chat">
    <header class="ai-chat__header">
      <div>
        <p class="eyebrow">GUIDED CONVERSATION</p>
        <h1 class="page-title">智能伴学</h1>
        <p class="page-copy">问单词、问语法、练口语，或者把一句话交给它翻译。</p>
      </div>
      <button
        class="secondary-button ai-chat__records"
        type="button"
        @click="sidebarOpen = !sidebarOpen"
      >
        对话记录
      </button>
    </header>

    <div class="ai-chat__body" :class="{ 'ai-chat__body--sidebar': sidebarOpen }">
      <ConversationSidebar
        :conversations="conversations"
        :current-id="currentId"
        :loading="isLoadingSessions"
        :error="sessionError"
        :open="sidebarOpen"
        @select="selectConversation"
        @create="startNewConversation"
        @delete="removeConversation"
        @close="sidebarOpen = false"
      />
      <button
        v-if="sidebarOpen"
        class="ai-chat__scrim"
        type="button"
        aria-label="收起对话记录"
        @click="sidebarOpen = false"
      ></button>

      <section class="ai-chat__main" :aria-busy="isLoadingMessages">
        <div class="ai-chat__main-header">
          <span>{{ currentTitle }}</span>
          <span v-if="isStreaming" class="ai-chat__status">正在回复…</span>
          <span v-else-if="isLoadingMessages" class="ai-chat__status">正在载入…</span>
        </div>

        <MessageList :messages="messages" @suggest="sendMessage" />

        <p v-if="errorMessage" class="inline-notice inline-notice--error" role="alert">
          {{ errorMessage }}
        </p>

        <ChatComposer
          :disabled="isLoadingMessages"
          :streaming="isStreaming"
          :scene="scene"
          @send="sendMessage"
          @stop="stopStreaming"
          @update:scene="scene = $event"
        />
      </section>
    </div>
  </div>
</template>

<style scoped src="./AiChat.css"></style>
