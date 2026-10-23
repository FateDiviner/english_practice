<script setup>
import { ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { deleteAdminWord, listAdminWords, listAdminWordbooks } from '../../api/admin'
import PagePagination from '../../components/PagePagination.vue'
import WordEditorDrawer from '../../components/admin/WordEditorDrawer.vue'
import { getErrorMessage } from '../../utils/errors'

const PAGE_SIZE = 20
const route = useRoute()
const wordbookId = Number(route.params.id)
const wordbookName = ref('')
const words = ref([])
const total = ref(0)
const page = ref(1)
const searchInput = ref('')
const keyword = ref('')
const isLoading = ref(true)
const errorMessage = ref('')
const noticeMessage = ref('')
const isDrawerOpen = ref(false)
const editingWord = ref(null)
const pendingDeleteId = ref(null)
const deletingId = ref(null)

function openCreate() {
  editingWord.value = null
  isDrawerOpen.value = true
}

function openEdit(word) {
  editingWord.value = word
  isDrawerOpen.value = true
}
async function loadWordbookName() {
  try {
    const result = await listAdminWordbooks({ page: 1, pageSize: 100 })
    wordbookName.value = result.items?.find((book) => book.id === wordbookId)?.name || '当前词书'
  } catch {
    wordbookName.value = '当前词书'
  }
}

async function loadWords() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const result = await listAdminWords(wordbookId, {
      page: page.value,
      pageSize: PAGE_SIZE,
      keyword: keyword.value,
    })
    words.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '单词列表暂时无法读取。')
  } finally {
    isLoading.value = false
  }
}

function applySearch() {
  keyword.value = searchInput.value.trim()
  if (page.value === 1) loadWords()
  else page.value = 1
}

async function handleSaved(message) {
  isDrawerOpen.value = false
  noticeMessage.value = message
  if (!editingWord.value && page.value !== 1) page.value = 1
  else await loadWords()
  editingWord.value = null
}

async function confirmDelete(word) {
  deletingId.value = word.id
  noticeMessage.value = ''
  try {
    await deleteAdminWord(word.id)
    pendingDeleteId.value = null
    noticeMessage.value = '单词已删除。'
    if (words.value.length === 1 && page.value > 1) page.value -= 1
    else await loadWords()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '单词没有删除成功。')
    pendingDeleteId.value = null
  } finally {
    deletingId.value = null
  }
}

watch(page, loadWords, { immediate: true })
loadWordbookName()
</script>

<template>
  <div class="app-page admin-page">
    <RouterLink class="back-link" to="/admin/wordbooks">← 返回词书管理</RouterLink>
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">WORD CATALOGUE</p>
        <h1 class="page-title">{{ wordbookName }} · 单词</h1>
        <p class="page-copy">逐条维护拼写、音标、释义、例句与排序。</p>
      </div>
      <button class="primary-button" type="button" @click="openCreate">新增单词</button>
    </header>

    <form class="search-bar" @submit.prevent="applySearch">
      <input v-model="searchInput" class="field-input" type="search" placeholder="按拼写搜索单词" />
      <button class="secondary-button" type="submit">搜索</button>
    </form>

    <p v-if="noticeMessage" class="inline-notice inline-notice--success admin-notice">
      {{ noticeMessage }}
    </p>
    <p v-if="errorMessage" class="inline-notice inline-notice--error admin-notice" role="alert">
      {{ errorMessage }}
    </p>

    <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入单词">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <section v-else-if="!words.length" class="state-panel state-panel--center">
      <h2 class="state-title">{{ keyword ? '没有找到匹配的单词' : '这本词书还没有单词' }}</h2>
      <p class="state-copy">
        {{
          keyword
            ? '换一个拼写片段，或者清空搜索条件。'
            : '先手动加入一个词，或从导入向导批量导入。'
        }}
      </p>
      <button v-if="!keyword" class="primary-button" type="button" @click="openCreate">
        添加第一个词
      </button>
    </section>

    <div v-else class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>拼写</th>
            <th>音标</th>
            <th>释义</th>
            <th>词性</th>
            <th>排序</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="word in words" :key="word.id">
            <td class="spelling-cell">{{ word.spelling }}</td>
            <td class="phonetic-cell">{{ word.phonetic_uk || word.phonetic_us || '—' }}</td>
            <td>{{ word.meaning_cn || '—' }}</td>
            <td>{{ word.part_of_speech || '—' }}</td>
            <td>{{ word.sort_order }}</td>
            <td>
              <div class="row-actions">
                <button class="text-link" type="button" @click="openEdit(word)">编辑</button>
                <template v-if="pendingDeleteId === word.id">
                  <button
                    class="text-link danger-link"
                    type="button"
                    :disabled="deletingId === word.id"
                    @click="confirmDelete(word)"
                  >
                    {{ deletingId === word.id ? '删除中…' : '确认删除' }}
                  </button>
                  <button class="text-link" type="button" @click="pendingDeleteId = null">
                    取消
                  </button>
                </template>
                <button
                  v-else
                  class="text-link danger-link"
                  type="button"
                  @click="pendingDeleteId = word.id"
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

    <WordEditorDrawer
      :open="isDrawerOpen"
      :word="editingWord"
      :wordbook-id="wordbookId"
      :wordbook-name="wordbookName"
      @close="isDrawerOpen = false"
      @saved="handleSaved"
    />
  </div>
</template>

<style scoped src="./WordManage.css"></style>
