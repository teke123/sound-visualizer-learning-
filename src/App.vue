<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAV_PAGES } from '@/data/pages'

const route = useRoute()
const router = useRouter()
const isCollapsed = ref(false)
const mobileOpen = ref(false)

/**
 * 一级导航（口径：docs/srs/02 4.2）
 * ---------------------------------------------------------------------------
 * 来源：src/data/pages.ts 的 NAV_PAGES；结果页（P09）为流程页、后台（ADMIN）
 * 为 CMS 入口，均不进入一级导航。
 */
const menuItems = NAV_PAGES.map(p => ({
  path: p.paths[0],
  icon: p.icon,
  title: p.title,
  desc: p.code,
  code: p.code,
}))

const currentTitle = computed(() => {
  const byMeta = route.meta.title as string | undefined
  if (byMeta) return byMeta
  return '看得见的声音'
})

const currentPageCode = computed(() => (route.meta.pageCode as string | undefined) ?? '')

function handleMenuClick(path: string) {
  router.push(path)
  mobileOpen.value = false
}
</script>

<template>
  <div class="app-container">
    <button class="mobile-toggle" @click="mobileOpen = !mobileOpen" aria-label="菜单">
      <el-icon :size="22"><Menu /></el-icon>
    </button>

    <aside class="sidebar" :class="{ collapsed: isCollapsed, open: mobileOpen }">
      <div class="sidebar-header">
        <div class="logo-section" @click="router.push('/')">
          <el-icon :size="28" color="#409eff"><Microphone /></el-icon>
          <div v-if="!isCollapsed" class="logo-text">
            <h1>看得见的声音</h1>
            <p>智能发音学习平台</p>
          </div>
        </div>
        <el-button :icon="isCollapsed ? 'ArrowRight' : 'ArrowLeft'" text @click="isCollapsed = !isCollapsed" class="collapse-btn hide-mobile" />
      </div>

      <el-menu :default-active="route.path" :collapse="isCollapsed" class="sidebar-menu" @select="handleMenuClick">
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>
            <div class="menu-item-content">
              <span>{{ item.title }}</span>
              <small v-if="!isCollapsed">{{ item.desc }}</small>
            </div>
          </template>
        </el-menu-item>
      </el-menu>
    </aside>

    <main class="main-content">
      <header class="top-header">
        <div class="header-left">
          <h2>
            {{ currentTitle }}
            <span v-if="currentPageCode" class="page-code">{{ currentPageCode }}</span>
          </h2>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-button type="primary" :icon="'Search'" @click="router.push('/search')">搜索</el-button>
          <el-button :icon="'Microphone'" @click="router.push('/test')">检测中心</el-button>
        </div>
      </header>
      <div class="page-content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<style scoped>
.app-container { display: flex; height: 100vh; overflow: hidden; position: relative; }
.mobile-toggle { display: none; position: fixed; top: 12px; left: 12px; z-index: 100; background: #fff; border: 1px solid #dcdfe6; border-radius: 8px; padding: 8px; cursor: pointer; }
.sidebar { width: 240px; background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%); color: white; display: flex; flex-direction: column; transition: width 0.3s ease; flex-shrink: 0; z-index: 90; }
.sidebar.collapsed { width: 64px; }
.sidebar-header { padding: 20px 16px; border-bottom: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; justify-content: space-between; }
.logo-section { display: flex; align-items: center; gap: 12px; cursor: pointer; }
.logo-text h1 { font-size: 16px; margin: 0; white-space: nowrap; }
.logo-text p { font-size: 11px; color: rgba(255,255,255,0.6); margin: 2px 0 0; }
.collapse-btn { color: rgba(255,255,255,0.6); }
.sidebar-menu { flex: 1; border-right: none; background: transparent; }
:deep(.el-menu-item) { color: rgba(255,255,255,0.8); height: 56px; margin: 4px 8px; border-radius: 8px; }
:deep(.el-menu-item:hover), :deep(.el-menu-item.is-active) { background: rgba(64,158,255,0.2); color: #409eff; }
.menu-item-content { display: flex; flex-direction: column; line-height: 1.4; }
.menu-item-content small { font-size: 11px; color: rgba(255,255,255,0.4); }
.main-content { flex: 1; display: flex; flex-direction: column; background: #f5f7fa; overflow: hidden; min-width: 0; }
.top-header { background: white; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 4px rgba(0,0,0,0.08); z-index: 10; flex-wrap: wrap; gap: 12px; }
.header-left h2 { margin: 0 0 4px; font-size: 18px; color: #303133; }
.page-code { margin-left: 6px; font-size: 11px; font-weight: 400; color: #909399; background: #f2f3f5; border-radius: 4px; padding: 1px 6px; vertical-align: middle; }
.header-right { display: flex; gap: 8px; flex-wrap: wrap; }
.page-content { flex: 1; overflow-y: auto; padding: 16px; }
@media (max-width: 768px) {
  .mobile-toggle { display: block; }
  .hide-mobile { display: none; }
  .sidebar { position: fixed; left: 0; top: 0; height: 100%; transform: translateX(-100%); }
  .sidebar.open { transform: translateX(0); width: 240px !important; }
  .main-content { width: 100%; }
  .top-header { padding-left: 56px; }
}
</style>
