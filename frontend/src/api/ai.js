import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'
import { consumeSseResponse } from '../utils/sse'
import request, { ApiError, handleUnauthenticated } from './request'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export function listAiSessions({ page = 1, pageSize = 50 } = {}) {
  return request.get('/ai/sessions', { params: { page, page_size: pageSize } })
}

export function createAiSession(payload = {}) {
  return request.post('/ai/sessions', payload)
}

export function getAiSession(sessionId) {
  return request.get(`/ai/sessions/${sessionId}`)
}

export function deleteAiSession(sessionId) {
  return request.delete(`/ai/sessions/${sessionId}`)
}

async function readErrorPayload(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

export async function streamAgentChat({
  message,
  scene = null,
  conversationId = null,
  history = [],
  signal,
  onMeta,
  onDelta,
  onDone,
}) {
  const authStore = useAuthStore(pinia)
  const response = await fetch(`${API_BASE_URL}/agent/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {}),
    },
    body: JSON.stringify({
      message,
      scene: scene || null,
      conversation_id: conversationId,
      history,
    }),
    signal,
  })

  if (!response.ok) {
    const payload = await readErrorPayload(response)
    if (response.status === 401 || payload?.code === 40101) {
      handleUnauthenticated()
    }
    throw new ApiError(payload?.message || '对话请求没有完成', {
      code: payload?.code,
      status: response.status,
      data: payload?.data,
    })
  }

  let finished = false
  await consumeSseResponse(response, ({ event, data }) => {
    if (event === 'meta') {
      onMeta?.(data)
    } else if (event === 'delta') {
      onDelta?.(data)
    } else if (event === 'done') {
      finished = true
      onDone?.(data)
    } else if (event === 'error') {
      throw new ApiError(data?.message || '对话生成失败')
    }
  })

  if (!finished) {
    throw new ApiError('对话连接中断，请重试')
  }
}
