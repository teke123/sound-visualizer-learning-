<script setup lang="ts">
/**
 * FeedbackWidget：纠错（FR-1502，subtype：文字/声音/图片/字幕）→ 后端 content_error
 */
import { ref } from 'vue'
import { QBtn, QInput } from 'quasar'
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
    <div class="fb-row-inline">
      <span class="fb-title">发现内容有错？</span>
      <QBtn flat no-caps class="fb-toggle" @click="expanded = !expanded">
        {{ expanded ? '收起' : '报告错误' }}
      </QBtn>
    </div>
    <div v-if="expanded" class="fb-expand">
      <label class="fb-label">错误类型</label>
      <div class="fb-row" role="radiogroup" aria-label="错误类型">
        <QBtn
          v-for="option in [
            { key: 'text', label: '文字' },
            { key: 'audio', label: '声音' },
            { key: 'image', label: '图片' },
            { key: 'subtitle', label: '字幕' },
          ]"
          :key="option.key"
          no-caps
          class="fb-chip"
          size="13px"
          :color="subtype === option.key ? 'teal-1' : 'blue-grey-2'"
          :text-color="subtype === option.key ? 'teal-9' : 'blue-grey-6'"
          :unelevated="subtype === option.key"
          :outline="subtype !== option.key"
          @click="subtype = option.key as typeof subtype"
        >
          {{ option.label }}
        </QBtn>
      </div>
      <label class="fb-label">错在哪里？</label>
      <QInput
        v-model="detail"
        type="textarea"
        :rows="2"
        class="fb-input"
        placeholder="请描述看到的问题"
        outlined
      />
      <QBtn
        outline
        no-caps
        color="primary"
        text-color="teal-9"
        class="fb-submit"
        :disable="!detail.trim() || feedback.submitting.value"
        @click="submitDetail"
      >
        提交纠错
      </QBtn>
    </div>

    <p v-if="feedback.submitted.value" class="fb-status ok">已收到，谢谢你的反馈！</p>
    <p v-else-if="feedback.error.value" class="fb-status err">
      {{ errorCopy(feedback.error.value).title }}
      <template v-if="feedback.waitSeconds.value">（约 {{ feedback.waitSeconds.value }} 秒后可再次提交）</template>
    </p>
  </section>
</template>

<style scoped lang="sass">
/* 页底不显眼的附属模块：小字号、无卡片边框与底色 */
.feedback-widget
  margin-top: 24px
  font-size: 13px

.fb-row-inline
  display: flex
  align-items: center
  gap: 8px

.fb-title
  color: #90a4ae

.fb-row
  display: flex
  gap: 10px
  flex-wrap: wrap

/* 页底低调的入口按钮：保留灰色下划线文字形态（中性灰，非品牌语义色） */
.fb-toggle
  font-size: 13px
  color: #78909c
  text-decoration: underline

.fb-expand
  margin-top: 8px
  display: flex
  flex-direction: column
  gap: 6px
  align-items: flex-start

.fb-label
  font-size: 12px
  color: #b0bec5

/* 原 .fb-chip 32px 高的紧凑 chip（半径走全局 999px 胶囊） */
.fb-chip
  min-height: 32px

/* 原 .fb-btn.primary 青描边透明底 8px 圆角 36px 高 */
.fb-submit
  border-radius: 8px
  min-height: 36px

.fb-input
  width: 100%
  max-width: 420px
  font-size: 13px

.fb-status
  margin: 6px 0 0
  font-size: 12px
  &.ok
    color: #2e7d32
  &.err
    color: #c62828
</style>
