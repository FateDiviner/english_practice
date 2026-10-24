<script setup>
import { computed } from 'vue'

import { formatDate, formatPercent } from '../../utils/format'
import ProfileAgentSection from './ProfileAgentSection.vue'

const props = defineProps({
  profile: { type: Object, required: true },
})

const levelLabels = {
  excellent: '优秀',
  good: '良好',
  developing: '发展中',
  needs_attention: '需要关注',
  insufficient_data: '数据不足',
}

const agentKeys = ['data', 'habit', 'diagnosis', 'planner']

const availableAgents = computed(() => agentKeys.filter((key) => props.profile.agents?.[key]))

function barWidth(score) {
  return `${Math.max(0, Math.min(100, Number(score) || 0))}%`
}
</script>

<template>
  <article class="profile-report">
    <header class="profile-report__head">
      <div>
        <p class="eyebrow">LEARNING PORTRAIT</p>
        <h3>{{ profile.summary.headline }}</h3>
        <div class="chip-row">
          <span class="chip chip--level">
            {{ levelLabels[profile.summary.level] || profile.summary.level }}
          </span>
          <span class="chip">置信度 {{ formatPercent(profile.summary.confidence) }}</span>
          <span class="chip">{{ profile.cache.hit ? '命中缓存' : '实时生成' }}</span>
        </div>
      </div>
      <p class="profile-report__time">
        生成于 {{ formatDate(profile.generated_at, true) }}<br />
        缓存至 {{ formatDate(profile.cache.expires_at, true) }}
      </p>
    </header>

    <div v-if="profile.summary.tags?.length" class="chip-row">
      <span v-for="tag in profile.summary.tags" :key="tag" class="chip">{{ tag }}</span>
    </div>

    <section class="profile-block">
      <h4>能力指标</h4>
      <ul class="metric-bars">
        <li v-for="metric in profile.summary.radar_metrics" :key="metric.key">
          <span class="metric-bars__label">{{ metric.label }}</span>
          <span class="metric-bars__track" aria-hidden="true">
            <i :style="{ width: barWidth(metric.score) }"></i>
          </span>
          <strong>{{ metric.score }}</strong>
        </li>
      </ul>
    </section>

    <section
      v-if="profile.summary.highlights?.length || profile.summary.risks?.length"
      class="profile-block profile-block--insights"
    >
      <div v-if="profile.summary.highlights?.length">
        <h4>亮点</h4>
        <ul class="insight-list">
          <li v-for="item in profile.summary.highlights" :key="item">{{ item }}</li>
        </ul>
      </div>
      <div v-if="profile.summary.risks?.length">
        <h4>风险</h4>
        <ul class="insight-list insight-list--risk">
          <li v-for="item in profile.summary.risks" :key="item">{{ item }}</li>
        </ul>
      </div>
    </section>

    <section class="profile-block">
      <h4>数据覆盖</h4>
      <dl class="coverage-grid">
        <div>
          <dt>有进度的词</dt>
          <dd>{{ profile.coverage.word_progress_count }}</dd>
        </div>
        <div>
          <dt>未解决错词</dt>
          <dd>{{ profile.coverage.wrong_word_count }}</dd>
        </div>
        <div>
          <dt>练习次数</dt>
          <dd>{{ profile.coverage.practice_session_count }}</dd>
        </div>
      </dl>
      <p class="profile-report__range">
        首次练习：{{ formatDate(profile.coverage.first_practice_at, true) }} · 最近练习：{{
          formatDate(profile.coverage.last_practice_at, true)
        }}
      </p>
    </section>

    <ProfileAgentSection
      v-for="key in availableAgents"
      :key="key"
      :agent-key="key"
      :agent="profile.agents[key]"
    />
  </article>
</template>

<style scoped>
.profile-report {
  margin-top: 22px;
}

.profile-report__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}

.profile-report__head h3 {
  margin: 4px 0 10px;
  font-family: var(--font-family-title);
  font-size: var(--font-size-lg);
}

.profile-report__time {
  flex: 0 0 auto;
  margin: 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  line-height: 1.8;
  text-align: right;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.chip {
  padding: 2px 8px;
  border: 1px solid var(--color-border);
  color: var(--color-primary);
  font-size: var(--font-size-xs);
}

.chip--level {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.profile-block {
  padding: 18px 0;
  border-bottom: 1px solid var(--color-border);
}

.profile-block h4 {
  margin: 0 0 12px;
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-md);
}

.profile-block--insights {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.insight-list {
  margin: 0;
  padding-left: 16px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  line-height: 1.9;
}

.insight-list--risk {
  color: var(--color-danger);
}

.metric-bars {
  display: grid;
  gap: 9px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.metric-bars li {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr) 34px;
  gap: 12px;
  align-items: center;
}

.metric-bars__label {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.metric-bars__track {
  display: block;
  height: 3px;
  background: var(--color-border);
}

.metric-bars__track i {
  display: block;
  height: 100%;
  background: var(--color-accent);
}

.metric-bars strong {
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 500;
  text-align: right;
}

.coverage-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 0;
}

.coverage-grid dt {
  margin-bottom: 4px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.coverage-grid dd {
  margin: 0;
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-lg);
}

.profile-report__range {
  margin: 12px 0 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

@media (max-width: 640px) {
  .profile-report__head {
    flex-direction: column;
  }

  .profile-report__time {
    text-align: left;
  }

  .profile-block--insights,
  .coverage-grid {
    grid-template-columns: 1fr;
  }
}
</style>
