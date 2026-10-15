/** 反馈与希望增加（FR-1501–1504）：429 时显示等待时间 */
import { ref } from 'vue'
import { ApiError, feedbackApi, type FeedbackPayload } from '@/api'

export function useFeedback() {
  const submitting = ref(false)
  const submitted = ref(false)
  const error = ref<unknown>(null)
  const waitSeconds = ref<number | null>(null)

  async function submit(payload: FeedbackPayload): Promise<boolean> {
    submitting.value = true
    submitted.value = false
    error.value = null
    waitSeconds.value = null
    try {
      await feedbackApi.submit(payload)
      submitted.value = true
      return true
    } catch (err) {
      error.value = err
      if (err instanceof ApiError && err.retryAfterMs) {
        waitSeconds.value = Math.max(1, Math.round(err.retryAfterMs / 1000))
      }
      return false
    } finally {
      submitting.value = false
    }
  }

  return { submitting, submitted, error, waitSeconds, submit }
}

export function useWish() {
  const submitting = ref(false)
  const submitted = ref(false)
  const error = ref<unknown>(null)
  const waitSeconds = ref<number | null>(null)

  async function submit(content: string, searchQuery?: string): Promise<boolean> {
    submitting.value = true
    submitted.value = false
    error.value = null
    waitSeconds.value = null
    try {
      await feedbackApi.submitWish({ content, searchQuery })
      submitted.value = true
      return true
    } catch (err) {
      error.value = err
      if (err instanceof ApiError && err.retryAfterMs) {
        waitSeconds.value = Math.max(1, Math.round(err.retryAfterMs / 1000))
      }
      return false
    } finally {
      submitting.value = false
    }
  }

  return { submitting, submitted, error, waitSeconds, submit }
}
