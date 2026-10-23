import request from './request'

export function sendAiChat(payload) {
  return request.post('/ai/chat', payload)
}

export function listAiSessions() {
  return request.get('/ai/sessions')
}

export function createAiSession(payload) {
  return request.post('/ai/sessions', payload)
}
