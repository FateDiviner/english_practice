import request from './request'

export function listAdminWordbooks({ page = 1, pageSize = 20 } = {}) {
  return request.get('/admin/wordbooks', { params: { page, page_size: pageSize } })
}

export function createAdminWordbook(payload) {
  return request.post('/admin/wordbooks', payload)
}

export function updateAdminWordbook(wordbookId, payload) {
  return request.put(`/admin/wordbooks/${wordbookId}`, payload)
}

export function deleteAdminWordbook(wordbookId) {
  return request.delete(`/admin/wordbooks/${wordbookId}`)
}

export function listAdminWords(wordbookId, { page = 1, pageSize = 20, keyword = '' } = {}) {
  return request.get(`/admin/wordbooks/${wordbookId}/words`, {
    params: { page, page_size: pageSize, keyword: keyword || undefined },
  })
}

export function createAdminWord(wordbookId, payload) {
  return request.post(`/admin/wordbooks/${wordbookId}/words`, payload)
}

export function updateAdminWord(wordId, payload) {
  return request.put(`/admin/words/${wordId}`, payload)
}

export function deleteAdminWord(wordId) {
  return request.delete(`/admin/words/${wordId}`)
}

export function getAdminOverview() {
  return request.get('/admin/overview')
}

export function listAdminUsers({ page = 1, pageSize = 20, keyword = '', status = '' } = {}) {
  return request.get('/admin/users', {
    params: {
      page,
      page_size: pageSize,
      keyword: keyword || undefined,
      status: status || undefined,
    },
  })
}

export function updateAdminUserStatus(userId, status) {
  return request.patch(`/admin/users/${userId}/status`, { status })
}

export function resetAdminUserPassword(userId, newPassword) {
  return request.post(`/admin/users/${userId}/reset-password`, { new_password: newPassword })
}

export function getAdminUserStats(userId) {
  return request.get(`/admin/users/${userId}/stats`)
}

export function readAdminUserProfile(userId) {
  return request.get(`/admin/users/${userId}/profile`)
}

const PROFILE_TIMEOUT_MS = 180_000

export function getAdminUserProfile(userId) {
  return request.post(`/admin/users/${userId}/profile`, undefined, {
    timeout: PROFILE_TIMEOUT_MS,
  })
}

export function previewAdminImport(wordbookId, file) {
  const body = new FormData()
  body.append('file', file)
  return request.post(`/admin/wordbooks/${wordbookId}/import/preview`, body)
}

export function importAdminWords(wordbookId, file, mapping) {
  const body = new FormData()
  body.append('file', file)
  body.append('mapping', JSON.stringify(mapping))
  return request.post(`/admin/wordbooks/${wordbookId}/import`, body)
}

export function getAdminImportJob(importJobId) {
  return request.get(`/admin/import-jobs/${importJobId}`)
}
