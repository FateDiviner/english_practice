<script setup>
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { listWordbooks } from '../../api/wordbooks'
import PagePagination from '../../components/PagePagination.vue'
import { getErrorMessage } from '../../utils/errors'
import { formatPercent } from '../../utils/format'

const PAGE_SIZE = 10
const items = ref([])
const total = ref(0)
const page = ref(1)
const isLoading = ref(true)
const errorMessage = ref('')

async function loadWordbooks() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const result = await listWordbooks({ page: page.value, pageSize: PAGE_SIZE })
    items.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '词书架暂时没有打开，请稍后再试。')
  } finally {
    isLoading.value = false
  }
}

function progressPercent(book) {
  const mastered = Number(book.my_progress?.mastered) || 0
  const totalWords = Number(book.my_progress?.total || book.word_count) || 0
  if (!totalWords) return 0
  return Math.min(100, (mastered / totalWords) * 100)
}

watch(page, loadWordbooks, { immediate: true })
</script>

<template>
  <div class="app-page">
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">THE BOOKSHELF</p>
        <h1 class="page-title">词书架</h1>
        <p class="page-copy">选一本正在学的词书。每一次默写，都会在这条进度线上留下刻度。</p>
      </div>
      <RouterLink class="primary-button" to="/practice">直接开始练习</RouterLink>
    </header>

    <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入词书">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <section v-else-if="errorMessage" class="state-panel">
      <h2 class="state-title">这一页暂时翻不开</h2>
      <p class="state-copy">{{ errorMessage }}</p>
      <button class="secondary-button" type="button" @click="loadWordbooks">重新载入</button>
    </section>

    <section v-else-if="!items.length" class="state-panel state-panel--center">
      <p class="eyebrow">AN EMPTY SHELF</p>
      <h2 class="state-title">书架空着，正好等第一本好书</h2>
      <p class="state-copy">管理员发布词书后，你的练习会从这里开始。</p>
    </section>

    <section v-else class="book-list" aria-label="词书列表">
      <article v-for="(book, index) in items" :key="book.id" class="book-entry">
        <div class="book-entry__number">
          {{ String((page - 1) * PAGE_SIZE + index + 1).padStart(2, '0') }}
        </div>
        <div class="book-entry__body">
          <div class="book-entry__heading">
            <div>
              <p class="book-entry__level">{{ book.level || '综合词书' }}</p>
              <RouterLink :to="`/wordbooks/${book.id}`" class="book-entry__name">
                {{ book.name }}
              </RouterLink>
            </div>
            <span class="book-entry__count">{{ book.word_count }} 词</span>
          </div>
          <p class="book-entry__description">
            {{ book.description || '一词一页，慢慢写，也会走得很远。' }}
          </p>
          <div class="book-entry__progress">
            <div class="book-entry__progress-copy">
              <span>掌握进度</span>
              <strong>
                {{ book.my_progress?.mastered || 0 }} /
                {{ book.my_progress?.total || book.word_count }}
                <small>{{ formatPercent(progressPercent(book) / 100) }}</small>
              </strong>
            </div>
            <div class="book-entry__track" aria-hidden="true">
              <span :style="{ width: `${progressPercent(book)}%` }"></span>
            </div>
          </div>
        </div>
        <div class="book-entry__actions">
          <RouterLink class="secondary-button" :to="`/wordbooks/${book.id}`">查看单词</RouterLink>
          <RouterLink
            class="primary-button"
            :to="{ name: 'practice', query: { wordbook_id: book.id } }"
          >
            开始默写
          </RouterLink>
        </div>
      </article>
    </section>

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

.book-list {
  margin-top: 16px;
  border-top: 1px solid var(--color-border);
}

.book-entry {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) auto;
  gap: 24px;
  align-items: center;
  padding: 26px 8px;
  border-bottom: 1px solid var(--color-border);
}

.book-entry__number {
  align-self: flex-start;
  padding-top: 4px;
  color: var(--color-accent);
  font-family: var(--font-family-title);
  font-size: var(--font-size-sm);
}

.book-entry__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.book-entry__level {
  margin-bottom: 5px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  letter-spacing: 0.08em;
}

.book-entry__name {
  color: var(--color-text);
  font-family: var(--font-family-title);
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.book-entry__name:hover {
  color: var(--color-primary);
}

.book-entry__count {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}

.book-entry__description {
  margin: 9px 0 18px;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.book-entry__progress {
  max-width: 470px;
}

.book-entry__progress-copy {
  display: flex;
  justify-content: space-between;
  margin-bottom: 7px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.book-entry__progress-copy strong {
  color: var(--color-primary);
  font-weight: 500;
}

.book-entry__progress-copy small {
  margin-left: 7px;
  color: var(--color-accent);
}

.book-entry__track {
  height: 2px;
  background: var(--color-border);
}

.book-entry__track span {
  display: block;
  height: 100%;
  background: var(--color-accent);
}

.book-entry__actions {
  display: flex;
  gap: 10px;
}

.book-entry__actions a:hover {
  text-decoration: none;
}

@media (max-width: 980px) {
  .book-entry {
    grid-template-columns: 38px 1fr;
  }

  .book-entry__actions {
    grid-column: 2;
  }
}

@media (max-width: 620px) {
  .book-entry {
    gap: 12px;
  }

  .book-entry__heading {
    flex-direction: column;
    gap: 4px;
  }

  .book-entry__actions {
    flex-direction: column;
  }

  .book-entry__actions a {
    text-align: center;
  }
}
</style>
