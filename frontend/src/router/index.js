import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    component: () => import('../layouts/AuthLayout.vue'),
    meta: { guestOnly: true },
    children: [
      {
        path: '',
        name: 'login',
        component: () => import('../views/auth/Login.vue'),
        meta: { guestOnly: true, title: '登录' },
      },
    ],
  },
  {
    path: '/register',
    component: () => import('../layouts/AuthLayout.vue'),
    meta: { guestOnly: true },
    children: [
      {
        path: '',
        name: 'register',
        component: () => import('../views/auth/Register.vue'),
        meta: { guestOnly: true, title: '注册' },
      },
    ],
  },
  {
    path: '/',
    component: () => import('../layouts/UserLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'home', component: () => import('../views/user/Home.vue') },
      {
        path: 'wordbooks',
        name: 'wordbooks',
        component: () => import('../views/user/WordbookList.vue'),
      },
      {
        path: 'wordbooks/:id',
        name: 'wordbook-detail',
        component: () => import('../views/user/WordbookDetail.vue'),
      },
      { path: 'practice', name: 'practice', component: () => import('../views/user/Practice.vue') },
      {
        path: 'wrong-words',
        name: 'wrong-words',
        component: () => import('../views/user/WrongWords.vue'),
      },
      { path: 'profile', name: 'profile', component: () => import('../views/user/Profile.vue') },
      {
        path: 'ai-chat',
        name: 'ai-chat',
        component: () => import('../views/user/AiChat.vue'),
      },
    ],
  },
  {
    path: '/admin',
    component: () => import('../layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/overview' },
      {
        path: 'overview',
        name: 'admin-overview',
        component: () => import('../views/admin/Overview.vue'),
      },
      {
        path: 'wordbooks',
        name: 'admin-wordbooks',
        component: () => import('../views/admin/WordbookManage.vue'),
      },
      {
        path: 'wordbooks/:id/words',
        name: 'admin-words',
        component: () => import('../views/admin/WordManage.vue'),
      },
      {
        path: 'import',
        name: 'admin-import',
        component: () => import('../views/admin/ImportWizard.vue'),
      },
      {
        path: 'users',
        name: 'admin-users',
        component: () => import('../views/admin/UserManage.vue'),
      },
      {
        path: 'mcp-approvals',
        name: 'admin-mcp-approvals',
        component: () => import('../views/admin/McpApprovals.vue'),
        meta: { title: 'MCP 审批' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

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
