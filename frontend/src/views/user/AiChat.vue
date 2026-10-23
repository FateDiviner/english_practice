<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="app-page ai-page">
    <section class="ai-sheet surface">
      <div class="ai-sheet__mark" aria-hidden="true">
        <span>语</span>
      </div>
      <p class="eyebrow">A ROOM NOT OPEN YET</p>
      <h1>AI English 对话即将上线</h1>
      <p class="ai-sheet__copy">
        这里会是一个用英语自由交谈的练习室。你可以选择情境、和对话伙伴来回交流，
        把刚学会的词真正用出去。
      </p>
      <div class="ai-sheet__rule" aria-hidden="true"></div>
      <dl>
        <div>
          <dt>自由对话</dt>
          <dd>从一句简单的问候开始。</dd>
        </div>
        <div>
          <dt>情景练习</dt>
          <dd>在真实语境里使用新词。</dd>
        </div>
        <div>
          <dt>生词留存</dt>
          <dd>对话中遇到的词，继续回到错词本。</dd>
        </div>
      </dl>
      <p class="ai-sheet__status">本期仅开放入口与页面骨架，不会接入任何模型服务。</p>
      <div class="ai-sheet__actions">
        <RouterLink class="primary-button" to="/wordbooks">先去词书架</RouterLink>
        <RouterLink class="secondary-button" to="/">返回首页</RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.ai-page {
  display: grid;
  min-height: calc(100vh - 130px);
  place-items: center;
}

.ai-sheet {
  width: min(760px, 100%);
  padding: 50px 54px;
}

.ai-sheet__mark {
  display: grid;
  width: 74px;
  height: 74px;
  margin-bottom: 28px;
  place-items: center;
  border: 1px solid var(--color-accent);
  color: var(--color-accent);
  font-family: var(--font-family-title);
  font-size: var(--font-size-xl);
  transform: rotate(-3deg);
}

.ai-sheet h1 {
  margin-bottom: 14px;
  font-size: var(--font-size-xl);
}

.ai-sheet__copy {
  max-width: 620px;
  margin-bottom: 28px;
  color: var(--color-disabled);
  font-size: var(--font-size-md-sm);
  line-height: 2;
}

.ai-sheet__rule {
  height: 1px;
  margin-bottom: 26px;
  background: var(--color-border);
}

.ai-sheet dl {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin: 0 0 30px;
}

.ai-sheet dl > div {
  padding-right: 16px;
  border-right: 1px solid var(--color-border);
}

.ai-sheet dl > div:last-child {
  border-right: 0;
}

.ai-sheet dt {
  margin-bottom: 5px;
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-sm);
}

.ai-sheet dd {
  margin: 0;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.ai-sheet__status {
  padding: 11px 14px;
  border-left: 2px solid var(--color-accent);
  background: var(--color-background-muted);
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.ai-sheet__actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.ai-sheet__actions a:hover {
  text-decoration: none;
}

@media (max-width: 680px) {
  .ai-sheet {
    padding: 30px 22px;
  }

  .ai-sheet dl {
    grid-template-columns: 1fr;
  }

  .ai-sheet dl > div {
    padding: 0 0 14px;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .ai-sheet__actions {
    flex-direction: column;
  }

  .ai-sheet__actions a {
    text-align: center;
  }
}
</style>
