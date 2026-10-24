<script setup>
import { computed } from 'vue'

import { formatPercent, formatPointsPercent } from '../../utils/format'

const props = defineProps({
  agentKey: { type: String, required: true },
  agent: { type: Object, required: true },
})

const titles = {
  data: '数据专家',
  habit: '习惯专家',
  diagnosis: '诊断专家',
  planner: '规划专家',
}
const sourceLabels = { llm: '模型分析', heuristic: '规则统计' }
const severityLabels = { low: '低', medium: '中', high: '高' }

const title = computed(() => titles[props.agentKey] || props.agentKey)
const source = computed(() => sourceLabels[props.agent.source] || props.agent.source)

function minutes(value) {
  return `${(Number(value) || 0).toFixed(1)} 分钟`
}
</script>

<template>
  <section class="agent-card">
    <header class="agent-card__header">
      <div>
        <h4>{{ title }}</h4>
        <p class="agent-card__source">
          {{ source }} · 置信度 {{ formatPercent(agent.confidence) }}
        </p>
      </div>
      <p class="agent-card__summary">{{ agent.summary }}</p>
    </header>

    <div v-if="agent.tags?.length" class="chip-row">
      <span v-for="tag in agent.tags" :key="tag" class="chip">{{ tag }}</span>
    </div>

    <template v-if="agentKey === 'data'">
      <div v-if="agent.accuracy_trend?.length" class="agent-block">
        <h5>正确率趋势</h5>
        <ul class="agent-rows">
          <li v-for="item in agent.accuracy_trend" :key="item.period">
            <span>{{ item.period }}</span>
            <strong>{{ formatPointsPercent(item.accuracy, 1) }}</strong>
            <small>{{ item.session_count }} 次</small>
          </li>
        </ul>
      </div>
      <div v-if="agent.vocabulary_distribution?.length" class="agent-block">
        <h5>词汇分布</h5>
        <ul class="agent-rows">
          <li v-for="item in agent.vocabulary_distribution" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.count }} 词</strong>
            <small>{{ formatPointsPercent(item.percentage, 1) }}</small>
          </li>
        </ul>
      </div>
    </template>

    <template v-if="agentKey === 'habit'">
      <dl class="agent-metrics">
        <div>
          <dt>平均单次</dt>
          <dd>{{ minutes(agent.average_duration_minutes) }}</dd>
        </div>
        <div>
          <dt>累计时长</dt>
          <dd>{{ minutes(agent.total_duration_minutes) }}</dd>
        </div>
        <div>
          <dt>活跃天数</dt>
          <dd>{{ agent.active_days }} 天</dd>
        </div>
        <div>
          <dt>当前连续</dt>
          <dd>{{ agent.current_streak_days }} 天</dd>
        </div>
        <div>
          <dt>最长连续</dt>
          <dd>{{ agent.longest_streak_days }} 天</dd>
        </div>
        <div>
          <dt>偏好时段</dt>
          <dd>{{ agent.preferred_time_slot || '—' }}</dd>
        </div>
      </dl>
      <div v-if="agent.weekly_frequency?.length" class="agent-block">
        <h5>每周练习</h5>
        <ul class="agent-rows">
          <li v-for="item in agent.weekly_frequency" :key="item.week">
            <span>{{ item.week }}</span>
            <strong>{{ item.sessions }} 次</strong>
            <small>{{ item.active_days }} 天活跃</small>
          </li>
        </ul>
      </div>
      <div v-if="agent.checkin_pattern?.length" class="agent-block">
        <h5>星期分布</h5>
        <ul class="agent-rows">
          <li v-for="item in agent.checkin_pattern" :key="item.weekday">
            <span>{{ item.weekday }}</span>
            <strong>{{ item.sessions }} 次</strong>
            <small>{{ formatPointsPercent(item.percentage, 1) }}</small>
          </li>
        </ul>
      </div>
    </template>

    <template v-if="agentKey === 'diagnosis'">
      <div v-if="agent.error_patterns?.length" class="agent-block">
        <h5>错误模式</h5>
        <ul class="agent-rows">
          <li v-for="item in agent.error_patterns" :key="`${item.kind}-${item.label}`">
            <span>{{ item.label }}</span>
            <strong>{{ item.hit_count }} 次</strong>
            <small>严重度 {{ severityLabels[item.severity] || item.severity }}</small>
            <em v-if="item.evidence">{{ item.evidence }}</em>
          </li>
        </ul>
      </div>
      <div v-if="agent.focus_words?.length" class="agent-block">
        <h5>重点词</h5>
        <div class="chip-row">
          <span
            v-for="word in agent.focus_words"
            :key="word.word_id"
            class="chip"
            :class="{ 'chip--muted': word.resolved }"
          >
            {{ word.spelling }} · {{ word.wrong_count }} 次
          </span>
        </div>
      </div>
    </template>

    <template v-if="agentKey === 'planner'">
      <div v-if="agent.review_plan?.length" class="agent-block">
        <h5>七日复习计划</h5>
        <ul class="agent-rows agent-rows--plan">
          <li v-for="item in agent.review_plan" :key="item.day">
            <span>第 {{ item.day }} 天 · {{ item.title }}</span>
            <strong>{{ item.word_count }} 词</strong>
            <small>{{ item.activity }}</small>
            <em v-if="item.focus_words?.length">{{ item.focus_words.join('、') }}</em>
          </li>
        </ul>
      </div>
      <div v-if="agent.weekly_goals?.length" class="agent-block">
        <h5>周目标</h5>
        <ul class="agent-list">
          <li v-for="goal in agent.weekly_goals" :key="goal">{{ goal }}</li>
        </ul>
      </div>
      <div v-if="agent.recommendations?.length" class="agent-block">
        <h5>学习建议</h5>
        <ul class="agent-list">
          <li v-for="item in agent.recommendations" :key="item">{{ item }}</li>
        </ul>
      </div>
    </template>

    <div v-if="agent.highlights?.length" class="agent-block">
      <h5>亮点</h5>
      <ul class="agent-list">
        <li v-for="item in agent.highlights" :key="item">{{ item }}</li>
      </ul>
    </div>
    <div v-if="agent.risks?.length" class="agent-block">
      <h5>风险</h5>
      <ul class="agent-list agent-list--risk">
        <li v-for="item in agent.risks" :key="item">{{ item }}</li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.agent-card {
  padding: 20px 0;
  border-top: 1px solid var(--color-border);
}

