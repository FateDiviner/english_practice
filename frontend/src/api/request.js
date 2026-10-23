import axios from 'axios'

import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'

export class ApiError extends Error {
  constructor(message, { code = null, status = null, data = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.data = data
  }
}

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 20_000,
})

request.interceptors.request.use((config) => {
  const authStore = useAuthStore(pinia)
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

function handleUnauthenticated() {
  const authStore = useAuthStore(pinia)
  authStore.clearSession()
  const currentPath = window.location.pathname
  if (currentPath !== '/login' && currentPath !== '/register') {
    window.location.replace('/login')
  }
}

function normalizeError(error) {
  const response = error.response
  const payload = response?.data
  const message =
    payload?.message ||
    (error.code === 'ECONNABORTED' ? '请求超时，请稍后再试' : null) ||
    (response ? '请求未完成，请稍后再试' : '无法连接服务器，请检查网络')

  if (payload?.code === 40101) {
    handleUnauthenticated()
  }

  return new ApiError(message, {
    code: payload?.code,
    status: response?.status,
    data: payload?.data,
  })
}

request.interceptors.response.use(
  (response) => {
    const payload = response.data
    if (payload && payload.code === 0) return payload.data
    if (payload && typeof payload.code === 'number') {
      if (payload.code === 40101) handleUnauthenticated()
      return Promise.reject(
        new ApiError(payload.message || '请求未完成', {
          code: payload.code,
          status: response.status,
          data: payload.data,
        }),
      )
    }
    return payload
  },
  (error) => Promise.reject(normalizeError(error)),
)

export default request
