<script setup lang="ts">
/** TestTaskSection：P08 任务区（level 已就绪）：示范、朗读内容、标定、录音、提交 */
import { computed, onBeforeUnmount, toRef } from 'vue'
import { mediaUrl, type LevelDetail } from '@/api'
import { useAssessmentFlow } from '@/features/assessment'
import { usePlayerStore } from '@/stores/player'
import { useRecorderStore } from '@/stores/recorder'
import RecorderPanel from '@/components/RecorderPanel.vue'
import CalibrationPanel from '@/components/CalibrationPanel.vue'
import RecordingTips from '@/components/RecordingTips.vue'

const props = defineProps<{ level: LevelDetail }>()
const emit = defineEmits<{ (e: 'reload'): void }>()

const player = usePlayerStore()
const recorder = useRecorderStore()

const levelRef = toRef(props, 'level')
const flow = useAssessmentFlow({
  level: levelRef,
  // CONTENT_VERSION_CHANGED 后由 TestPage 重新拉取关卡详情（FR-907：按新任务重录）
  reloadLevel: async () => {
    emit('reload')
  },
})
const calibrating = computed(() => flow.state.value === 'calibrating')

const sampleKey = computed(() => `demo:${props.level.detection?.sampleMediaId ?? ''}`)

function playSample() {
  const mediaId = props.level.detection?.sampleMediaId
  if (!mediaId) return
  void player.play({ key: sampleKey.value, url: mediaUrl(mediaId), label: '参考示范' })
}

onBeforeUnmount(() => recorder.release())
</script>

<template>
  <div class="test-task">
    <!-- 进入前可听示范并看到朗读内容（FR-902） -->
    <section class="task-brief" aria-label="任务说明">
      <h2>要朗读的内容</h2>
      <p class="prompt-text">{{ level.detection?.promptText }}</p>
      <button v-if="level.detection?.sampleMediaId" type="button" class="sample-btn" @click="playSample">
        {{ player.isCurrent(sampleKey) ? '⏸ 暂停参考示范' : '▶ 听参考示范' }}
      </button>
    </section>

    <RecordingTips />

    <RecorderPanel
      :state="flow.state.value"
      :recorder-status="recorder.status"
      :elapsed-ms="recorder.elapsedMs"
      :blob-url="recorder.blobUrl"
      :has-take="recorder.hasPendingTake"
      :waveform="recorder.waveform"
      :error="flow.flowError.value"
      :busy="flow.busy.value"
      :recorder-error="recorder.error"
      @begin="flow.begin"
      @retry-mic="flow.requestMic"
      @start="flow.startRecording"
      @stop="flow.stopRecording"
      @re-record="flow.reRecord"
      @submit="flow.submit"
    />

    <RouterLink :to="`/learn/${level.id}`" class="to-learn">这一关还没学？先看示范和讲解 →</RouterLink>

    <CalibrationPanel :open="calibrating" @done="flow.onCalibrationDone" @cancel="flow.onCalibrationCancel" />
  </div>
</template>

<style scoped lang="sass">
.test-task
  display: flex
  flex-direction: column
  gap: 16px

.task-brief
  background: #fff
  border: 1px solid #eceff1
  border-radius: 12px
  padding: 16px
  h2
    margin: 0 0 8px
    font-size: 16px

.prompt-text
  font-size: 20px
  line-height: 2
  background: #fffde7
  border-radius: 8px
  padding: 10px 16px
  margin: 0 0 10px

.sample-btn
  min-height: 44px
  padding: 4px 18px
  border-radius: 999px
  border: 1px solid #00897b
  background: #e0f2f1
  color: #00695c
  cursor: pointer

.to-learn
  color: #00897b
  font-size: 14px
  text-decoration: none
  align-self: flex-start
</style>