.agent-card__header {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  margin-bottom: 14px;
}

.agent-card__header h4 {
  margin: 0 0 4px;
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-md);
}

.agent-card__source {
  margin: 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.agent-card__summary {
  margin: 0;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
  line-height: 1.85;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.chip {
  padding: 2px 8px;
  border: 1px solid var(--color-border);
  color: var(--color-primary);
  font-size: var(--font-size-xs);
}

.chip--muted {
  color: var(--color-disabled);
}

.agent-block {
  margin-top: 14px;
}

.agent-block h5 {
  margin: 0 0 8px;
  color: var(--color-disabled);
  font-family: var(--font-family-body);
  font-size: var(--font-size-xs);
  font-weight: 500;
  letter-spacing: 0.06em;
}

.agent-rows {
  margin: 0;
  padding: 0;
  list-style: none;
}

.agent-rows li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 4px 12px;
  padding: 7px 0;
  border-bottom: 1px dashed var(--color-border);
  font-size: var(--font-size-xs);
}

.agent-rows li strong {
  color: var(--color-primary);
  font-weight: 500;
}

.agent-rows li small {
  color: var(--color-disabled);
}

.agent-rows li em {
  grid-column: 1 / -1;
  color: var(--color-disabled);
  font-style: normal;
}

.agent-rows--plan li {
  grid-template-columns: minmax(0, 1fr) auto;
}

.agent-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 18px;
  margin: 12px 0 0;
}

.agent-metrics div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--color-border);
  font-size: var(--font-size-xs);
}

.agent-metrics dt {
  color: var(--color-disabled);
}

.agent-metrics dd {
  margin: 0;
  color: var(--color-primary);
}

.agent-list {
  margin: 0;
  padding-left: 16px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  line-height: 1.9;
}

.agent-list--risk {
  color: var(--color-danger);
}

@media (max-width: 720px) {
  .agent-card__header {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .agent-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
