<script setup>
import { computed, onMounted, ref } from 'vue'

import { createMcpToken, getMcpConnection, listMcpTokens, revokeMcpToken } from '../../api/adminMcp'
import { getErrorMessage } from '../../utils/errors'
import { formatDate } from '../../utils/format'

const connection = ref({ enabled: false, endpoint: '', default_expires_in_days: 90 })
const tokens = ref([])
const isLoading = ref(true)
const isSaving = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')
const revealOpen = ref(false)
const created = ref(null)
const form = ref({ name: '', scopes: 'read', expiresInDays: '90' })

const scopeLabels = { read: '只读', write: '可提交变更' }
const expiryOptions = [
  { value: '30', label: '30 天' },
  { value: '90', label: '90 天' },
  { value: '365', label: '1 年' },
  { value: 'never', label: '永不过期' },
]

const claudeCodeCommand = computed(() => {
  if (!created.value) return ''
  return `claude mcp add --transport http english-practice-admin ${connection.value.endpoint} --header "Authorization: Bearer ${created.value.token}"`
})

const httpConfig = computed(() => {
  if (!created.value) return ''
  return JSON.stringify(
    {
      mcpServers: {
        'english-practice-admin': {
          type: 'http',
          url: connection.value.endpoint,
          headers: { Authorization: `Bearer ${created.value.token}` },
        },
      },
    },
    null,
    2,
  )
})

const stdioConfig = computed(() => {
  if (!created.value) return ''
  return JSON.stringify(
    {
      mcpServers: {
        'english-practice-admin': {
          command: 'npx',
          args: [
            '-y',
            'mcp-remote',
            connection.value.endpoint,
            '--header',
            `Authorization: Bearer ${created.value.token}`,
          ],
        },
      },
    },
    null,
    2,
  )
})

function tokenStatus(token) {
  if (token.revoked_at) return { label: '已吊销', className: 'revoked' }
  if (token.expires_at && new Date(token.expires_at).getTime() <= Date.now()) {
    return { label: '已过期', className: 'expired' }
  }
  return { label: '有效', className: 'active' }
}

async function loadConnection() {
  try {
    const result = await getMcpConnection()
    connection.value = result
    if (result.default_expires_in_days) {
      form.value.expiresInDays = String(result.default_expires_in_days)
    }
  } catch (error) {
    errorMessage.value = getErrorMessage(error, 'MCP 服务状态暂时无法读取。')
  }
}

async function loadTokens() {
  try {
    const result = await listMcpTokens()
    tokens.value = result.items || []
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '令牌列表暂时无法读取。')
  }
}

async function submitToken() {
  if (!form.value.name.trim()) {
    errorMessage.value = '请先填写令牌名称。'
    return
  }
  isSaving.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const expiresInDays =
      form.value.expiresInDays === 'never' ? null : Number(form.value.expiresInDays)
    created.value = await createMcpToken({
      name: form.value.name.trim(),
      scopes: form.value.scopes,
      expires_in_days: expiresInDays,
    })
    revealOpen.value = true
    form.value.name = ''
    await loadTokens()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '令牌创建失败。')
  } finally {
    isSaving.value = false
  }
}

async function handleRevoke(token) {
  if (!window.confirm(`确定吊销「${token.name}」？使用该令牌的客户端会立即无法连接。`)) return
  try {
    await revokeMcpToken(token.id)
    noticeMessage.value = '令牌已吊销。'
    await loadTokens()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '令牌吊销失败。')
  }
}

async function copyText(text, label) {
  try {
    await window.navigator.clipboard.writeText(text)
    noticeMessage.value = `${label}已复制。`
  } catch {
    errorMessage.value = '复制失败，请手动选择文本复制。'
  }
}

onMounted(async () => {
  isLoading.value = true
  await Promise.all([loadConnection(), loadTokens()])
  isLoading.value = false
})
</script>

