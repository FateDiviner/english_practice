<script setup>
import { computed, onMounted, ref } from 'vue'

import { getAdminOverview } from '../../api/admin'
import { getErrorMessage } from '../../utils/errors'

const overview = ref(null)
const isLoading = ref(true)
const errorMessage = ref('')

const metrics = computed(() => [
  {
    label: '总用户数',
    value: overview.value?.total_users ?? 0,
    unit: '人',
    note: '平台累计注册账户',
  },
  {
    label: '活跃用户',
    value: overview.value?.active_users ?? 0,
    unit: '人',
    note: '近 7 天有练习记录',
  },
  {
    label: '总词书数',
    value: overview.value?.total_wordbooks ?? 0,
    unit: '本',
    note: '包含全部状态词书',
  },
  {
    label: '总单词数',
    value: overview.value?.total_words ?? 0,
    unit: '词',
    note: '所有词书词汇总量',
  },
  {
    label: '今日练习',
    value: overview.value?.today_sessions ?? 0,
    unit: '次',
    note: '按上海自然日统计',
  },
  {
    label: '今日答题',
    value: overview.value?.today_answers ?? 0,
    unit: '题',
    note: '今日全部作答记录',
  },
])

async function loadOverview() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    overview.value = await getAdminOverview()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '概览数据暂时无法读取，请稍后再试。')
  } finally {
    isLoading.value = false
  }
}

onMounted(loadOverview)
</script>

<template>
  <div class="app-page admin-page">
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">THE REGISTRY</p>
        <h1 class="page-title">数据概览</h1>
        <p class="page-copy">从用户、内容到今日练习量，一览当前平台的工作状态。</p>
      </div>
      <button class="secondary-button" type="button" :disabled="isLoading" @click="loadOverview">
        {{ isLoading ? '读取中…' : '刷新数据' }}
      </button>
    </header>

    <div v-if="isLoading" class="skeleton-stack" aria-label="正在读取概览">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <section v-else-if="errorMessage" class="state-panel">
      <h2 class="state-title">登记簿暂时没有翻开</h2>
      <p class="state-copy">{{ errorMessage }}</p>
      <button class="secondary-button" type="button" @click="loadOverview">重新读取</button>
    </section>

    <template v-else>
      <section class="metric-grid" aria-label="六项平台指标">
        <article v-for="(metric, index) in metrics" :key="metric.label" class="metric">
          <span class="metric__index">{{ String(index + 1).padStart(2, '0') }}</span>
          <div class="metric__value">
            {{ metric.value }}<small>{{ metric.unit }}</small>
          </div>
          <h2>{{ metric.label }}</h2>
          <p>{{ metric.note }}</p>
        </article>
      </section>

      <footer class="overview-note">
        <span class="overview-note__rule"></span>
        <p>
          数据来自聚合查询。今日指标按 Asia/Shanghai 自然日计算，活跃用户以近 7 天练习记录为准。
        </p>
        <span class="overview-note__date">LIVE LEDGER</span>
      </footer>
    </template>
  </div>
</template>

<style scoped>
.admin-page {
  padding-top: 36px;
}

.page-header > button:hover:not(:disabled) {
  text-decoration: none;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin-top: 30px;
  border-top: 1px solid var(--color-border);
  border-left: 1px solid var(--color-border);
}

.metric {
  min-height: 200px;
  padding: 24px;
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.metric__index {
  color: var(--color-accent);
  font-family: var(--font-family-title);
  font-size: var(--font-size-xs);
}

.metric__value {
  margin-top: 22px;
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-xl);
}

.metric__value small {
  margin-left: 4px;
  color: var(--color-disabled);
  font-family: var(--font-family-body);
  font-size: var(--font-size-xs);
}

.metric h2 {
  margin: 7px 0 4px;
  font-size: var(--font-size-md);
}

.metric p {
  margin-bottom: 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.overview-note {
  display: grid;
  grid-template-columns: 80px 1fr auto;
  align-items: center;
  gap: 20px;
  margin-top: 28px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.overview-note__rule {
  height: 1px;
  background: var(--color-border);
}

.overview-note p {
  margin: 0;
}

.overview-note__date {
  color: var(--color-accent);
  letter-spacing: 0.1em;
}

@media (max-width: 900px) {
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 560px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .metric {
    min-height: auto;
  }

  .overview-note {
    grid-template-columns: 36px 1fr;
  }

  .overview-note__date {
    display: none;
  }
}
</style>
