export const routes = [
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
      { path: 'mcp-access', redirect: '/admin/mcp/access' },
      { path: 'mcp-approvals', redirect: '/admin/mcp/approvals' },
      {
        path: 'mcp',
        component: () => import('../views/admin/McpManage.vue'),
        children: [
          { path: '', redirect: '/admin/mcp/access' },
          {
            path: 'access',
            name: 'admin-mcp-access',
            component: () => import('../views/admin/McpAccess.vue'),
            meta: { title: 'MCP 管理 · 接入配置' },
          },
          {
            path: 'approvals',
            name: 'admin-mcp-approvals',
            component: () => import('../views/admin/McpApprovals.vue'),
            meta: { title: 'MCP 管理 · 审批队列' },
          },
        ],
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]