<template>
  <div class="app-page admin-page">
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">MCP ACCESS</p>
        <h1 class="page-title">MCP 接入</h1>
        <p class="page-copy">
          为 Claude Code、Claude Desktop、VS Code 等客户端创建长期令牌。令牌只在创建时显示一次，
          可随时吊销。
        </p>
      </div>
    </header>

    <p v-if="noticeMessage" class="inline-notice inline-notice--success admin-notice">
      {{ noticeMessage }}
    </p>
    <p v-if="errorMessage" class="inline-notice inline-notice--error admin-notice">
      {{ errorMessage }}
    </p>

    <section class="mcp-connection">
      <div>
        <span class="mcp-connection__label">服务端点</span>
        <code class="mcp-connection__url">{{ connection.endpoint || '—' }}</code>
      </div>
      <span
        class="status-tag"
        :class="connection.enabled ? 'status-tag--active' : 'status-tag--disabled'"
      >
        {{ connection.enabled ? '已启用' : '未启用' }}
      </span>
    </section>
    <p v-if="!connection.enabled" class="mcp-hint">
      服务当前未启用，请在后端 `.env` 设置 `MCP_ENABLED=true` 后重启。
    </p>

    <section class="mcp-panel">
      <h2 class="mcp-panel__title">新建客户端令牌</h2>
      <form class="mcp-form" @submit.prevent="submitToken">
        <label class="mcp-field">
          <span>名称</span>
          <input
            v-model="form.name"
            class="field-input"
            type="text"
            maxlength="100"
            placeholder="例如：我的 Claude Code"
          />
        </label>
        <label class="mcp-field">
          <span>权限</span>
          <select v-model="form.scopes" class="field-input">
            <option value="read">只读（查询数据）</option>
            <option value="write">可提交变更（仍需人工审批）</option>
          </select>
        </label>
        <label class="mcp-field">
          <span>有效期</span>
          <select v-model="form.expiresInDays" class="field-input">
            <option v-for="option in expiryOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <button class="primary-button" type="submit" :disabled="isSaving">
          {{ isSaving ? '创建中…' : '创建令牌' }}
        </button>
      </form>
      <p class="mcp-hint">
        只读令牌只能调用查询工具；即使选择“可提交变更”，写操作也必须由管理员在
        <RouterLink to="/admin/mcp-approvals">MCP 审批</RouterLink> 页面确认。
      </p>
    </section>

    <section class="mcp-panel">
      <h2 class="mcp-panel__title">已创建的令牌</h2>
      <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入令牌">
        <span class="skeleton-line"></span>
        <span class="skeleton-line"></span>
      </div>
      <p v-else-if="!tokens.length" class="mcp-hint">还没有创建过客户端令牌。</p>
      <div v-else class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>令牌</th>
              <th>权限</th>
              <th>创建人</th>
              <th>最近使用</th>
              <th>到期</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="token in tokens" :key="token.id">
              <td class="mcp-token-name">{{ token.name }}</td>
              <td>
                <code>{{ token.token_prefix }}…</code>
              </td>
              <td>{{ scopeLabels[token.scopes] || token.scopes }}</td>
              <td class="mcp-muted">{{ token.created_by_username || `#${token.created_by}` }}</td>
              <td class="mcp-muted">{{ formatDate(token.last_used_at, true) }}</td>
              <td class="mcp-muted">
                {{ token.expires_at ? formatDate(token.expires_at) : '永不过期' }}
              </td>
              <td>
                <span class="status-tag" :class="`status-tag--${tokenStatus(token).className}`">
                  {{ tokenStatus(token).label }}
                </span>
              </td>
              <td>
                <button
                  v-if="!token.revoked_at"
                  class="text-link danger-link"
                  type="button"
                  @click="handleRevoke(token)"
                >
                  吊销
                </button>
                <span v-else class="mcp-muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="revealOpen && created" class="mcp-overlay" @click.self="revealOpen = false">
      <section class="mcp-dialog" role="dialog" aria-label="令牌已创建">
        <header class="mcp-dialog__header">
          <div>
            <h2>令牌「{{ created.name }}」已创建</h2>
            <p class="mcp-hint">令牌只显示这一次，关闭后无法再次查看。</p>
          </div>
          <button class="text-link" type="button" @click="revealOpen = false">关闭</button>
        </header>

        <div class="mcp-token-reveal">
          <code>{{ created.token }}</code>
          <button class="secondary-button" type="button" @click="copyText(created.token, '令牌')">
            复制令牌
          </button>
        </div>

        <h3 class="mcp-block__title">Claude Code</h3>
        <div class="mcp-block">
          <pre>{{ claudeCodeCommand }}</pre>
          <button
            class="secondary-button"
            type="button"
            @click="copyText(claudeCodeCommand, '命令')"
          >
            复制
          </button>
        </div>

        <h3 class="mcp-block__title">Claude Desktop / VS Code（HTTP）</h3>
        <div class="mcp-block">
          <pre>{{ httpConfig }}</pre>
          <button class="secondary-button" type="button" @click="copyText(httpConfig, '配置')">
            复制
          </button>
        </div>

        <h3 class="mcp-block__title">仅支持 stdio 的客户端</h3>
        <div class="mcp-block">
          <pre>{{ stdioConfig }}</pre>
          <button class="secondary-button" type="button" @click="copyText(stdioConfig, '配置')">
            复制
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped src="./McpAccess.css"></style>
