<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const items = [
  { index: 'A1', label: '数据概览', to: '/admin/overview', name: 'admin-overview' },
  { index: 'A2', label: '词书管理', to: '/admin/wordbooks', name: 'admin-wordbooks' },
  { index: 'A3', label: '导入单词', to: '/admin/import', name: 'admin-import' },
  { index: 'A4', label: '用户管理', to: '/admin/users', name: 'admin-users' },
  {
    index: 'A5',
    label: 'MCP 审批',
    to: '/admin/mcp-approvals',
    name: 'admin-mcp-approvals',
  },
]
const activeName = computed(() => route.name)

function logout() {
  authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <div class="admin-brand">
        <span class="admin-brand__mark">墨</span>
        <div>
          <strong>管理事务所</strong>
          <small>ADMIN OFFICE</small>
        </div>
      </div>

      <nav class="admin-nav" aria-label="管理端导航">
        <RouterLink
          v-for="item in items"
          :key="item.name"
          :to="item.to"
          class="admin-nav__item"
          :class="{ 'admin-nav__item--active': activeName === item.name }"
        >
          <span>{{ item.index }}</span>
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="admin-sidebar__footer">
        <p>{{ authStore.user?.username }}</p>
        <RouterLink to="/">返回学习端</RouterLink>
        <button type="button" @click="logout">退出账户</button>
      </div>
    </aside>

    <main class="admin-main">
      <header class="admin-topbar">
        <span>纸感学院 · 内容与人员管理</span>
        <span class="admin-topbar__actions">
          <RouterLink to="/">学习端</RouterLink>
          <button type="button" @click="logout">退出</button>
        </span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.admin-shell {
  min-height: 100vh;
  background: var(--color-background-muted);
}

.admin-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  display: flex;
  width: 236px;
  flex-direction: column;
  border-right: 1px solid var(--color-border);
  background: var(--color-primary);
  color: var(--color-surface);
}

.admin-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 30px 26px;
  border-bottom: 1px solid color-mix(in srgb, var(--color-surface), transparent 78%);
}

.admin-brand__mark {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border: 1px solid var(--color-accent);
  color: var(--color-accent);
  font-family: var(--font-family-title);
  font-size: var(--font-size-lg);
}

.admin-brand strong,
.admin-brand small {
  display: block;
}

.admin-brand strong {
  font-family: var(--font-family-title);
  font-size: var(--font-size-md);
}

.admin-brand small {
  color: color-mix(in srgb, var(--color-surface), transparent 40%);
  font-size: 9px;
  letter-spacing: 0.14em;
}

.admin-nav {
  display: grid;
  gap: 4px;
  padding: 26px 18px;
}

.admin-nav__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 11px 12px;
  color: color-mix(in srgb, var(--color-surface), transparent 28%);
  font-size: var(--font-size-sm);
  text-decoration: none;
}

.admin-nav__item span {
  color: var(--color-accent);
  font-family: var(--font-family-title);
  font-size: 10px;
  letter-spacing: 0.08em;
}

.admin-nav__item:hover {
  background: color-mix(in srgb, var(--color-surface), transparent 92%);
  color: var(--color-surface);
  text-decoration: none;
}

.admin-nav__item--active {
  background: color-mix(in srgb, var(--color-surface), transparent 90%);
  color: var(--color-surface);
}

.admin-nav__item--active::before {
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 3px;
  background: var(--color-accent);
  content: '';
}

.admin-sidebar__footer {
  display: grid;
  gap: 8px;
  margin-top: auto;
  padding: 22px 26px 30px;
  border-top: 1px solid color-mix(in srgb, var(--color-surface), transparent 78%);
  font-size: var(--font-size-xs);
}

.admin-sidebar__footer p {
  margin-bottom: 4px;
  font-size: var(--font-size-sm);
}

.admin-sidebar__footer a,
.admin-sidebar__footer button {
  border: 0;
  background: none;
  padding: 0;
  color: color-mix(in srgb, var(--color-surface), transparent 35%);
  text-align: left;
}

.admin-sidebar__footer a:hover,
.admin-sidebar__footer button:hover {
  color: var(--color-accent);
  text-decoration: none;
}

.admin-main {
  min-height: 100vh;
  margin-left: 236px;
}

.admin-topbar {
  display: flex;
  justify-content: space-between;
  padding: 16px 36px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  letter-spacing: 0.04em;
}

.admin-main :deep(.app-page) {
  width: min(1280px, 100%);
}

.admin-topbar__actions {
  display: flex;
  gap: 14px;
}

.admin-topbar__actions button {
  border: 0;
  background: none;
  padding: 0;
  color: var(--color-disabled);
  font-size: inherit;
}

.admin-topbar__actions button:hover {
  color: var(--color-error);
}

@media (max-width: 860px) {
  .admin-sidebar {
    position: static;
    width: 100%;
  }

  .admin-brand {
    padding: 18px 20px;
  }

  .admin-nav {
    grid-template-columns: repeat(4, 1fr);
    padding: 0 12px 12px;
    overflow-x: auto;
  }

  .admin-nav__item {
    justify-content: center;
    padding: 9px 8px;
    white-space: nowrap;
  }

  .admin-nav__item span {
    display: none;
  }

  .admin-sidebar__footer {
    display: none;
  }

  .admin-main {
    margin-left: 0;
  }

  .admin-topbar {
    padding: 12px 20px;
  }
}
</style>
