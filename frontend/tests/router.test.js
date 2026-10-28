import assert from 'node:assert/strict'
import test from 'node:test'
import { createMemoryHistory, createRouter } from 'vue-router'

import { routes } from '../src/router/routes.js'

function makeRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

test('MCP 接入与审批都挂在 admin 路由下', () => {
  const router = makeRouter()

  const access = router.resolve('/admin/mcp/access')
  assert.equal(access.name, 'admin-mcp-access')
  assert.equal(access.meta.requiresAdmin, true)
  assert.equal(access.matched[0].path, '/admin')

  const approvals = router.resolve('/admin/mcp/approvals')
  assert.equal(approvals.name, 'admin-mcp-approvals')
  assert.equal(approvals.meta.requiresAdmin, true)
})

test('MCP 入口重定向到接入配置', () => {
  const router = makeRouter()
  const resolved = router.resolve('/admin/mcp')
  const record = resolved.matched[resolved.matched.length - 1]
  assert.equal(record.redirect, '/admin/mcp/access')
})

test('旧 MCP 地址重定向到新路由', () => {
  const router = makeRouter()

  const access = router.resolve('/admin/mcp-access')
  assert.equal(access.matched[access.matched.length - 1].redirect, '/admin/mcp/access')

  const approvals = router.resolve('/admin/mcp-approvals')
  assert.equal(approvals.matched[approvals.matched.length - 1].redirect, '/admin/mcp/approvals')
})

test('未知路径落到兜底路由而不是 admin', () => {
  const router = makeRouter()
  const resolved = router.resolve('/admin/not-exist')
  assert.equal(resolved.matched[0].path, '/:pathMatch(.*)*')
})
