<script setup lang="ts">
/**
 * CalibrationPanel：音域标定对话框（FR-1006 / D-20，可跳过）。
 * 录音区引导标定与 P11 主动重新标定共用；
 * 流程：读取标定文本 → 录音（40 秒）→ 上传 purpose=calibration → POST 标定。
 * 未标定可直接「跳过标定，直接录音」，不影响评分与结果展示。
 */
import { onMounted, ref, watch } from 'vue'
import { QDialog } from 'quasar'
import { useCalibration } from '@/features/calibration'
import { errorCopy } from '@/copy/usePageCopy'
import { usePlayerStore } from '@/stores/player'

const props = defineProps<{
  open: boolean
  /** 标定成功回调（检测流程自动重提交 / P11 刷新状态） */
}>()

const emit = defineEmits<{
  (e: 'done'): void
  (e: 'cancel'): void
}>()

const calibration = useCalibration()
const player = usePlayerStore()
const wasOpen = ref(false)

onMounted(() => {
  if (props.open) void calibration.loadText()
})

watch(
  () => props.open,
  (open) => {
    if (open && !wasOpen.value) void calibration.loadText()
    if (!open) calibration.reset()
    wasOpen.value = open
  },
)

// 录音结束（手动停止或 40 秒上限）只能从 recorder 状态感知：
// 监听 phase 本身永远不会触发（phase 正是要靠这里推进）
watch(
  () => calibration.recorder.status,
  (status) => {
    if (status === 'recorded') calibration.onStop()
  },
)

async function submit() {
  const ok = await calibration.submit()
  if (ok) emit('done')
}
</script>

<template>
  <QDialog
    :model-value="open"
    :persistent="true"
    @update:model-value="(value: boolean) => !value && emit('cancel')"
  >
    <div class="calibration-panel" role="dialog" aria-label="音域标定">
      <header class="cal-head">
        <h2>先做一次音域标定</h2>
        <p>标定让你和标准曲线站在同一把「尺子」上比较，不同音高的人都能公平对比。只需要一次，很快。也可以跳过标定，直接录音检测。</p>
      </header>

      <!-- 读取标定文本 -->
      <p v-if="calibration.phase.value === 'loading-text'" class="cal-loading">正在读取标定文本…</p>

      <!-- 朗读 + 录音 -->
      <template v-if="calibration.info.value && calibration.phase.value !== 'success'">
        <div class="cal-text">
          <h3>请朗读下面这段文字</h3>
          <p class="cal-passage">{{ calibration.info.value.text }}</p>
          <p class="cal-note">用平常说话的音高自然朗读，不用刻意高或低。</p>
        </div>

        <div v-if="calibration.failAdvice.value" class="cal-fail">
          <p class="cal-fail-title">这次标定没有成功</p>
          <p>{{ calibration.failAdvice.value }}</p>
          <button type="button" class="cal-btn" @click="calibration.startRecording()">再试一次</button>
        </div>

        <div v-else-if="calibration.phase.value === 'intro'" class="cal-actions">
          <button type="button" class="cal-btn primary" @click="calibration.startRecording()">
            ● 开始朗读录音
          </button>
        </div>

        <div v-else-if="calibration.phase.value === 'recording'" class="cal-recording">
          <p class="cal-recording-hint">录音中…读完后点「停止」（最长 40 秒）</p>
          <span class="cal-timer">{{ (calibration.recorder.elapsedMs / 1000).toFixed(1) }}s</span>
          <button type="button" class="cal-btn stop" @click="calibration.recorder.stop()">■ 停止</button>
        </div>

        <div
          v-else-if="calibration.phase.value === 'recorded' || calibration.phase.value === 'uploading' || calibration.phase.value === 'submitting'"
          class="cal-recorded"
        >
          <button
            v-if="calibration.recorder.blobUrl"
            type="button"
            class="cal-btn"
            @click="player.play({ key: 'cal-preview', url: calibration.recorder.blobUrl! })"
          >
            {{ player.isCurrent('cal-preview') ? '⏸ 暂停试听' : '▶ 试听' }}
          </button>
          <button type="button" class="cal-btn" :disabled="calibration.busy.value" @click="calibration.discard()">
            重录
          </button>
          <button type="button" class="cal-btn primary" :disabled="calibration.busy.value" @click="submit">
            {{ calibration.busy.value ? '处理中…' : '提交标定' }}
          </button>
        </div>
      </template>

      <!-- 成功 -->
      <div v-if="calibration.phase.value === 'success'" class="cal-success">
        <p>
          ✅ 标定完成{{ calibration.result.value ? `，你的音域约 ${Math.round(calibration.result.value.pitchRange.fLo)}–${Math.round(calibration.result.value.pitchRange.fHi)} Hz` : '' }}。
        </p>
        <button type="button" class="cal-btn primary" @click="emit('done')">继续</button>
      </div>

      <!-- 失败 -->
      <div v-if="calibration.phase.value === 'failed' && calibration.error.value" class="cal-fail">
        <p class="cal-fail-title">{{ errorCopy(calibration.error.value).title }}</p>
        <p>{{ errorCopy(calibration.error.value).hint }}</p>
        <button type="button" class="cal-btn" @click="calibration.loadText()">重试</button>
      </div>

      <footer class="cal-foot">
        <button type="button" class="cal-skip" @click="emit('cancel')">
          {{ calibration.phase.value === 'success' ? '关闭' : '跳过标定，直接录音' }}
        </button>
      </footer>
    </div>
  </QDialog>
