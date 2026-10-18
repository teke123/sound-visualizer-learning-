<script setup lang="ts">
/**
 * App 外壳（docs/srs/07 弱网与异常处理）：
 * 1. 并行请求 /api/me/context 与 /api/levels；context 失败以未登录态渲染公开内容。
 * 2. 已登录 → 拉取 me/progress 并尝试上传 outbox 学习事件。
 * 3. 窗口重新可见 / 路由切换 / 联网：后台校验 levels、刷新 context、flush outbox。
 */
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEventListener } from '@vueuse/core'
import AppShell from '@/components/AppShell.vue'
import { useContextStore } from '@/stores/context'
import { useLevelsStore } from '@/stores/levels'
import { useProgressStore } from '@/stores/progress'
import { useOutboxStore } from '@/stores/outbox'

const route = useRoute()
const router = useRouter()

const contextStore = useContextStore()
const levelsStore = useLevelsStore()
const progressStore = useProgressStore()
const outbox = useOutboxStore()

async function bootstrap() {
  // 1. 并行请求 context 与 levels
  await Promise.allSettled([contextStore.refresh(), levelsStore.refresh()])
  // 2. 校验 outbox 归属（账号不符即清理）；已登录拉服务端进度并上传事件
  progressStore.syncIdentity()
  if (contextStore.isAuthenticated) {
    void progressStore.loadServerProgress()
    void outbox.flush()
  }
}

onMounted(() => {
  void bootstrap()
})

/* 窗口重新可见：后台校验 levels + 刷新 context + flush outbox */
useEventListener(window, 'visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    void contextStore.refresh()
    void levelsStore.refresh({ background: true })
    if (contextStore.isAuthenticated) {
      void progressStore.loadServerProgress()
      void outbox.flush()
    }
  }
})

/* 网络恢复：重试 outbox */
useEventListener(window, 'online', () => {
  if (contextStore.isAuthenticated) void outbox.flush()
})

/* 路由切换：outbox 上传 + levels 后台校验 */
router.afterEach(() => {
  void levelsStore.refresh({ background: true })
  if (contextStore.isAuthenticated) void outbox.flush()
})
</script>

<template>
  <AppShell>
    <RouterView :key="route.path" />
  </AppShell>
</template>
