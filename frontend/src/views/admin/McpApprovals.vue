<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { approveMcpChange, listMcpChanges, rejectMcpChange } from '../../api/adminMcp'
import PagePagination from '../../components/PagePagination.vue'
import { getErrorMessage } from '../../utils/errors'
import { formatDate } from '../../utils/format'

const PAGE_SIZE = 20
const REFRESH_INTERVAL = 15_000

const actionLabels = {
  'wordbook.create': '创建词书',
  'wordbook.update': '更新词书',
  'wordbook.delete': '删除词书',
  'word.create': '新增单词',
  'word.update': '更新单词',
  'word.delete': '删除单词',
  'word.import': '批量导入',
  'user.status': '用户状态',
  'user.profile_refresh': '刷新画像',
}

const statusLabels = {
  pending: '待审批',
  approved: '执行中',
  executed: '已执行',
  rejected: '已驳回',
  failed: '执行失败',
  expired: '已过期',
  cancelled: '已取消',
}

const items = ref([])
const total = ref(0)
const page = ref(1)
const statusFilter = ref('pending')
const isLoading = ref(true)
const errorMessage = ref('')
const noticeMessage = ref('')
const actingId = ref(null)
const detail = ref(null)
const detailOpen = ref(false)
const confirmOpen = ref(false)
const confirmMode = ref('approve')
const confirmTarget = ref(null)
const rejectReason = ref('')

let refreshTimer = null

const pendingCount = computed(() => items.value.filter((item) => item.status === 'pending').length)
const canAct = computed(() => confirmTarget.value?.status === 'pending')

async function loadChanges({ silent = false } = {}) {
  if (!silent) isLoading.value = true
  if (!silent) errorMessage.value = ''
  try {
    const result = await listMcpChanges({
      page: page.value,
      pageSize: PAGE_SIZE,
      status: statusFilter.value,
    })
    items.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    if (!silent) errorMessage.value = getErrorMessage(error, 'MCP 审批列表暂时无法读取。')
  } finally {
    if (!silent) isLoading.value = false
  }
}

function changeStatusFilter() {
  if (page.value === 1) loadChanges()
  else page.value = 1
}

function openDetail(item) {
  detail.value = item
  detailOpen.value = true
}

function openConfirm(item, mode) {
  confirmTarget.value = item
  confirmMode.value = mode
  rejectReason.value = ''
  confirmOpen.value = true
}

async function submitConfirm() {
  const target = confirmTarget.value
  if (!target) return
  actingId.value = target.id
  noticeMessage.value = ''
  try {
    if (confirmMode.value === 'approve') {
      const result = await approveMcpChange(target.id)
      noticeMessage.value = `已通过并执行：${result.summary}`
    } else {
      await rejectMcpChange(target.id, rejectReason.value.trim())
      noticeMessage.value = `已驳回：${target.summary}`
    }
    confirmOpen.value = false
    await loadChanges({ silent: true })
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '审批操作没有完成。')
    confirmOpen.value = false
  } finally {
    actingId.value = null
  }
}

function payloadText(item) {
  return JSON.stringify(item?.payload || {}, null, 2)
}

watch(page, () => loadChanges())
watch(statusFilter, changeStatusFilter)

