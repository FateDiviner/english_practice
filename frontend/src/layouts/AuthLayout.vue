<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="auth-shell">
    <section class="auth-intro" aria-label="墨痕英语默写">
      <RouterLink class="auth-brand" to="/login">
        <span>习</span>
        <strong>墨痕</strong>
      </RouterLink>
      <div class="auth-intro__copy">
        <p class="eyebrow">WRITE · REMEMBER · GROW</p>
        <h1>让拼写回到<br />纸与笔的节奏。</h1>
        <p>每日一组默写，把陌生词写成熟词。细微的进步，也值得被认真记录。</p>
      </div>
      <footer>
        <span>ENGLISH PRACTICE STUDIO</span>
        <span>EST. 2026</span>
      </footer>
    </section>
    <section class="auth-panel">
      <div class="auth-panel__inner">
        <RouterView />
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth-shell {
  display: grid;
  min-height: 100vh;
  grid-template-columns: minmax(360px, 0.92fr) minmax(420px, 1.08fr);
  background: var(--color-surface);
}

.auth-intro {
  position: relative;
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  justify-content: space-between;
  padding: 48px 56px;
  overflow: hidden;
  border-right: 1px solid var(--color-border);
  background: var(--color-primary);
  color: var(--color-surface);
}

.auth-intro::after {
  position: absolute;
  right: 38px;
  bottom: 120px;
  width: 180px;
  height: 180px;
  border: 1px solid color-mix(in srgb, var(--color-accent), transparent 38%);
  border-radius: 50%;
  content: '';
  opacity: 0.5;
}

.auth-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--color-surface);
  text-decoration: none;
}

.auth-brand:hover {
  text-decoration: none;
}

.auth-brand span {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 1px solid var(--color-accent);
  color: var(--color-accent);
  font-family: var(--font-family-title);
  font-size: var(--font-size-lg);
}

.auth-brand strong {
  font-family: var(--font-family-title);
  font-size: var(--font-size-lg);
  letter-spacing: 0.1em;
}

.auth-intro__copy {
  max-width: 430px;
}

.auth-intro__copy h1 {
  margin-bottom: 22px;
  font-size: var(--font-size-xl);
  letter-spacing: 0.04em;
}

.auth-intro__copy > p:last-child {
  max-width: 360px;
  color: color-mix(in srgb, var(--color-surface), transparent 30%);
  font-size: var(--font-size-sm);
  line-height: 2;
}

.auth-intro footer {
  display: flex;
  justify-content: space-between;
  color: color-mix(in srgb, var(--color-surface), transparent 50%);
  font-size: 9px;
  letter-spacing: 0.14em;
}

.auth-panel {
  display: grid;
  place-items: center;
  padding: 44px;
  background: var(--color-background);
}

.auth-panel__inner {
  width: min(390px, 100%);
}

@media (max-width: 820px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }

  .auth-intro {
    min-height: auto;
    padding: 24px 22px 34px;
    border-right: 0;
  }

  .auth-intro__copy {
    margin-top: 54px;
  }

  .auth-intro__copy h1 {
    font-size: var(--font-size-lg);
  }

  .auth-intro footer {
    display: none;
  }

  .auth-panel {
    align-items: start;
    padding: 34px 22px 54px;
  }
}
</style>
