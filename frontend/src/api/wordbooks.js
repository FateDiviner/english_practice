import request from './request'

export function listWordbooks({ page = 1, pageSize = 12 } = {}) {
  return request.get('/wordbooks', { params: { page, page_size: pageSize } })
}

export function getWordbook(wordbookId) {
  return request.get(`/wordbooks/${wordbookId}`)
}

export function listWordbookWords(wordbookId, { page = 1, pageSize = 20, mastery = null } = {}) {
  return request.get(`/wordbooks/${wordbookId}/words`, {
    params: { page, page_size: pageSize, mastery },
  })
}

export function startWordbook(wordbookId) {
  return request.post(`/wordbooks/${wordbookId}/start`)
}
