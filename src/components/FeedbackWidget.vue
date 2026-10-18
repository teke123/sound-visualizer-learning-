<script setup lang="ts">
/**
 * FeedbackWidget：纠错（FR-1502，subtype：文字/声音/图片/字幕）→ 后端 content_error
 */
import { ref } from 'vue'
import { errorCopy } from '@/copy/usePageCopy'
import { useFeedback } from '@/features/feedback'

const props = defineProps<{
  sourcePage: string
  levelId?: string
}>()

const feedback = useFeedback()
const detail = ref('')
const subtype = ref<'text' | 'audio' | 'image' | 'subtitle'>('text')
const expanded = ref(false)

async function submitDetail() {
  if (!detail.value.trim()) return
  await feedback.submit({
    sourcePage: props.sourcePage,
    type: 'content_error',
    subtype: subtype.value,
    content: detail.value.trim(),
    levelId: props.levelId,
  })
  detail.value = ''
  expanded.value = false
}
</script>

<template>
  <section class="feedback-widget" aria-label="页面反馈">
    <h3>发现内容有错？</h3>

    <button type="button" class="fb-btn" @click="expanded = !expanded">
      {{ expanded ? '收起' : '报告错误' }}
    </button>
    <div v-if="expanded" class="fb-expand">
      <label class="fb-label">错误类型</label>
      <div class="fb-row" role="radiogroup" aria-label="错误类型">
        <button
          v-for="option in [
            { key: 'text', label: '文字' },
            { key: 'audio', label: '声音' },
            { key: 'image', label: '图片' },
            { key: 'subtitle', label: '字幕' },
          ]"
          :key="option.key"
          type="button"
          :class="['fb-chip', { active: subtype === option.key }]"
          @click="subtype = option.key as typeof subtype"
        >
          {{ option.label }}
        </button>
      </div>
      <label class="fb-label">错在哪里？</label>
      <textarea v-model="detail" rows="2" class="fb-input" placeholder="请描述看到的问题"></textarea>
      <button type="button" class="fb-btn primary" :disabled="!detail.trim() || feedback.submitting.value" @click="submitDetail">
        提交纠错
      </button>
    </div>

    <p v-if="feedback.submitted.value" class="fb-status ok">已收到，谢谢你的反馈！</p>
    <p v-else-if="feedback.error.value" class="fb-status err">
      {{ errorCopy(feedback.error.value).title }}
      <template v-if="feedback.waitSeconds.value">（约 {{ feedback.waitSeconds.value }} 秒后可再次提交）</template>
    </p>
  </section>
</template>

<style scoped lang="sass">
.feedback-widget
  margin-top: 28px
  border: 1px solid #eceff1
  border-radius: 12px
  padding: 14px 16px
  background: #fafafa

  h3
    margin: 0 0 10px
    font-size: 15px
    color: #37474f

.fb-row
  display: flex
  gap: 10px
  flex-wrap: wrap

.fb-btn
  min-height: 44px
  padding: 4px 18px
  border-radius: 999px
  border: 1px solid #cfd8dc
  background: #fff
  cursor: pointer
  font-size: 14px
  &.primary
    background: #00897b
    border-color: #00897b
    color: #fff
    font-weight: 600
  &:disabled
    opacity: 0.55
    cursor: default

.fb-chip
  min-height: 40px
  padding: 2px 14px
  border-radius: 999px
  border: 1px solid #cfd8dc
  background: #fff
  cursor: pointer
  &.active
    border-color: #00897b
    background: #e0f2f1
    color: #00695c
    font-weight: 600

.fb-expand
  margin-top: 10px
  display: flex
  flex-direction: column
  gap: 8px
  align-items: flex-start

.fb-label
  font-size: 13px
  color: #78909c

.fb-input
  width: 100%
  border: 1px solid #cfd8dc
  border-radius: 8px
  padding: 8px 12px
  font-size: 14px
  box-sizing: border-box
  resize: vertical

.fb-status
  margin: 10px 0 0
  font-size: 13px
  &.ok
    color: #2e7d32
  &.err
    color: #c62828
</style>
