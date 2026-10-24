<script setup>
import { reactive, ref, watch } from 'vue'

import {
  getAdminUserProfile,
  getAdminUserStats,
  listAdminUsers,
  resetAdminUserPassword,
  updateAdminUserStatus,
} from '../../api/admin'
import AdminDrawer from '../../components/AdminDrawer.vue'
import PagePagination from '../../components/PagePagination.vue'
import UserStatsDrawer from '../../components/admin/UserStatsDrawer.vue'
import { useAuthStore } from '../../stores/auth'
import { getErrorMessage } from '../../utils/errors'
import { formatDate } from '../../utils/format'

const PAGE_SIZE = 20
const authStore = useAuthStore()
const items = ref([])
const total = ref(0)
const page = ref(1)
const keywordInput = ref('')
const keyword = ref('')
const statusFilter = ref('')
const isLoading = ref(true)
const errorMessage = ref('')
const noticeMessage = ref('')
const updatingId = ref(null)
const resetDrawerOpen = ref(false)
const resetTarget = ref(null)
const resetForm = reactive({ password: '', confirmPassword: '' })
const resetError = ref('')
const isResetting = ref(false)
const statsDrawerOpen = ref(false)
const statsTarget = ref(null)
const stats = ref(null)
const statsError = ref('')
const isLoadingStats = ref(false)
const profile = ref(null)
const profileError = ref('')
const isLoadingProfile = ref(false)

const roleLabels = { user: '学习者', admin: '管理员' }
const statusLabels = { active: '正常', disabled: '已禁用' }

async function loadUsers() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const result = await listAdminUsers({
      page: page.value,
      pageSize: PAGE_SIZE,
      keyword: keyword.value,
      status: statusFilter.value,
    })
    items.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '用户列表暂时无法读取。')
  } finally {
    isLoading.value = false
  }
}

function applyFilters() {
  keyword.value = keywordInput.value.trim()
  if (page.value === 1) loadUsers()
  else page.value = 1
}

function applyStatusFilter() {
  if (page.value === 1) loadUsers()
  else page.value = 1
}

async function toggleStatus(user) {
  if (user.id === authStore.user?.id) {
    errorMessage.value = '不能禁用当前登录的管理员账户。'
    return
  }
  updatingId.value = user.id
  noticeMessage.value = ''
  try {
    const nextStatus = user.status === 'active' ? 'disabled' : 'active'
    await updateAdminUserStatus(user.id, nextStatus)
    noticeMessage.value = nextStatus === 'active' ? '用户已启用。' : '用户已禁用。'
    await loadUsers()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '用户状态没有更新成功。')
  } finally {
    updatingId.value = null
  }
}

function openReset(user) {
  resetTarget.value = user
  resetForm.password = ''
  resetForm.confirmPassword = ''
  resetError.value = ''
  resetDrawerOpen.value = true
}

async function submitReset() {
  resetError.value = ''
  if (resetForm.password.length < 8) {
    resetError.value = '新密码至少需要 8 位。'
    return
  }
  if (resetForm.password !== resetForm.confirmPassword) {
    resetError.value = '两次输入的新密码不一致。'
    return
  }
  isResetting.value = true
  try {
    await resetAdminUserPassword(resetTarget.value.id, resetForm.password)
    resetDrawerOpen.value = false
    noticeMessage.value = `已重置 ${resetTarget.value.username} 的密码。`
  } catch (error) {
    resetError.value = getErrorMessage(error, '密码没有重置成功。')
  } finally {
    isResetting.value = false
  }
}

async function openStats(user) {
  statsTarget.value = user
  stats.value = null
  statsError.value = ''
  profile.value = null
  profileError.value = ''
  statsDrawerOpen.value = true
  isLoadingStats.value = true
  try {
    stats.value = await getAdminUserStats(user.id)
  } catch (error) {
    statsError.value = getErrorMessage(error, '该用户的学习数据暂时无法读取。')
  } finally {
    isLoadingStats.value = false
  }
}

async function loadProfile() {
  if (!statsTarget.value || isLoadingProfile.value) return
  profile.value = null
  profileError.value = ''
  isLoadingProfile.value = true
  try {
    profile.value = await getAdminUserProfile(statsTarget.value.id)
  } catch (error) {
    profileError.value = getErrorMessage(error, '学情画像暂时无法生成。')
  } finally {
    isLoadingProfile.value = false
  }
}

