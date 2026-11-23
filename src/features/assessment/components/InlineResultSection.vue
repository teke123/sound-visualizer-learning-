<script setup lang="ts">
/**
 * InlineResultSection：关卡页（P05）页内检测结果区（docs §3.2 / FR-1001–1008 摘要版）。
 * 提交成功后不跳转独立结果页，用 useRecordingResult 在右栏原地轮询与展示：
 * 完成态主体复用 ResultBody（质量/分数/声学对比图/现象与四步），
 * 回放按钮经 #score-actions 插槽放在分数旁；
 * 「再录一次」交回页面（reRecord），「查看完整报告」进 /result/:id 看原始声学数据。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { audioFileUrl } from '@/api'
import { useRecordingResult } from '@/features/result'
import { usePlayerStore } from '@/stores/player'
import AppIcon from '@/components/ui/AppIcon.vue'
import ProcessingStage from './ProcessingStage.vue'
import ResultBody from './ResultBody.vue'

const props = defineProps<{
  recordingId: string
  levelId?: string
}>()

const emit = defineEmits<{ (e: 'reRecord'): void }>()

const router = useRouter()
const player = usePlayerStore()

const recordingIdRef = computed(() => props.recordingId)
const result = useRecordingResult(recordingIdRef)

const phase = result.phase
const recording = result.recording
const assessment = result.result

/** 失败时仅当内存 entry 匹配本记录才能同键重试（FD-15，同 ResultPage） */
const retryable = computed(
  () => phase.value === 'failed' && result.entry.value?.recordingId === props.recordingId,
)

const playbackKey = computed(() => `audio:${recording.value?.audioId ?? ''}`)

async function onRetrySubmission() {
  const outcome = await result.retrySubmission()
  if (outcome?.changed) void router.push(`/result/${outcome.recordingId}`)
}

function playRecording() {
  const audioId = recording.value?.audioId
  if (!audioId) return
  void player.play({ key: playbackKey.value, url: audioFileUrl(audioId), label: '本次录音' })
}
</script>

<template>
  <div class="inline-result">
    <!-- 处理中（202 轮询） -->
    <ProcessingStage v-if="phase === 'processing' || phase === 'loading'" :stage="result.stage.value" />

    <!-- 404：过期或不可见 -->
    <p v-else-if="phase === 'not-found'" class="inline-note">记录不存在或不可见。</p>

    <!-- 失败（504 / 500 等） -->
    <div v-else-if="phase === 'failed'" class="inline-failed vs-card">
      <h3>这次检测没有完成</h3>
      <p class="fail-hint">可能是评分服务繁忙或处理超时。</p>
      <div class="fail-actions">
        <button v-if="retryable" type="button" class="vs-btn" @click="onRetrySubmission">重试本次提交</button>
        <button type="button" class="vs-btn vs-btn--ghost" @click="emit('reRecord')">重新录音</button>
      </div>
    </div>

    <!-- 已完成：公共主体 + 页内专属底部操作 -->
    <template v-else-if="assessment && recording">
      <ResultBody
        :result="assessment"
        :audio-id="recording.audioId"
        :recording-id="recordingId"
        heading-level="h3"
        :formant-height="260"
      >
        <template #score-actions>
          <button type="button" class="vs-btn vs-btn--ghost" @click="playRecording">
            <AppIcon :name="player.isCurrent(playbackKey) ? 'pause' : 'play'" size="sm" />
            {{ player.isCurrent(playbackKey) ? '暂停本次录音' : '回放本次录音' }}
          </button>
        </template>
      </ResultBody>

      <!-- 底部操作 -->
      <div class="act-row">
        <button type="button" class="vs-btn" @click="emit('reRecord')">
          <AppIcon name="mic" size="sm" />再录一次
        </button>
        <RouterLink :to="`/result/${recordingId}`" class="vs-btn vs-btn--ghost">查看完整报告 →</RouterLink>
      </div>
    </template>
  </div>
</template>

<style scoped lang="sass">
.inline-result
  display: flex
  flex-direction: column
  gap: 18px

.inline-note
  margin: 0
  font-size: 14px
  color: var(--vs-mute)
  text-align: center
  padding: 18px 0

.inline-failed
  text-align: center
  padding: 24px
  h3
    font-size: 18px
    font-weight: 800
    margin: 0 0 6px

.fail-hint
  color: var(--vs-sub)
  font-size: 13px
  margin: 0 0 14px

.fail-actions, .act-row
  display: flex
  gap: 12px
  flex-wrap: wrap
  justify-content: center

.act-row
  padding-top: 12px
  border-top: 1px solid var(--vs-line)
</style>
