<script setup lang="ts">
/**
 * FeedbackWidget：三种模式（FR-1501/1502/1504）：
 * understanding = 看懂了 / 还不明白（可写不清楚的位置）
 * correction    = 纠错（subtype：文字/声音/图片/字幕）
 * rating        = 结果是否符合实际感受
 */
import { computed, ref } from 'vue'
import { errorCopy } from '@/copy/usePageCopy'
import { useFeedback } from '@/features/feedback'

type Mode = 'understanding' | 'correction' | 'rating'
// 后端反馈类型：understanding→clarity，correction→content_error，rating→result_match（rating：符合=1 不符合=0）

const props = withDefaults(
  defineProps<{
    mode: Mode
    sourcePage: string
    articleSlug?: string
    levelId?: string
    recordingId?: string
  }>(),
  {},
)

const feedback = useFeedback()
const detail = ref('')
const subtype = ref<'text' | 'audio' | 'image' | 'subtitle'>('text')
const rating = ref<'match' | 'mismatch' | null>(null)
const expanded = ref(false)

const title = computed(() => {
  if (props.mode === 'rating') return '这个结果符合你的实际感受吗？'
  if (props.mode === 'correction') return '发现内容有错？'
  return '这一页看懂了吗？'
})

async function submitUnderstanding(ok: boolean) {
  if (ok) {
    await feedback.submit({ sourcePage: props.sourcePage, type: 'clarity', content: '看懂了' })
    expanded.value = false
  } else {
    expanded.value = true
  }
}

async function submitDetail() {
  if (!detail.value.trim()) return
  if (props.mode === 'rating') {
    await feedback.submit({
      sourcePage: props.sourcePage,
      type: 'result_match',
      rating: rating.value === 'match' ? 1 : 0,
      content: detail.value.trim() || undefined,
      recordingId: props.recordingId,
    })
  } else {
    await feedback.submit({
      sourcePage: props.sourcePage,
      type: 'content_error',
      subtype: subtype.value,
      content: detail.value.trim(),
      articleSlug: props.articleSlug,
      levelId: props.levelId,
      recordingId: props.recordingId,
    })
  }
  detail.value = ''
  expanded.value = false
}

async function submitRating(value: 'match' | 'mismatch') {
  rating.value = value
  await feedback.submit({
    sourcePage: props.sourcePage,
    type: 'result_match',
    rating: value === 'match' ? 1 : 0,
    recordingId: props.recordingId,
  })
}
</script>

<template>
  <section class="feedback-widget" aria-label="页面反馈">
    <h3>{{ title }}</h3>

    <template v-if="mode === 'understanding'">
      <div class="fb-row">
        <button type="button" class="fb-btn ok" :disabled="feedback.submitted.value" @click="submitUnderstanding(true)">
          👍 看懂了
        </button>
        <button type="button" class="fb-btn no" @click="submitUnderstanding(false)">🤔 还不明白</button>
      </div>
      <div v-if="expanded" class="fb-expand">
        <label class="fb-label">哪里不清楚？（可选）</label>
        <textarea v-model="detail" rows="2" class="fb-input" placeholder="例如：剖面图里的舌头位置看不明白"></textarea>
        <button type="button" class="fb-btn primary" :disabled="!detail.trim() || feedback.submitting.value" @click="submitDetail">
          提交
        </button>
      </div>
    </template>

    <template v-else-if="mode === 'correction'">
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
    </template>

    <template v-else>
      <div class="fb-row">
        <button
          type="button"
          class="fb-btn ok"
          :disabled="feedback.submitted.value"
          @click="submitRating('match')"
        >
          ✓ 符合感受
        </button>
        <button
          type="button"
          class="fb-btn no"
          :disabled="feedback.submitted.value"
          @click="submitRating('mismatch')"
        >
          ✗ 不太符合
        </button>
      </div>
      <button type="button" class="fb-more" @click="expanded = !expanded">
        {{ expanded ? '收起补充' : '哪里不理解？补充说明' }}
      </button>
      <div v-if="expanded" class="fb-expand">
        <textarea v-model="detail" rows="2" class="fb-input" placeholder="例如：分数和我的感受不一致，现象没看懂"></textarea>
        <button type="button" class="fb-btn primary" :disabled="!detail.trim() || feedback.submitting.value" @click="submitDetail">
          提交
        </button>
      </div>
    </template>

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
  &.ok
    border-color: #66bb6a
    color: #2e7d32
  &.no
    border-color: #ff8a65
    color: #bf360c
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

.fb-more
  margin-top: 8px
  background: none
  border: none
  color: #0288d1
  cursor: pointer
  font-size: 13px
  padding: 4px 0
  min-height: 32px

.fb-status
  margin: 10px 0 0
  font-size: 13px
  &.ok
    color: #2e7d32
  &.err
    color: #c62828
</style>
