import request from './request'

export function listMcpChanges({ page = 1, pageSize = 20, status = '' } = {}) {
  return request.get('/admin/mcp-changes', {
    params: {
      page,
      page_size: pageSize,
      status: status || undefined,
    },
  })
}

export function getMcpChange(requestId) {
  return request.get(`/admin/mcp-changes/${requestId}`)
}

export function approveMcpChange(requestId) {
  return request.post(`/admin/mcp-changes/${requestId}/approve`)
}

export function rejectMcpChange(requestId, reason = '') {
  return request.post(`/admin/mcp-changes/${requestId}/reject`, {
    reason: reason || null,
  })
}

export function getMcpConnection() {
  return request.get('/admin/mcp-tokens/connection')
}

export function listMcpTokens() {
  return request.get('/admin/mcp-tokens')
}

export function createMcpToken(payload) {
  return request.post('/admin/mcp-tokens', payload)
}

export function revokeMcpToken(tokenId) {
  return request.post(`/admin/mcp-tokens/${tokenId}/revoke`)
}
