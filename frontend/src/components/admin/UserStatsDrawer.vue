<script setup>
import AdminDrawer from '../AdminDrawer.vue'
import { formatPercent } from '../../utils/format'
import ProfileReport from './ProfileReport.vue'

defineProps({
  open: { type: Boolean, default: false },
  user: { type: Object, default: null },
  stats: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  profile: { type: Object, default: null },
  profileLoading: { type: Boolean, default: false },
  profileError: { type: String, default: '' },
})

defineEmits(['close', 'load-profile'])
</script>

<template>
  <AdminDrawer
    :open="open"
    title="用户学习数据"
    :description="user ? `正在查看：${user.username}` : ''"
    @close="$emit('close')"
  >
    <div v-if="loading" class="skeleton-stack" aria-label="正在读取用户数据">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>
    <p v-else-if="error" class="inline-notice inline-notice--error" role="alert">{{ error }}</p>
    <dl v-else class="user-stats">
      <div>
        <dt>累计默写</dt>
        <dd>{{ stats?.total_practiced ?? 0 }} 题</dd>
      </div>
      <div>
        <dt>总体正确率</dt>
        <dd>{{ formatPercent(stats?.accuracy || 0) }}</dd>
      </div>
      <div>
        <dt>连续练习</dt>
        <dd>{{ stats?.streak_days ?? 0 }} 天</dd>
      </div>
      <div>
        <dt>已掌握词数</dt>
        <dd>{{ stats?.mastered_words ?? 0 }} 词</dd>
      </div>
      <div>
        <dt>未解决错词</dt>
        <dd>{{ stats?.wrong_words_count ?? 0 }} 词</dd>
      </div>
    </dl>

    <div class="profile-action">
      <button
        class="secondary-button"
        type="button"
        :disabled="profileLoading"
        @click="$emit('load-profile')"
      >
        {{ profileLoading ? '分析中…' : profile ? '重新生成学情画像' : '生成学情画像' }}
      </button>
      <p class="profile-action__help">
        汇总数据、习惯、诊断、规划四位专家的分析，结果会缓存 6 小时。
      </p>
    </div>

    <div v-if="profileLoading" class="skeleton-stack" aria-label="正在生成学情画像">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>
    <p v-else-if="profileError" class="inline-notice inline-notice--error" role="alert">
      {{ profileError }}
    </p>
    <ProfileReport v-else-if="profile" :profile="profile" />
  </AdminDrawer>
</template>

<style scoped>
.user-stats {
  margin: 0;
  border-top: 1px solid var(--color-border);
}

.user-stats > div {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border);
}

.user-stats dt {
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.user-stats dd {
  margin: 0;
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-md);
}

.profile-action {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border);
}

.profile-action__help {
  margin: 8px 0 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  line-height: 1.8;
}
</style>
