<script setup>
import { reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import {
  createAdminWordbook,
  deleteAdminWordbook,
  listAdminWordbooks,
  updateAdminWordbook,
} from '../../api/admin'
import AdminDrawer from '../../components/AdminDrawer.vue'
import PagePagination from '../../components/PagePagination.vue'
import { getErrorMessage, hasBusinessCode } from '../../utils/errors'
import { formatDate } from '../../utils/format'

const PAGE_SIZE = 15
const items = ref([])
const total = ref(0)
const page = ref(1)
const isLoading = ref(true)
const errorMessage = ref('')
const noticeMessage = ref('')
const isDrawerOpen = ref(false)
const isSaving = ref(false)
const formError = ref('')
const pendingDeleteId = ref(null)
const deletingId = ref(null)
const form = reactive({ id: null, name: '', description: '', level: '', status: 'draft' })

const statusLabels = { draft: '草稿', published: '已发布', archived: '已归档' }

function resetForm() {
  Object.assign(form, { id: null, name: '', description: '', level: '', status: 'draft' })
  formError.value = ''
}

function openCreate() {
  resetForm()
  isDrawerOpen.value = true
}

function openEdit(book) {
  Object.assign(form, {
    id: book.id,
    name: book.name,
    description: book.description || '',
    level: book.level || '',
    status: book.status,
  })
  formError.value = ''
  isDrawerOpen.value = true
}

async function loadWordbooks() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const result = await listAdminWordbooks({ page: page.value, pageSize: PAGE_SIZE })
    items.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '词书列表暂时无法读取。')
  } finally {
    isLoading.value = false
  }
}

async function saveWordbook() {
  if (!form.name.trim()) {
    formError.value = '词书名不能为空。'
    return
  }
  isSaving.value = true
  formError.value = ''
  const payload = {
    name: form.name.trim(),
    description: form.description.trim() || null,
    level: form.level.trim() || null,
    status: form.status,
  }
  try {
    if (form.id) await updateAdminWordbook(form.id, payload)
    else await createAdminWordbook(payload)
    isDrawerOpen.value = false
    noticeMessage.value = form.id ? '词书信息已更新。' : '新词书已创建。'
    if (!form.id) page.value = 1
    await loadWordbooks()
  } catch (error) {
    formError.value = getErrorMessage(error, '词书没有保存成功。')
  } finally {
    isSaving.value = false
  }
}

async function togglePublish(book) {
  const nextStatus = book.status === 'published' ? 'draft' : 'published'
  noticeMessage.value = ''
  try {
    await updateAdminWordbook(book.id, { status: nextStatus })
    noticeMessage.value = nextStatus === 'published' ? '词书已上架。' : '词书已下架。'
    await loadWordbooks()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '词书状态没有更新成功。')
  }
}

async function confirmDelete(book) {
  deletingId.value = book.id
  noticeMessage.value = ''
  try {
    await deleteAdminWordbook(book.id)
    pendingDeleteId.value = null
    noticeMessage.value = '词书已删除。'
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    else await loadWordbooks()
  } catch (error) {
    if (hasBusinessCode(error, 40901)) {
      errorMessage.value = '这本词书里还有单词，请先进入单词管理清空后再删除。'
    } else {
      errorMessage.value = getErrorMessage(error, '词书没有删除成功。')
    }
    pendingDeleteId.value = null
  } finally {
    deletingId.value = null
  }
}

watch(page, loadWordbooks, { immediate: true })
</script>

<template>
  <div class="app-page admin-page">
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">CONTENT OFFICE</p>
        <h1 class="page-title">词书管理</h1>
        <p class="page-copy">维护学习目录、上下架状态，并进入每本词书管理单词。</p>
      </div>
      <button class="primary-button" type="button" @click="openCreate">新建词书</button>
    </header>

    <p v-if="noticeMessage" class="inline-notice inline-notice--success admin-notice">
      {{ noticeMessage }}
    </p>
    <p v-if="errorMessage" class="inline-notice inline-notice--error admin-notice" role="alert">
      {{ errorMessage }}
      <button class="text-link admin-notice__retry" type="button" @click="loadWordbooks">
        重试
      </button>
    </p>

    <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入词书">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <section v-else-if="!items.length" class="state-panel state-panel--center">
      <h2 class="state-title">管理室里还没有词书</h2>
      <p class="state-copy">先创建一本词书，再往里添加第一批单词。</p>
      <button class="primary-button" type="button" @click="openCreate">创建第一本</button>
    </section>

    <div v-else class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>词书</th>
            <th>状态</th>
            <th>词数</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="book in items" :key="book.id">
            <td>
              <div class="wordbook-cell">
                <strong>{{ book.name }}</strong>
                <small>{{ book.level || '未分级' }} · {{ book.description || '暂无说明' }}</small>
              </div>
            </td>
            <td>
              <span class="status-tag" :class="`status-tag--${book.status}`">{{
                statusLabels[book.status]
              }}</span>
            </td>
            <td>{{ book.word_count }}</td>
            <td>{{ formatDate(book.updated_at, true) }}</td>
            <td>
              <div class="row-actions">
                <RouterLink :to="`/admin/wordbooks/${book.id}/words`">管理单词</RouterLink>
                <button class="text-link" type="button" @click="openEdit(book)">编辑</button>
                <button class="text-link" type="button" @click="togglePublish(book)">
                  {{ book.status === 'published' ? '下架' : '上架' }}
                </button>
                <template v-if="pendingDeleteId === book.id">
                  <button
                    class="text-link danger-link"
                    type="button"
                    :disabled="deletingId === book.id"
                    @click="confirmDelete(book)"
                  >
                    {{ deletingId === book.id ? '删除中…' : '确认删除' }}
                  </button>
                  <button class="text-link" type="button" @click="pendingDeleteId = null">
                    取消
                  </button>
                </template>
                <button
                  v-else
                  class="text-link danger-link"
                  type="button"
                  @click="pendingDeleteId = book.id"
                >
                  删除
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
      :open="isDrawerOpen"
      :title="form.id ? '编辑词书' : '新建词书'"
      description="词书信息保存后会立即出现在管理表格中。"
      @close="isDrawerOpen = false"
    >
      <form class="form-grid" @submit.prevent="saveWordbook">
        <label class="field form-grid__wide">
          <span class="field-label">词书名</span>
          <input
            v-model="form.name"
            class="field-input"
            maxlength="100"
            placeholder="例如：大学英语四级核心词"
          />
        </label>
        <label class="field form-grid__wide">
          <span class="field-label">说明</span>
          <textarea
            v-model="form.description"
            class="field-input form-textarea"
            rows="4"
            placeholder="这本词书适合谁、如何使用"
          ></textarea>
        </label>
        <label class="field">
          <span class="field-label">分级</span>
          <input v-model="form.level" class="field-input" maxlength="20" placeholder="如 CET-4" />
        </label>
        <label class="field">
          <span class="field-label">状态</span>
          <select v-model="form.status" class="field-input">
            <option value="draft">草稿</option>
            <option value="published">已发布</option>
            <option value="archived">已归档</option>
          </select>
        </label>
        <p v-if="formError" class="inline-notice inline-notice--error form-grid__wide" role="alert">
          {{ formError }}
        </p>
        <div class="form-actions form-grid__wide">
          <button class="secondary-button" type="button" @click="isDrawerOpen = false">取消</button>
          <button class="primary-button" type="submit" :disabled="isSaving">
            {{ isSaving ? '保存中…' : '保存词书' }}
          </button>
        </div>
      </form>
    </AdminDrawer>
  </div>
</template>

<style scoped src="./WordbookManage.css"></style>
