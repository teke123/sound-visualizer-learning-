/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import { quasar, transformAssetUrls } from '@quasar/vite-plugin'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue({ template: { transformAssetUrls } }),
    quasar(),
    vueDevTools(),
  ],
  /**
   * 开发服务器固定只监听 IPv4，并开启 strictPort（第 5 周 D 修复）
   * ---------------------------------------------------------------------------
   * 现象：浏览器打开 http://localhost:5173 一直转圈，页面根本不出来。
   * 原因有两条，都会在这里被挡住：
   *   1) 本机 localhost 会优先解析到 IPv6 ::1，而 Vite 在 ::1 上表现为
   *      「TCP 能连上但永不返回内容」，Chromium 拿到连接就不会回落到 127.0.0.1；
   *   2) 如果 127.0.0.1:5173 已被另一份服务占用，第二份 Vite 不会报错，
   *      而是静默绑到 ::1:5173 —— 两份服务抢同一端口，浏览器恰好连到坏的那份。
   * 固定 host + strictPort 之后，端口被占会直接报错，不会再出现这种「静默双开」。
   */
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      // 开发态将 /api 代理到本地后端（docs/architecture/04 第 1 节）；
      // 后端未就绪时可用 `npm run dev:mock` 走 MSW 模拟（不经代理）。
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
    watch: {
      /**
       * 忽略「原子写入」留下的临时目录（第 5 周 D 修复）
       * -----------------------------------------------------------------
       * 有些编辑器/工具保存文件时会先在源文件旁建一个
       *   .<文件名>.<pid>.<guid>.<文件名>.tmp
       * 再改名覆盖。chokidar 监听到这个目录被删除的瞬间会抛
       *   Error: EBUSY: resource busy or locked, watch '...tmpdir\...tmp'
       * 而且这个异常会直接终止整个 Vite 进程（不是只打印一条警告）。
       * 实测在改 vite.config.ts / src 下任意文件时都会触发。
       * 把这些临时产物排除掉，dev server 就不会再被保存动作打死。
       */
      ignored: ['**/*.tmpdir', '**/*.tmpdir/**', '**/.*.tmp'],
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.spec.ts'],
  },
})
