<script setup>
import { computed } from 'vue'

const props = defineProps({
  headers: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  errors: { type: Array, default: () => [] },
})

const previewRows = computed(() => props.rows.slice(0, 20))
const visibleErrors = computed(() => props.errors.slice(0, 10))
</script>

<template>
  <div class="import-preview">
    <div class="preview-summary">
      <div>
        <span>识别列数</span>
        <strong>{{ headers.length }}</strong>
      </div>
      <div>
        <span>总行数</span>
        <strong>{{ rows.length }}</strong>
      </div>
      <div>
        <span>校验问题</span>
        <strong :class="{ 'preview-summary__problem': errors.length }">{{ errors.length }}</strong>
      </div>
    </div>

    <div v-if="!rows.length" class="state-panel">
      <h3 class="state-title">没有读到可预览的行</h3>
      <p class="state-copy">请重新选择 CSV 或 TSV 文件，并确认第一行是表头。</p>
    </div>

    <template v-else>
      <div class="data-table-wrap preview-table-wrap">
        <table class="data-table preview-table">
          <thead>
            <tr>
              <th>行</th>
              <th v-for="header in headers" :key="header">{{ header || '未命名列' }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in previewRows" :key="rowIndex">
              <td>{{ rowIndex + 2 }}</td>
              <td v-for="(header, columnIndex) in headers" :key="`${rowIndex}-${header}`">
                {{ row[columnIndex] || '' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="preview-note">仅展示前 20 行，正式导入时会处理全部 {{ rows.length }} 行。</p>
    </template>

    <section v-if="errors.length" class="error-summary">
      <h3>错误摘要</h3>
      <ul>
        <li v-for="error in visibleErrors" :key="`${error.row}-${error.reason}`">
          第 {{ error.row }} 行：{{ error.reason }}
        </li>
      </ul>
      <p v-if="errors.length > visibleErrors.length">
        还有 {{ errors.length - visibleErrors.length }} 条问题未展开。
      </p>
    </section>
  </div>
</template>

<style scoped>
.import-preview {
  display: grid;
  gap: 18px;
}

.preview-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--color-border);
  border-left: 1px solid var(--color-border);
}

.preview-summary > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.preview-summary strong {
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-lg);
}

.preview-summary__problem {
  color: var(--color-error) !important;
}

.preview-table-wrap {
  max-height: 440px;
}

.preview-table {
  min-width: 680px;
  font-size: var(--font-size-xs);
}

.preview-note {
  margin: -8px 0 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.error-summary {
  padding: 16px;
  border-left: 3px solid var(--color-error);
  background: color-mix(in srgb, var(--color-error), transparent 94%);
}

.error-summary h3 {
  margin-bottom: 8px;
  color: var(--color-error);
  font-size: var(--font-size-sm);
}

.error-summary ul {
  margin: 0;
  padding-left: 20px;
  color: var(--color-text);
  font-size: var(--font-size-xs);
}

.error-summary p {
  margin: 8px 0 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

@media (max-width: 620px) {
  .preview-summary {
    grid-template-columns: 1fr;
  }
}
</style>
