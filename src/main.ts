/**
 * 应用入口：
 * Vue 3 + Quasar v2（按需组件）+ Pinia + vue-router；
 * dev:mock 模式（后端未就绪）先启动 MSW 再挂载。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { Quasar, Notify } from 'quasar'
import '@quasar/extras/material-icons/material-icons.css'
import 'quasar/src/css/index.sass'

import App from './App.vue'
import './css/theme.sass'
import router from './router'

async function enableMockWorker(): Promise<void> {
  // `npm run dev:mock` 走 --mode mock，直接按 mode 判定，不依赖 .env.mock 文件；
  // 也保留 VITE_USE_MSW 开关，便于只改环境变量时使用。
  const useMock = import.meta.env.MODE === 'mock' || import.meta.env.VITE_USE_MSW === 'true'
  if (!useMock) return
  const { worker } = await import('./mocks/browser')
  await worker.start({ onUnhandledFrame: 'bypass' })
}

async function startApp() {
  await enableMockWorker()

  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.use(Quasar, { plugins: { Notify } })
  app.mount('#app')
}

void startApp()
