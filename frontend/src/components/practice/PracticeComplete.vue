<script setup>
import { RouterLink } from 'vue-router'

import { formatDuration, formatPointsPercent } from '../../utils/format'

defineProps({
  summary: { type: Object, required: true },
  mode: { type: String, default: 'normal' },
})

defineEmits(['replay'])
</script>

<template>
  <section class="complete surface">
    <div class="complete__stamp" aria-label="本轮完成">
      <span>完成</span>
      <small>COMPLETE</small>
    </div>
    <p class="eyebrow">THIS PAGE IS FINISHED</p>
    <h1>这一轮，写完了。</h1>
    <p class="complete__copy">
      {{ mode === 'wrong_only' ? '错词正在被一个个攻克。' : '每一个认真写下的词，都算数。' }}
    </p>

    <dl class="complete__metrics">
      <div>
        <dt>正确率</dt>
        <dd>{{ formatPointsPercent(summary.accuracy) }}</dd>
      </div>
      <div>
        <dt>答对</dt>
        <dd>
          {{ summary.correct }}<small>/ {{ summary.total }}</small>
        </dd>
      </div>
      <div>
        <dt>用时</dt>
        <dd>{{ formatDuration(summary.duration_seconds) }}</dd>
      </div>
    </dl>

    <div class="complete__actions">
      <button class="primary-button" type="button" @click="$emit('replay')">再来一组</button>
      <RouterLink class="secondary-button" to="/wrong-words">查看错词本</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.complete {
  position: relative;
  max-width: 720px;
  margin: 38px auto 0;
  padding: 58px 46px 44px;
  text-align: center;
}

.complete__stamp {
  display: grid;
  width: 108px;
  height: 108px;
  margin: 0 auto 24px;
  place-items: center;
  border: 3px double var(--color-primary);
  border-radius: 50%;
  color: var(--color-primary);
  transform: rotate(-5deg);
}

.complete__stamp span {
  font-family: var(--font-family-title);
  font-size: var(--font-size-xl);
  line-height: 1;
  letter-spacing: 0.1em;
}

.complete__stamp small {
  font-size: 8px;
  letter-spacing: 0.12em;
}

.complete h1 {
  margin-bottom: 8px;
  font-size: var(--font-size-xl);
}

.complete__copy {
  margin-bottom: 30px;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.complete__metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin: 0 0 32px;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

.complete__metrics > div {
  padding: 20px 12px;
  border-right: 1px solid var(--color-border);
}

.complete__metrics > div:last-child {
  border-right: 0;
}

.complete__metrics dt {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.complete__metrics dd {
  margin: 3px 0 0;
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-xl);
}

.complete__metrics dd small {
  margin-left: 3px;
  color: var(--color-disabled);
  font-family: var(--font-family-body);
  font-size: var(--font-size-xs);
}

.complete__actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.complete__actions a:hover {
  text-decoration: none;
}

@media (max-width: 560px) {
  .complete {
    padding: 42px 20px 34px;
  }

  .complete__metrics {
    grid-template-columns: 1fr;
  }

  .complete__metrics > div {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .complete__metrics > div:last-child {
    border-bottom: 0;
  }

  .complete__actions {
    flex-direction: column;
  }

  .complete__actions a {
    text-align: center;
  }
}
</style>
