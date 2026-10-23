<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

const props = defineProps({
  job: { type: Object, default: null },
  error: { type: String, default: '' },
  fallbackTotal: { type: Number, default: 0 },
})

defineEmits(['restart'])
const statusLabel = computed(() => {
  const labels = { pending: '排队中', processing: '处理中', done: '已完成', failed: '失败' }
  return labels[props.job?.status] || '处理中'
})
</script>

<template>
  <div>
    <div class="step-heading">
      <span>STEP 05</span>
      <h2>{{ statusLabel }}</h2>
      <p>任务提交后可以离开，结果会保留在导入记录中。</p>
    </div>
    <div class="job-status" :class="`job-status--${job?.status || 'pending'}`">
      <div>
        <span>状态</span><strong>{{ statusLabel }}</strong>
      </div>
      <div>
        <span>总行数</span><strong>{{ job?.total_rows ?? fallbackTotal }}</strong>
      </div>
      <div>
        <span>成功</span><strong>{{ job?.success_rows ?? 0 }}</strong>
      </div>
      <div>
        <span>失败</span><strong>{{ job?.failed_rows ?? 0 }}</strong>
      </div>
    </div>
    <p v-if="error" class="inline-notice inline-notice--error" role="alert">{{ error }}</p>
    <div v-if="job?.errors?.length" class="job-errors">
      <h3>失败行明细</h3>
      <ul>
        <li v-for="item in job.errors" :key="`${item.row}-${item.reason}`">
          第 {{ item.row }} 行 · {{ item.content || '—' }} · {{ item.reason }}
        </li>
      </ul>
    </div>
    <div class="step-actions">
      <button class="secondary-button" type="button" @click="$emit('restart')">再导一批</button>
      <RouterLink class="primary-button" to="/admin/wordbooks">返回词书管理</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.job-status {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-top: 1px solid var(--color-border);
  border-left: 1px solid var(--color-border);
}

.job-status > div {
  display: grid;
  gap: 4px;
  padding: 18px;
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

.job-status span {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.job-status strong {
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-xl);
}

.job-status--failed strong {
  color: var(--color-error);
}

.job-errors {
  margin-top: 20px;
  padding: 16px;
  border-left: 3px solid var(--color-error);
  background: color-mix(in srgb, var(--color-error), transparent 95%);
}

.job-errors h3 {
  color: var(--color-error);
  font-size: var(--font-size-sm);
}

.job-errors ul {
  margin: 0;
  padding-left: 20px;
  font-size: var(--font-size-xs);
}

.step-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 20px;
}

.step-actions a:hover {
  text-decoration: none;
}

@media (max-width: 720px) {
  .job-status {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
