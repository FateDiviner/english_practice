<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { getStatsOverview } from '../../api/stats'
import { listWordbooks } from '../../api/wordbooks'
import { useAuthStore } from '../../stores/auth'
import { formatPercent } from '../../utils/format'

const authStore = useAuthStore()
const overview = ref(null)
const wordbooks = ref([])
const isLoading = ref(true)

const username = computed(() => authStore.user?.username || '同学')
const todayLabel = new Intl.DateTimeFormat('zh-CN', {
  month: 'long',
  day: 'numeric',
  weekday: 'long',
}).format(new Date())

onMounted(async () => {
  const [overviewResult, wordbookResult] = await Promise.allSettled([
    getStatsOverview(),
    listWordbooks({ page: 1, pageSize: 3 }),
  ])
  if (overviewResult.status === 'fulfilled') overview.value = overviewResult.value
  if (wordbookResult.status === 'fulfilled') wordbooks.value = wordbookResult.value.items || []
  isLoading.value = false
})
</script>

<template>
  <div class="app-page home-page">
    <section class="home-hero">
      <div class="home-hero__copy">
        <p class="eyebrow">{{ todayLabel }} · 今日练习</p>
        <h1>你好，{{ username }}。<br />把今天的词，写稳一点。</h1>
        <p>不必追求一次记住。每天十个词，写下来、读出来，让记忆在纸面上留下痕迹。</p>
        <div class="home-hero__actions">
          <RouterLink class="primary-button" to="/wordbooks">挑选一本词书</RouterLink>
          <RouterLink class="ghost-button" to="/wrong-words">复习错词</RouterLink>
        </div>
      </div>

      <aside class="today-ledger surface">
        <p class="today-ledger__label">TODAY'S LEDGER</p>
        <dl>
          <div>
            <dt>累计默写</dt>
            <dd>{{ overview?.total_practiced ?? '—' }}</dd>
          </div>
          <div>
            <dt>总体正确率</dt>
            <dd>{{ overview ? formatPercent(overview.accuracy) : '—' }}</dd>
          </div>
          <div>
            <dt>连续练习</dt>
            <dd>{{ overview?.streak_days ?? '—' }}<small>天</small></dd>
          </div>
        </dl>
        <RouterLink to="/profile">查看完整学习账本</RouterLink>
      </aside>
    </section>

    <section class="home-section">
      <div class="home-section__heading">
        <div>
          <p class="eyebrow">OPEN A BOOK</p>
          <h2>从一本词书开始</h2>
        </div>
        <RouterLink to="/wordbooks">全部词书</RouterLink>
      </div>

      <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入">
        <span class="skeleton-line"></span>
        <span class="skeleton-line"></span>
        <span class="skeleton-line"></span>
      </div>
      <div v-else-if="wordbooks.length" class="book-lines">
        <RouterLink
          v-for="(book, index) in wordbooks"
          :key="book.id"
          :to="`/wordbooks/${book.id}`"
          class="book-line"
        >
          <span class="book-line__index">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="book-line__title">
            <strong>{{ book.name }}</strong>
            <small>{{ book.description || '按自己的节奏，一页一页写下去。' }}</small>
          </span>
          <span class="book-line__meta">{{ book.word_count }} 词</span>
          <span class="book-line__arrow" aria-hidden="true">→</span>
        </RouterLink>
      </div>
      <div v-else class="state-panel">
        <h3 class="state-title">词书架还在等第一本书</h3>
        <p class="state-copy">管理员发布词书后，这里会出现你的下一段练习。</p>
      </div>
    </section>

    <section class="home-bottom">
      <RouterLink class="practice-note" to="/practice">
        <span class="eyebrow">QUICK PRACTICE</span>
        <h2>随手默写十个词</h2>
        <p>从已发布词书中选一本，现在就开始。</p>
        <span class="text-link">进入练习 →</span>
      </RouterLink>
      <RouterLink class="ai-note" to="/ai-chat">
        <span class="ai-note__badge">即将上线</span>
        <span class="eyebrow">AI CONVERSATION</span>
        <h2>把学到的词带进对话</h2>
        <p>自由对话与情景练习正在筹备中。</p>
      </RouterLink>
    </section>
  </div>
</template>

<style scoped src="./Home.css"></style>
