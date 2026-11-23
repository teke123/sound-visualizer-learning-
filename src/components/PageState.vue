<script setup lang="ts">
/**
 * PageState：加载 / 空 / 错误 / 无权限 / 不可见 状态统一展示；
 * 错误显示 requestId（NFR-19）与「下一步能做什么」（usePageCopy）。
 */
import { computed } from 'vue'
import { errorCopy, requestIdOf, PAGE_STATE_COPY } from '@/copy/usePageCopy'
import AppIcon from '@/components/ui/AppIcon.vue'

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

const iconName = computed(() => {
  switch (props.state) {
    case 'error':
      return 'info'
    case 'forbidden':
      return 'lock'
    case 'not-visible':
      return 'search'
    case 'empty':
      return 'folder'
    default:
      return 'wave'
  }
})
</script>

<template>
  <div class="vs-state" :class="`state-${state}`" role="status">
    <div v-if="state === 'loading'" class="vs-spin" aria-hidden="true" />
    <AppIcon v-else :name="iconName" size="lg" />
    <p class="state-title">{{ title }}</p>
    <p v-if="hint" class="state-hint">{{ hint }}</p>
    <p v-if="requestId" class="state-request-id">requestId：{{ requestId }}</p>
    <button v-if="state === 'error'" type="button" class="vs-btn vs-btn--ghost vs-btn--small retry-btn" @click="emit('retry')">
      重试
    </button>
  </div>
</template>

<style scoped lang="sass">
.state-title
  margin: 0
  font-size: 15px
  font-weight: 600
  color: var(--vs-ink2)

.state-hint
  margin: 0
  font-size: 13.5px
  color: var(--vs-sub)
  text-align: center
  max-width: 520px

.state-request-id
  margin: 0
  font-size: 12px
  color: var(--vs-mute)

.retry-btn
  margin-top: 8px
</style>
