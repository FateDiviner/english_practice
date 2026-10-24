<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const navItems = [
  { index: '01', label: '首页', to: '/', name: 'home' },
  { index: '02', label: '词书', to: '/wordbooks', name: 'wordbooks' },
  { index: '03', label: '练习', to: '/practice', name: 'practice' },
  { index: '04', label: '错词本', to: '/wrong-words', name: 'wrong-words' },
  { index: '05', label: '我的', to: '/profile', name: 'profile' },
  { index: '06', label: 'AI 对话', to: '/ai-chat', name: 'ai-chat' },
]

const activeName = computed(() => route.name)
const username = computed(() => authStore.user?.username || '同学')

function logout() {
  authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <div class="user-shell">
    <aside class="user-sidebar">
      <RouterLink class="brand" to="/" aria-label="回到首页">
        <span class="brand__seal">习</span>
        <span>
          <strong>墨痕</strong>
          <small>ENGLISH STUDIO</small>
        </span>
      </RouterLink>

      <nav class="side-nav" aria-label="主导航">
        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          :to="item.to"
          class="nav-link"
          :class="{ 'nav-link--active': activeName === item.name }"
        >
          <span class="nav-link__index">{{ item.index }}</span>
          <span class="nav-link__label">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div class="account-line">
          <span class="account-initial">{{ username.slice(0, 1).toUpperCase() }}</span>
          <span class="account-copy">
            <strong>{{ username }}</strong>
            <small>{{ authStore.isAdmin ? '管理员账户' : '学习者' }}</small>
          </span>
        </div>
        <div class="sidebar-actions">
          <RouterLink v-if="authStore.isAdmin" to="/admin/overview">管理端</RouterLink>
          <button type="button" @click="logout">退出</button>
        </div>
      </div>
    </aside>

    <main class="user-main">
      <header class="mobile-header">
        <RouterLink class="mobile-brand" to="/">墨痕 / 英语默写</RouterLink>
        <span class="mobile-account">
          <span>{{ username }}</span>
          <RouterLink v-if="authStore.isAdmin" to="/admin/overview">管理端</RouterLink>
          <button type="button" @click="logout">退出</button>
        </span>
      </header>
      <RouterView />
    </main>

    <nav class="mobile-tabs" aria-label="移动端主导航">
      <RouterLink
        v-for="item in navItems"
        :key="`mobile-${item.name}`"
        :to="item.to"
        class="mobile-tab"
        :class="{ 'mobile-tab--active': activeName === item.name }"
      >
        <span class="mobile-tab__mark"></span>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped src="./UserLayout.css"></style>
