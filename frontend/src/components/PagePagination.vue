<script setup>
import { computed } from 'vue'

const props = defineProps({
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  total: { type: Number, default: 0 },
})

const emit = defineEmits(['update:page'])
const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

function goTo(nextPage) {
  if (nextPage < 1 || nextPage > totalPages.value || nextPage === props.page) return
  emit('update:page', nextPage)
}
</script>

<template>
  <nav class="pagination" aria-label="分页">
    <span class="pagination__summary">
      共 {{ total }} 条，第 {{ page }} / {{ totalPages }} 页
    </span>
    <div class="pagination__actions">
      <button
        class="pagination__button"
        type="button"
        :disabled="page <= 1"
        @click="goTo(page - 1)"
      >
        上一页
      </button>
      <button
        class="pagination__button"
        type="button"
        :disabled="page >= totalPages"
        @click="goTo(page + 1)"
      >
        下一页
      </button>
    </div>
  </nav>
</template>
