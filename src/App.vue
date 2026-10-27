<script setup lang="ts">
/**
 * App 外壳（docs/srs/07 弱网与异常处理）：
 * 1. 并行请求 /api/me/context 与 /api/levels；context 失败以未登录态渲染公开内容。
 * 2. 已登录 → 拉取 me/progress。
 * 3. 窗口重新可见 / 路由切换：后台校验 levels、刷新 context 与进度。
 */
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEventListener } from '@vueuse/core'
import AppShell from '@/components/AppShell.vue'
import { useContextStore } from '@/stores/context'
import { useLevelsStore } from '@/stores/levels'
import { useProgressStore } from '@/stores/progress'

const route = useRoute()
const router = useRouter()

const contextStore = useContextStore()
const levelsStore = useLevelsStore()
const progressStore = useProgressStore()

async function bootstrap() {
  // 1. 并行请求 context 与 levels
  await Promise.allSettled([contextStore.refresh(), levelsStore.refresh()])
  // 2. 已登录拉服务端进度
  if (contextStore.isAuthenticated) {
    void progressStore.loadServerProgress()
  }
}

onMounted(() => {
  void bootstrap()
})

/* 窗口重新可见：后台校验 levels + 刷新 context 与进度 */
useEventListener(window, 'visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    void contextStore.refresh()
    void levelsStore.refresh({ background: true })
    if (contextStore.isAuthenticated) {
      void progressStore.loadServerProgress()
    }
  }
})

/* 路由切换：levels 后台校验 */
router.afterEach(() => {
  void levelsStore.refresh({ background: true })
})
</script>

<template>
  <AppShell>
    <RouterView :key="route.path" />
  </AppShell>
</template>

<style lang="sass">
/* IPA 严式标音字体栈：Roboto 等常用 UI 字体缺附加符号 ◌̯（U+032F）会渲染成豆腐块，
   本机 Segoe UI / Calibri / Arial / Times New Roman 已验证完整覆盖 IPA 附加符号与扩展区 */
:root
  --font-ipa: 'Segoe UI', 'Calibri', 'Arial', 'Times New Roman', 'Microsoft YaHei', sans-serif

/* Quasar 接管控件后，正文默认色对齐全站蓝灰（Quasar 默认近黑） */
body
  color: #455a64

/* 还原原版按钮观感：无水波纹（原版无 ripple）、干脆的 0.15s 过渡
   （QBtn 默认过渡偏慢且带 ripple 波纹，观感发软） */
.q-ripple
  display: none

.q-btn
  transition: background-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease

/* Quasar outline 按钮描边跟随文字色（currentColor），与原版「浅描边 + 深字」组合不符，
   按文字色类校正描边浓淡 */
.q-btn--outline.text-blue-grey-9::before
  border-color: #90a4ae // 灰系：浅灰蓝边 + 深灰蓝字（原版 #90a4ae/#37474f）
.q-btn--outline.text-teal-9::before
  border-color: #00897b // 青系浅青填充：青边 + 深青字（原版 #00897b/#00695c）
.q-btn--outline.text-red-9::before
  border-color: #ef9a9a // 危险：浅红边 + 红字（原版 #ef9a9a/#c62828）
.q-btn--outline.text-blue-grey-6::before
  border-color: #cfd8dc // 浅灰 chip：极浅边 + 中灰字
</style>