onMounted(() => {
  loadChanges()
  refreshTimer = window.setInterval(() => {
    if (!confirmOpen.value && !detailOpen.value) loadChanges({ silent: true })
  }, REFRESH_INTERVAL)
})

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
  <div class="app-page admin-page">
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">MCP REVIEW DESK</p>
        <h1 class="page-title">MCP 审批</h1>
        <p class="page-copy">
          MCP 客户端提交的增删改申请会先停在这里，由管理员确认后才会真正写入数据库。
        </p>
      </div>
    </header>

    <form class="mcp-filters" @submit.prevent="loadChanges()">
      <select v-model="statusFilter" class="field-input">
        <option value="pending">待审批</option>
        <option value="">全部状态</option>
        <option value="executed">已执行</option>
        <option value="rejected">已驳回</option>
        <option value="failed">执行失败</option>
        <option value="expired">已过期</option>
        <option value="cancelled">已取消</option>
      </select>
      <button class="secondary-button" type="submit">刷新</button>
      <span class="mcp-filters__hint">每 15 秒自动刷新 · 当前页待审批 {{ pendingCount }} 条</span>
    </form>

    <p v-if="noticeMessage" class="inline-notice inline-notice--success admin-notice">
      {{ noticeMessage }}
    </p>

    <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入审批申请">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <section v-else-if="errorMessage" class="state-panel">
      <h2 class="state-title">审批队列暂时没有打开</h2>
      <p class="state-copy">{{ errorMessage }}</p>
      <button class="secondary-button" type="button" @click="loadChanges()">重新载入</button>
    </section>

    <section v-else-if="!items.length" class="state-panel state-panel--center">
      <h2 class="state-title">没有待处理的申请</h2>
      <p class="state-copy">MCP 客户端提交变更后会出现在这里。</p>
    </section>

    <div v-else class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>提交时间</th>
            <th>动作</th>
            <th>摘要</th>
            <th>发起人</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td class="mcp-date">{{ formatDate(item.created_at, true) }}</td>
            <td>
              <span class="mcp-action">{{
                actionLabels[item.action_type] || item.action_type
              }}</span>
              <small v-if="item.target_id" class="mcp-target">#{{ item.target_id }}</small>
            </td>
            <td class="mcp-summary">{{ item.summary }}</td>
            <td class="mcp-requester">
              {{ item.requested_by_username || `#${item.requested_by}` }}
            </td>
            <td>
              <span class="status-tag" :class="`status-tag--${item.status}`">
                {{ statusLabels[item.status] || item.status }}
              </span>
            </td>
            <td>
              <div class="row-actions">
                <button class="text-link" type="button" @click="openDetail(item)">详情</button>
                <button
                  v-if="item.status === 'pending'"
                  class="text-link"
                  type="button"
                  :disabled="actingId === item.id"
                  @click="openConfirm(item, 'approve')"
                >
                  通过
                </button>
                <button
                  v-if="item.status === 'pending'"
                  class="text-link danger-link"
                  type="button"
                  :disabled="actingId === item.id"
                  @click="openConfirm(item, 'reject')"
                >
                  驳回
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <PagePagination
      v-if="total > PAGE_SIZE"
      v-model:page="page"
      :page-size="PAGE_SIZE"
      :total="total"
    />

    <div v-if="detailOpen" class="mcp-overlay" @click.self="detailOpen = false">
      <section class="mcp-dialog" role="dialog" aria-label="申请详情">
        <header class="mcp-dialog__header">
          <h2>{{ detail?.summary }}</h2>
          <button class="text-link" type="button" @click="detailOpen = false">关闭</button>
        </header>
        <dl class="mcp-detail">
          <div>
            <dt>动作</dt>
            <dd>{{ actionLabels[detail?.action_type] || detail?.action_type }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{{ statusLabels[detail?.status] || detail?.status }}</dd>
          </div>
          <div>
            <dt>发起人</dt>
            <dd>{{ detail?.requested_by_username || `#${detail?.requested_by}` }}</dd>
          </div>
          <div>
            <dt>理由</dt>
            <dd>{{ detail?.reason || '—' }}</dd>
          </div>
          <div>
            <dt>过期时间</dt>
            <dd>{{ formatDate(detail?.expires_at, true) }}</dd>
          </div>
          <div v-if="detail?.error_message">
            <dt>错误信息</dt>
            <dd>{{ detail.error_message }}</dd>
          </div>
        </dl>
        <h3 class="mcp-detail__title">申请参数</h3>
        <pre class="mcp-payload">{{ payloadText(detail) }}</pre>
        <h3 v-if="detail?.result" class="mcp-detail__title">执行结果</h3>
        <pre v-if="detail?.result" class="mcp-payload">{{
          JSON.stringify(detail.result, null, 2)
        }}</pre>
      </section>
    </div>

    <div v-if="confirmOpen" class="mcp-overlay" @click.self="confirmOpen = false">
      <section class="mcp-dialog mcp-dialog--confirm" role="dialog" aria-label="确认审批">
        <header class="mcp-dialog__header">
          <h2>{{ confirmMode === 'approve' ? '确认执行这条变更？' : '确认驳回这条申请？' }}</h2>
        </header>
        <p class="mcp-confirm__summary">{{ confirmTarget?.summary }}</p>
        <p v-if="confirmMode === 'approve'" class="mcp-confirm__warning">
          通过后会立即调用后台服务写入数据，且无法撤回。
        </p>
        <label v-else class="mcp-reason">
          <span>驳回原因（可选）</span>
          <textarea v-model="rejectReason" class="field-input" rows="3" maxlength="500"></textarea>
        </label>
        <footer class="mcp-dialog__actions">
          <button class="secondary-button" type="button" @click="confirmOpen = false">取消</button>
          <button
            class="primary-button"
            :class="{ 'danger-button': confirmMode === 'reject' }"
            type="button"
            :disabled="!canAct || actingId === confirmTarget?.id"
            @click="submitConfirm"
          >
            {{
              actingId === confirmTarget?.id
                ? '处理中…'
                : confirmMode === 'approve'
                  ? '通过并执行'
                  : '确认驳回'
            }}
          </button>
        </footer>
      </section>
    </div>
  </div>
</template>

<style scoped src="./McpApprovals.css"></style>
