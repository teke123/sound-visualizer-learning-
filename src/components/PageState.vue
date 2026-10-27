<script setup lang="ts">
/**
 * PageState：加载 / 空 / 错误 / 无权限 / 不可见 状态统一展示；
 * 错误显示 requestId（NFR-19）与「下一步能做什么」（usePageCopy）。
 */
import { computed } from 'vue'
import { QBtn, QSpinner } from 'quasar'
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
    <QSpinner v-if="state === 'loading'" size="28px" color="primary" aria-hidden="true" />
    <p class="state-title">{{ title }}</p>
    <p v-if="hint" class="state-hint">{{ hint }}</p>
    <p v-if="requestId" class="state-request-id">requestId：{{ requestId }}</p>
    <QBtn
      v-if="state === 'error'"
      outline
      no-caps
      color="primary"
      text-color="teal-9"
      label="重试"
      class="retry-btn"
      @click="emit('retry')"
    />
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

/* 原 .retry-btn：浅青底 + 青描边 + 深青字，44px / 8px 圆角（非胶囊）；
   Quasar outline 底色为 transparent !important，浅青底需 important 补回 */
.retry-btn
  margin-top: 8px
  min-height: 44px
  border-radius: 8px
  background: #e0f2f1 !important
</style>
