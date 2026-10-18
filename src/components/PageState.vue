<script setup lang="ts">
/**
 * PageState：加载 / 空 / 错误 / 无权限 / 不可见 状态统一展示；
 * 错误显示 requestId（NFR-19）与「下一步能做什么」（usePageCopy）。
 */
import { computed } from 'vue'
import { errorCopy, requestIdOf, PAGE_STATE_COPY } from '@/copy/usePageCopy'

export type PageStateKind = 'loading' | 'empty' | 'error' | 'forbidden' | 'not-visible'

const props = defineProps<{
  state: PageStateKind
  error?: unknown
  /** 覆盖默认文案 */
  text?: string
}>()

const emit = defineEmits<{ (e: 'retry'): void }>()

const title = computed(() => {
  if (props.text) return props.text
  switch (props.state) {
    case 'loading':
      return PAGE_STATE_COPY.loading
    case 'empty':
      return PAGE_STATE_COPY.empty
    case 'error':
      return errorCopy(props.error).title
    case 'forbidden':
      return PAGE_STATE_COPY.forbidden
    case 'not-visible':
      return PAGE_STATE_COPY.notVisible
    default:
      return PAGE_STATE_COPY.empty
  }
})

const hint = computed(() => (props.state === 'error' ? errorCopy(props.error).hint : ''))
const requestId = computed(() => (props.state === 'error' ? requestIdOf(props.error) : undefined))
</script>

<template>
  <div class="page-state" :class="`state-${state}`" role="status">
    <span v-if="state === 'loading'" class="spinner" aria-hidden="true"></span>
    <p class="state-title">{{ title }}</p>
    <p v-if="hint" class="state-hint">{{ hint }}</p>
    <p v-if="requestId" class="state-request-id">requestId：{{ requestId }}</p>
    <button v-if="state === 'error'" type="button" class="retry-btn" @click="emit('retry')">重试</button>
  </div>
</template>

<style scoped lang="sass">
.page-state
  display: flex
  flex-direction: column
  align-items: center
  gap: 8px
  padding: 48px 16px
  color: #546e7a

.state-title
  margin: 0
  font-size: 16px

.state-hint
  margin: 0
  font-size: 14px
  color: #78909c
  text-align: center

.state-request-id
  margin: 0
  font-size: 12px
  color: #b0bec5

.spinner
  width: 28px
  height: 28px
  border: 3px solid #cfd8dc
  border-top-color: #00897b
  border-radius: 50%
  animation: spin 0.8s linear infinite

@keyframes spin
  to
    transform: rotate(360deg)

.retry-btn
  min-height: 44px
  margin-top: 8px
  padding: 6px 24px
  border-radius: 8px
  border: 1px solid #00897b
  background: #e0f2f1
  color: #00695c
  cursor: pointer
</style>
