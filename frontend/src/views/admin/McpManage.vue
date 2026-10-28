<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
const tabs = [
  { name: 'admin-mcp-access', label: '接入配置', to: '/admin/mcp/access' },
  { name: 'admin-mcp-approvals', label: '审批队列', to: '/admin/mcp/approvals' },
]
const activeName = computed(() => route.name)
</script>

<template>
  <div class="mcp-manage">
    <nav class="mcp-manage__tabs" aria-label="MCP 管理导航">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.name"
        :to="tab.to"
        class="mcp-manage__tab"
        :class="{ 'mcp-manage__tab--active': activeName === tab.name }"
      >
        {{ tab.label }}
      </RouterLink>
    </nav>
    <RouterView />
  </div>
</template>

<style scoped src="./McpManage.css"></style>
