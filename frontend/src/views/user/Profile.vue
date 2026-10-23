<script setup>
import { computed, onMounted, ref } from 'vue'

import { getStatsDaily, getStatsOverview } from '../../api/stats'
import LineChart from '../../components/LineChart.vue'
import Sparkline from '../../components/Sparkline.vue'
import { useAuthStore } from '../../stores/auth'
import { getErrorMessage } from '../../utils/errors'
import {
  buildDateRange,
  formatDate,
  formatPercent,
  getInitial,
  getJoinDays,
  toIsoDate,
} from '../../utils/format'

const authStore = useAuthStore()
const overview = ref(null)
const dailyItems = ref([])
const rangeDays = ref(7)
const isLoading = ref(true)
const errorMessage = ref('')

const username = computed(() => authStore.user?.username || '同学')
const joinedAt = computed(() => authStore.user?.created_at)
const joinDays = computed(() => getJoinDays(joinedAt.value))
const dateSeries = computed(() => {
  const series = []
  const end = new Date()
  for (let offset = rangeDays.value - 1; offset >= 0; offset -= 1) {
    const date = new Date(end)
    date.setDate(end.getDate() - offset)
    series.push(toIsoDate(date))
  }
  return series
})
const chartItems = computed(() => {
  const byDate = new Map(dailyItems.value.map((item) => [item.date, item]))
  return dateSeries.value.map((date) => ({
    date,
    answered: Number(byDate.get(date)?.answered) || 0,
    correct: Number(byDate.get(date)?.correct) || 0,
  }))
})
const trendValues = computed(() => chartItems.value.map((item) => item.answered))
const metrics = computed(() => [
  {
    label: '累计默写',
    value: overview.value?.total_practiced ?? 0,
    unit: '题',
    note: '每一次作答都被记在账上',
  },
  {
    label: '总体正确率',
    value: overview.value ? formatPercent(overview.value.accuracy) : '0%',
    unit: '',
    note: '稳定，比一次漂亮更重要',
  },
  {
    label: '连续练习',
    value: overview.value?.streak_days ?? 0,
    unit: '天',
    note: '今天也来写一组吧',
  },
  {
    label: '已掌握词数',
    value: overview.value?.mastered_words ?? 0,
    unit: '词',
    note: '连续答对两次，就会留下记号',
  },
  {
    label: '未解决错词',
    value: overview.value?.wrong_words_count ?? 0,
    unit: '词',
    note: '它们正等着被你重新写下',
  },
])
const achievements = computed(() => [
  { name: '落笔', code: 'BEGIN', earned: (overview.value?.total_practiced || 0) >= 1 },
  { name: '三日不辍', code: 'STREAK', earned: (overview.value?.streak_days || 0) >= 3 },
  { name: '百题成册', code: 'HUNDRED', earned: (overview.value?.total_practiced || 0) >= 100 },
  {
    name: '准确如衡',
    code: 'PRECISION',
    earned: (overview.value?.total_practiced || 0) >= 10 && (overview.value?.accuracy || 0) >= 0.9,
  },
  {
    name: '错词克星',
    code: 'REVISED',
    earned:
      (overview.value?.total_practiced || 0) > 0 && (overview.value?.wrong_words_count || 0) === 0,
  },
  { name: '十词入心', code: 'MASTERED', earned: (overview.value?.mastered_words || 0) >= 10 },
])

async function loadProfile() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const [overviewResult, dailyResult] = await Promise.all([
      getStatsOverview(),
      getStatsDaily(buildDateRange(rangeDays.value)),
    ])
    overview.value = overviewResult
    dailyItems.value = dailyResult.items || []
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '学习账本暂时没有打开，请稍后再试。')
  } finally {
    isLoading.value = false
  }
}

function changeRange(days) {
  if (rangeDays.value === days) return
  rangeDays.value = days
  loadProfile()
}

onMounted(loadProfile)
</script>

<template>
  <div class="app-page profile-page">
    <header class="profile-hero">
      <div class="profile-avatar">{{ getInitial(username) }}</div>
      <div class="profile-hero__copy">
        <p class="eyebrow">MY LEARNING LEDGER</p>
        <h1>{{ username }}</h1>
        <p>
          加入墨痕的第 {{ joinDays }} 天
          <span v-if="joinedAt"> · {{ formatDate(joinedAt) }} 起</span>
        </p>
      </div>
      <RouterLink class="secondary-button" to="/practice">继续练习</RouterLink>
    </header>

    <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入学习账本">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <section v-else-if="errorMessage" class="state-panel">
      <h2 class="state-title">账本暂时没有打开</h2>
      <p class="state-copy">{{ errorMessage }}</p>
      <button class="secondary-button" type="button" @click="loadProfile">重新载入</button>
    </section>

    <template v-else>
      <p v-if="!overview?.total_practiced" class="inline-notice profile-empty-note">
        账本还是崭新的一页。完成第一组默写后，这里会留下第一条记录。
      </p>

      <section class="profile-grid">
        <article class="ledger surface">
          <div class="section-heading">
            <div>
              <p class="eyebrow">MONTHLY ACCOUNT</p>
              <h2>学习账本</h2>
            </div>
            <span>近 {{ rangeDays }} 天</span>
          </div>
          <dl class="ledger__rows">
            <div v-for="metric in metrics" :key="metric.label" class="ledger__row">
              <dt>
                <span>{{ metric.label }}</span>
                <small>{{ metric.note }}</small>
              </dt>
              <dd>
                {{ metric.value }}<small>{{ metric.unit }}</small>
              </dd>
              <Sparkline :values="trendValues" />
            </div>
          </dl>
        </article>

        <article class="trend surface">
          <div class="section-heading">
            <div>
              <p class="eyebrow">DAILY TRACE</p>
              <h2>练习趋势</h2>
            </div>
            <div class="range-switch" role="group" aria-label="趋势范围">
              <button
                type="button"
                :class="{ 'range-switch__item--active': rangeDays === 7 }"
                @click="changeRange(7)"
              >
                7 天
              </button>
              <button
                type="button"
                :class="{ 'range-switch__item--active': rangeDays === 30 }"
                @click="changeRange(30)"
              >
                30 天
              </button>
            </div>
          </div>
          <LineChart :items="chartItems" />
        </article>
      </section>

      <section class="achievements">
        <div class="section-heading">
          <div>
            <p class="eyebrow">COLLECTED MARKS</p>
            <h2>印章墙</h2>
          </div>
          <span
            >{{ achievements.filter((item) => item.earned).length }} /
            {{ achievements.length }} 已得</span
          >
        </div>
        <div class="stamp-wall">
          <article
            v-for="achievement in achievements"
            :key="achievement.code"
            class="stamp"
            :class="{ 'stamp--earned': achievement.earned }"
          >
            <span class="stamp__seal">{{ achievement.earned ? '得' : '待' }}</span>
            <strong>{{ achievement.name }}</strong>
            <small>{{ achievement.code }}</small>
          </article>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped src="./Profile.css"></style>
