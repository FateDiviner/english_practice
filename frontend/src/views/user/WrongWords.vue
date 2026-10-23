<script setup>
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { listWrongWords, removeWrongWord } from '../../api/wrongWords'
import AudioButton from '../../components/AudioButton.vue'
import PagePagination from '../../components/PagePagination.vue'
import { getErrorMessage } from '../../utils/errors'
import { formatDate } from '../../utils/format'

const PAGE_SIZE = 20
const items = ref([])
const total = ref(0)
const page = ref(1)
const resolved = ref(false)
const isLoading = ref(true)
const errorMessage = ref('')
const actionError = ref('')
const pendingRemovalId = ref(null)
const removingId = ref(null)

async function loadWrongWords() {
  isLoading.value = true
  errorMessage.value = ''
  actionError.value = ''
  try {
    const result = await listWrongWords({
      page: page.value,
      pageSize: PAGE_SIZE,
      resolved: resolved.value,
    })
    items.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '错词本暂时没有打开，请稍后再试。')
  } finally {
    isLoading.value = false
  }
}

function changeFilter(nextResolved) {
  resolved.value = nextResolved
  if (page.value === 1) loadWrongWords()
  else page.value = 1
}

async function confirmRemove(wordId) {
  if (removingId.value) return
  removingId.value = wordId
  actionError.value = ''
  try {
    await removeWrongWord(wordId)
    pendingRemovalId.value = null
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    else await loadWrongWords()
  } catch (error) {
    actionError.value = getErrorMessage(error, '这个词暂时没有移除，请稍后再试。')
  } finally {
    removingId.value = null
  }
}

watch(page, loadWrongWords, { immediate: true })
</script>

<template>
  <div class="app-page">
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">THE MARGIN NOTES</p>
        <h1 class="page-title">错词本</h1>
        <p class="page-copy">错过的词不是污点，是下一次默写时最该停留的地方。</p>
      </div>
      <RouterLink
        class="primary-button"
        :to="{ name: 'practice', query: { mode: 'wrong_only', count: 10 } }"
      >
        重练错词
      </RouterLink>
    </header>

    <div class="wrong-toolbar">
      <div class="filter-switch" role="group" aria-label="错词状态筛选">
        <button
          type="button"
          :class="{ 'filter-switch__item--active': !resolved }"
          @click="changeFilter(false)"
        >
          待攻克
        </button>
        <button
          type="button"
          :class="{ 'filter-switch__item--active': resolved }"
          @click="changeFilter(true)"
        >
          已解决
        </button>
      </div>
      <span>共 {{ total }} 个词</span>
    </div>

    <p v-if="actionError" class="inline-notice inline-notice--error" role="alert">
      {{ actionError }}
    </p>

    <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入错词">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <section v-else-if="errorMessage" class="state-panel">
      <h2 class="state-title">这一页暂时翻不开</h2>
      <p class="state-copy">{{ errorMessage }}</p>
      <button class="secondary-button" type="button" @click="loadWrongWords">重新载入</button>
    </section>

    <section v-else-if="!items.length" class="state-panel state-panel--center">
      <p class="eyebrow">{{ resolved ? 'CLEARED' : 'A CLEAN PAGE' }}</p>
      <h2 class="state-title">
        {{ resolved ? '还没有已经解决的词' : '这一页很干净，继续保持' }}
      </h2>
      <p class="state-copy">
        {{
          resolved
            ? '连续答对两次后，词会出现在这里。'
            : '去词书架开始一轮默写，错词会自动记在这里。'
        }}
      </p>
    </section>

    <div v-else class="data-table-wrap">
      <table class="data-table wrong-table">
        <thead>
          <tr>
            <th>单词</th>
            <th>音标</th>
            <th>释义</th>
            <th>错误次数</th>
            <th>最近错误</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="word in items" :key="word.word_id">
            <td class="wrong-table__word">{{ word.spelling }}</td>
            <td class="wrong-table__phonetic">{{ word.phonetic_uk || word.phonetic_us || '—' }}</td>
            <td>{{ word.meaning_cn || '释义待补充' }}</td>
            <td>
              <span class="wrong-count">{{ word.wrong_count }} 次</span>
            </td>
            <td class="wrong-table__date">{{ formatDate(word.last_wrong_at, true) }}</td>
            <td>
              <div class="row-actions">
                <AudioButton :word-id="word.word_id" :label="word.spelling" compact />
                <template v-if="pendingRemovalId === word.word_id">
                  <button
                    class="danger-button table-action"
                    type="button"
                    :disabled="removingId === word.word_id"
                    @click="confirmRemove(word.word_id)"
                  >
                    {{ removingId === word.word_id ? '移除中…' : '确认移除' }}
                  </button>
                  <button class="text-link" type="button" @click="pendingRemovalId = null">
                    取消
                  </button>
                </template>
                <button
                  v-else
                  class="text-link danger-link"
                  type="button"
                  @click="pendingRemovalId = word.word_id"
                >
                  移除
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
  </div>
</template>

<style scoped>
.page-header > a:hover {
  text-decoration: none;
}

.wrong-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 0 14px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.filter-switch {
  display: flex;
  gap: 20px;
}

.filter-switch button {
  padding: 3px 0 6px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.filter-switch__item--active {
  border-bottom-color: var(--color-accent) !important;
  color: var(--color-text) !important;
}

.inline-notice {
  margin-bottom: 16px;
}

.wrong-table__word {
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.wrong-table__phonetic {
  color: var(--color-disabled);
  font-family: var(--font-family-title);
}

.wrong-count {
  color: var(--color-error);
  font-family: var(--font-family-title);
}

.wrong-table__date {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}

.table-action {
  min-height: 28px;
  padding: 3px 8px;
  font-size: var(--font-size-xs);
}

.danger-link {
  color: var(--color-error);
  font-size: var(--font-size-xs);
}

@media (max-width: 620px) {
  .wrong-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
