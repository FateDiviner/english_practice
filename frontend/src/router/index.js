import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'
import { routes } from './routes'

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia)
  if (!authStore.initialized) {
    try {
      await authStore.fetchMe()
    } catch {
      // The request layer clears invalid sessions; the guards below redirect.
    }
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresAdmin && !authStore.isAdmin) return { name: 'home' }
  if (to.meta.guestOnly && authStore.isAuthenticated) return { name: 'home' }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 墨痕` : '墨痕 · 英语默写'
})

export default router
