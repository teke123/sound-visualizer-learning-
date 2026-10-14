/**
 * 保存同意的 UI 提示位（重构后降级为纯前端提示）
 * ---------------------------------------------------------------------------
 * 口径（SRS NFR-15 / FR-102~104）：档案写入以服务端记录的账号与同意状态为准，
 * 逐请求校验。本 composable 只用于界面提示（如「已同意保存」标签），
 * 不再承担同意裁决；重构接通账号体系后，consented 应改为从服务端读取。
 * 客户端隐藏入口仅为体验处理，不构成权限。
 */
import { ref, watch } from 'vue'

const STORAGE_KEY = 'voice_archive_consent_v1'

export function useArchiveConsent() {
  const consented = ref(localStorage.getItem(STORAGE_KEY) === 'true')

  watch(consented, (v) => {
    if (v) localStorage.setItem(STORAGE_KEY, 'true')
    else localStorage.removeItem(STORAGE_KEY)
  })

  function grant() {
    consented.value = true
  }

  function revoke() {
    consented.value = false
  }

  return { consented, grant, revoke }
}