watch(page, loadUsers, { immediate: true })
</script>

<template>
  <div class="app-page admin-page">
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">PEOPLE REGISTER</p>
        <h1 class="page-title">用户管理</h1>
        <p class="page-copy">查看学习者状态、累计练习量，并处理账户启停与密码重置。</p>
      </div>
    </header>

    <form class="user-filters" @submit.prevent="applyFilters">
      <input
        v-model="keywordInput"
        class="field-input"
        type="search"
        placeholder="搜索用户名或邮箱"
      />
      <select v-model="statusFilter" class="field-input" @change="applyStatusFilter">
        <option value="">全部状态</option>
        <option value="active">正常</option>
        <option value="disabled">已禁用</option>
      </select>
      <button class="secondary-button" type="submit">搜索</button>
    </form>

    <p v-if="noticeMessage" class="inline-notice inline-notice--success admin-notice">
      {{ noticeMessage }}
    </p>
    <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入用户">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <section v-else-if="errorMessage" class="state-panel">
      <h2 class="state-title">用户登记簿暂时没有打开</h2>
      <p class="state-copy">{{ errorMessage }}</p>
      <button class="secondary-button" type="button" @click="loadUsers">重新载入</button>
    </section>

    <section v-else-if="!items.length" class="state-panel state-panel--center">
      <h2 class="state-title">没有找到符合条件的用户</h2>
      <p class="state-copy">换一个关键词或状态筛选，再试一次。</p>
    </section>

    <div v-else class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>用户名</th>
            <th>邮箱</th>
            <th>角色</th>
            <th>状态</th>
            <th>累计练习</th>
            <th>注册时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in items" :key="user.id">
            <td class="user-name">{{ user.username }}</td>
            <td class="user-email">{{ user.email }}</td>
            <td>{{ roleLabels[user.role] }}</td>
            <td>
              <span class="status-tag" :class="`status-tag--${user.status}`">{{
                statusLabels[user.status]
              }}</span>
            </td>
            <td>{{ user.total_practiced }} 题</td>
            <td class="user-date">{{ formatDate(user.created_at, true) }}</td>
            <td>
              <div class="row-actions">
                <button class="text-link" type="button" @click="openStats(user)">查看数据</button>
                <button class="text-link" type="button" @click="openReset(user)">重置密码</button>
                <button
                  class="text-link"
                  :class="{ 'danger-link': user.status === 'active' }"
                  type="button"
                  :disabled="updatingId === user.id || user.id === authStore.user?.id"
                  @click="toggleStatus(user)"
                >
                  {{
                    updatingId === user.id ? '处理中…' : user.status === 'active' ? '禁用' : '启用'
                  }}
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

    <AdminDrawer
      :open="resetDrawerOpen"
      title="重置用户密码"
      :description="resetTarget ? `正在处理：${resetTarget.username}` : ''"
      @close="resetDrawerOpen = false"
    >
      <form class="reset-form" @submit.prevent="submitReset">
        <label class="field">
          <span class="field-label">新密码</span>
          <input
            v-model="resetForm.password"
            class="field-input"
            type="password"
            minlength="8"
            maxlength="72"
            autocomplete="new-password"
          />
        </label>
        <label class="field">
          <span class="field-label">确认新密码</span>
          <input
            v-model="resetForm.confirmPassword"
            class="field-input"
            type="password"
            minlength="8"
            maxlength="72"
            autocomplete="new-password"
          />
        </label>
        <p v-if="resetError" class="inline-notice inline-notice--error" role="alert">
          {{ resetError }}
        </p>
        <p class="field-help">重置后旧密码立即失效，请通过安全渠道告知用户。</p>
        <div class="form-actions">
          <button class="secondary-button" type="button" @click="resetDrawerOpen = false">
            取消
          </button>
          <button class="primary-button" type="submit" :disabled="isResetting">
            {{ isResetting ? '重置中…' : '确认重置' }}
          </button>
        </div>
      </form>
    </AdminDrawer>

    <UserStatsDrawer
      :open="statsDrawerOpen"
      :user="statsTarget"
      :stats="stats"
      :loading="isLoadingStats"
      :error="statsError"
      :profile="profile"
      :profile-loading="isLoadingProfile"
      :profile-error="profileError"
      @load-profile="loadProfile"
      @close="statsDrawerOpen = false"
    />
  </div>
</template>

<style scoped src="./UserManage.css"></style>
