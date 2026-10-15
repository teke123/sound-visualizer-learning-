/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** dev:mock 模式下启用 MSW 模拟后端（后端未就绪时的开发态） */
  readonly VITE_USE_MSW?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
