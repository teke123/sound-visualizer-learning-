/**
 * 同意流程（FR-102 / FD-07 / docs/architecture/04 §6.6）：
 * 未处理账号登录后立即弹出；可同意 / 拒绝 / 暂不（暂不不调用接口）；
 * 同意时展示将转存条数与「本地进度不导入」说明；
 * transfer 结果：completed 显示已保存 N 条，partial 提供重试，none 不提示。
 *
 * 对话框与转存提示为全局单例状态（多个组件共享同一个 ConsentDialog）。
 */
import { computed, ref } from 'vue'
import { identityApi, sessionApi, type TransferResult } from '@/api'
import { useContextStore } from '@/stores/context'
import { useProgressStore } from '@/stores/progress'
import { useOutboxStore } from '@/stores/outbox'

/* ------------------------- 全局单例状态 ------------------------- */

const dialogOpen = ref(false)
const transferNotice = ref<TransferResult | null>(null)
const transferableCount = ref<number | null>(null)
const loadingCount = ref(false)
const submitting = ref(false)
const submitError = ref<unknown>(null)

export type ConsentDialogAction = 'granted' | 'rejected' | 'deferred'

export function useConsent() {
  const contextStore = useContextStore()
  const progressStore = useProgressStore()
  const outbox = useOutboxStore()

  const consentTextVersion = computed(() => contextStore.context.currentConsentTextVersion)

  async function openDialog(): Promise<void> {
    dialogOpen.value = true
    transferableCount.value = contextStore.context.pendingTransfer ?? null
    if (transferableCount.value == null) {
      loadingCount.value = true
      try {
        const res = await sessionApi.recordings()
        transferableCount.value = res.data.transferableCount
      } catch {
        transferableCount.value = null
      } finally {
        loadingCount.value = false
      }
    }
  }

  function closeDialog() {
    dialogOpen.value = false
  }

  function showTransfer(notice: TransferResult | null | undefined) {
    transferNotice.value = notice ?? null
  }

  function dismissTransfer() {
    transferNotice.value = null
  }

  /** 同意 / 拒绝 / 暂不 */
  async function decide(action: ConsentDialogAction): Promise<void> {
    if (action === 'deferred') {
      closeDialog()
      return
    }
    submitting.value = true
    submitError.value = null
    try {
      const res = await identityApi.postConsent({
        decision: action,
        consentTextVersion: consentTextVersion.value,
      })
      if (action === 'granted') {
        // 同意：清除账号桶（不导入本地进度，D-16），刷新 context 与进度，展示转存
        await contextStore.refresh()
        progressStore.onConsentGranted()
        void outbox.flush()
        showTransfer(res.data.transfer)
      } else {
        await contextStore.refresh()
      }
      closeDialog()
    } catch (error) {
      submitError.value = error
    } finally {
      submitting.value = false
    }
  }

  /** 转存重试：已是 granted 时再次 granted 只重跑转存 */
  async function retryTransfer(): Promise<void> {
    submitting.value = true
    submitError.value = null
    try {
      const res = await identityApi.postConsent({
        decision: 'granted',
        consentTextVersion: consentTextVersion.value,
      })
      await contextStore.refresh()
      showTransfer(res.data.transfer)
    } catch (error) {
      submitError.value = error
    } finally {
      submitting.value = false
    }
  }

  /** P09 / P10 / P11 的同意入口（未处理 / 已拒绝 / 已撤回均可再次发起） */
  const consentEntryAvailable = computed(() =>
    contextStore.isAuthenticated && !contextStore.consentGranted,
  )

  return {
    dialogOpen,
    transferableCount,
    loadingCount,
    submitting,
    submitError,
    transferNotice,
    consentEntryAvailable,
    openDialog,
    closeDialog,
    decide,
    retryTransfer,
    showTransfer,
    dismissTransfer,
  }
}
