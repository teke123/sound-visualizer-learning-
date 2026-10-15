<script setup lang="ts">
/**
 * App 外壳（docs/architecture/04 §6.1 启动 / §6.5 学习事件 / §6.9 新鲜度）：
 * 1. 并行请求 /api/me/context 与 /api/levels；context 失败以访客态渲染公开内容。
 * 2. 已同意 → 拉取 me/progress 并尝试上传 outbox；否则本地桶计算进度。
 * 3. 窗口重新可见 / 路由切换 / 联网：后台校验 levels、刷新 context、flush outbox。
 * 4. 全局 ConsentDialog 与转存提示。
 */
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useEventListener } from '@vueuse/core'
import AppShell from '@/components/AppShell.vue'
import ConsentDialog from '@/components/ConsentDialog.vue'
import TransferNotice from '@/components/TransferNotice.vue'
import { useContextStore } from '@/stores/context'
import { useLevelsStore } from '@/stores/levels'
import { useProgressStore } from '@/stores/progress'
import { useOutboxStore } from '@/stores/outbox'
import { useConsent } from '@/features/consent'
import { useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const contextStore = useContextStore()
const levelsStore = useLevelsStore()
const progressStore = useProgressStore()
const outbox = useOutboxStore()
const consent = useConsent()

const isBare = computed(() => route.meta.bare === true)

async function bootstrap() {
  // 1. 并行请求 context 与 levels
  const [contextRes] = await Promise.allSettled([contextStore.refresh(), levelsStore.refresh()])
  // 2. 校验本地存储（dataEpoch / 账号不符即清理）；已同意拉服务端进度并上传 outbox
  progressStore.syncIdentity()
  if (contextStore.consentGranted) {
    void progressStore.loadServerProgress()
    void outbox.flush()
  }
  // 3. 未处理同意的账号（如会话保持的登录）不自动弹窗——仅登录动作触发（FD-07）
  void contextRes
}

onMounted(() => {
  void bootstrap()
})

/* 窗口重新可见：后台校验 levels + 刷新 context + flush outbox（§5/§6.9） */
useEventListener(window, 'visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    void contextStore.refresh()
    void levelsStore.refresh({ background: true })
    if (contextStore.consentGranted) {
      void progressStore.loadServerProgress()
      void outbox.flush()
    }
  }
})

/* 网络恢复：重试 outbox */
useEventListener(window, 'online', () => {
  if (contextStore.consentGranted) void outbox.flush()
})

/* 路由切换：outbox 上传 + levels 后台校验（§6.5 / §6.9） */
router.afterEach(() => {
  void levelsStore.refresh({ background: true })
  if (contextStore.consentGranted) void outbox.flush()
})
</script>

<template>
  <AppShell v-if="!isBare">
    <RouterView :key="route.path" />
  </AppShell>
  <RouterView v-else :key="route.path" />
  <ConsentDialog v-if="!isBare" />
  <TransferNotice v-if="!isBare" />
</template>