</template>

<style scoped lang="sass">
.calibration-panel
  background: #fff
  border-radius: 14px
  padding: 20px
  width: min(560px, 94vw)
  max-height: 88vh
  overflow: auto
  display: flex
  flex-direction: column
  gap: 14px

.cal-head
  h2
    margin: 0 0 4px
    font-size: 18px
  p
    margin: 0
    font-size: 13px
    color: #78909c

.cal-loading
  color: #90a4ae
  text-align: center

.cal-text
  background: #e0f2f1
  border-radius: 10px
  padding: 14px
  h3
    margin: 0 0 8px
    font-size: 15px
    color: #00695c

.cal-passage
  font-size: 18px
  line-height: 2
  margin: 0 0 8px
  color: #004d40

.cal-note
  margin: 0
  font-size: 13px
  color: #00796b

.cal-actions, .cal-recorded, .cal-recording
  display: flex
  gap: 10px
  align-items: center
  justify-content: center
  flex-wrap: wrap

.cal-recording
  flex-direction: column

.cal-recording-hint
  margin: 0
  color: #d32f2f
  font-size: 14px

.cal-timer
  font-variant-numeric: tabular-nums
  font-size: 24px
  font-weight: 700
  color: #d32f2f

.cal-btn
  min-height: 48px
  min-width: 110px
  padding: 6px 22px
  border-radius: 999px
  border: 2px solid #90a4ae
  background: #fff
  cursor: pointer
  font-size: 15px
  &.primary
    border-color: #00897b
    background: #00897b
    color: #fff
    font-weight: 700
  &.stop
    border-color: #455a64
    background: #455a64
    color: #fff
  &:disabled
    opacity: 0.55
    cursor: default

.cal-fail
  background: #fff3e0
  border: 1px solid #ffb74d
  border-radius: 10px
  padding: 12px 16px
  display: flex
  flex-direction: column
  gap: 8px
  align-items: flex-start
  p
    margin: 0
    font-size: 14px
    color: #5d4037

.cal-fail-title
  font-weight: 700
  color: #bf360c

.cal-success
  background: #e8f5e9
  border: 1px solid #a5d6a7
  border-radius: 10px
  padding: 16px
  display: flex
  flex-direction: column
  gap: 10px
  align-items: flex-start
  p
    margin: 0
    color: #1b5e20

.cal-foot
  text-align: center

.cal-skip
  background: none
  border: none
  color: #90a4ae
  font-size: 13px
  cursor: pointer
  min-height: 44px
</style>
