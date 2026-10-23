import request from './request'

export function createPracticeSession(payload) {
  return request.post('/practice/sessions', payload)
}

export function submitPracticeAnswer(sessionId, payload) {
  return request.post(`/practice/sessions/${sessionId}/answer`, payload)
}

export function finishPracticeSession(sessionId) {
  return request.post(`/practice/sessions/${sessionId}/finish`)
}

export function getPracticeSession(sessionId) {
  return request.get(`/practice/sessions/${sessionId}`)
}
