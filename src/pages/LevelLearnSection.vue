<script setup lang="ts">
/**
 * LevelLearnSection：关卡页内容区（level 已就绪）。
 * 在此一次性建立 quiz / practice / assessment 流程（level 引用稳定）。
 */
import { computed, onBeforeUnmount, ref, toRef } from 'vue'
import { mediaUrl, type LevelDetail } from '@/api'
import { useQuiz } from '@/features/quiz'
import { usePractice } from '@/features/practice'
import { useAssessmentFlow } from '@/features/assessment'
import { useComparePanel } from '@/features/compare'
import { useLevelsStore } from '@/stores/levels'
import { useRecorderStore } from '@/stores/recorder'
import LevelView from '@/renderers/LevelView.vue'
import LevelNav from '@/components/LevelNav.vue'
import ComparePanel from '@/components/ComparePanel.vue'
import RecorderPanel from '@/components/RecorderPanel.vue'
import CalibrationPanel from '@/components/CalibrationPanel.vue'
import FeedbackWidget from '@/components/FeedbackWidget.vue'

const props = defineProps<{ level: LevelDetail }>()
const emit = defineEmits<{ (e: 'reload'): void }>()

const levelsStore = useLevelsStore()
const recorder = useRecorderStore()

const levelRef = toRef(props, 'level')

const quiz = useQuiz(props.level)
const practice = usePractice(props.level)

const flow = useAssessmentFlow({
  level: levelRef,
  reloadLevel: async () => {
    emit('reload')
  },
})

const compare = useComparePanel()
const compareOpen = computed(() => compare.pair.value !== null)
const calibrating = computed(() => flow.state.value === 'calibrating')

const canAssess = computed(() => props.level.detection?.available !== false)
const quizDoneIds = computed(() => new Set(quiz.passedIds.value))

function openPair(aId: string, bId: string) {
  void compare.open(aId, bId)
}

const confusablePairsHere = computed(() =>
  levelsStore.confusablePairs.filter((pair) => pair.a === props.level.id || pair.b === props.level.id),
)

function otherId(pair: { a: string; b: string }): string {
  return pair.a === props.level.id ? pair.b : pair.a
}

onBeforeUnmount(() => recorder.release())
</script>

<template>
  <div class="level-learn">
    <LevelView
      :level="level"
      :media-resolver="mediaUrl"
      :practice-done-ids="practice.doneIds.value"
      :interactive="true"
      @quiz-answer="(payload) => quiz.answerById(payload)"
      @practice-done="(payload) => practice.markDoneById(payload)"
      @practice-redo="(payload) => practice.redoById(payload)"
    >
      <template #assessment>
        <!-- 熔断：检测入口显示故障说明，学习入口保留（D-05 / NFR-11） -->
        <div v-if="!canAssess" class="detection-off" role="note">
          <p>🎤 录音检测暂停中（维护中），学习内容不受影响。</p>
          <RouterLink to="/library" class="off-link">先去学习其他关卡</RouterLink>
        </div>
        <template v-else>
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
          <p class="task-prompt">
            朗读内容：<strong>{{ level.detection?.promptText }}</strong>
          </p>
          <p v-if="level.detection?.reliabilityNote" class="task-note">{{ level.detection?.reliabilityNote }}</p>
        </template>
      </template>
    </LevelView>

    <LevelNav :level="level" />

    <section v-if="confusablePairsHere.length > 0" class="confusable-entry" aria-label="易混关比较入口">
      <button
        v-for="pair in confusablePairsHere"
        :key="`${pair.a}-${pair.b}`"
        type="button"
        class="compare-open"
        @click="openPair(pair.a, pair.b)"
      >
        和「{{ levelsStore.byId.get(otherId(pair))?.title ?? otherId(pair) }}」并排比较 →
      </button>
    </section>

    <FeedbackWidget mode="understanding" :source-page="`/learn/${level.id}`" :level-id="level.id" />
    <FeedbackWidget mode="correction" :source-page="`/learn/${level.id}`" :level-id="level.id" />

    <CalibrationPanel
      :open="calibrating"
      @done="flow.onCalibrationDone"
      @cancel="flow.onCalibrationCancel"
    />
    <ComparePanel
      :open="compareOpen"
      :detail-a="compare.detailA.value"
      :detail-b="compare.detailB.value"
      :loading="compare.loading.value"
      :error="compare.error.value"
      @close="compare.close()"
    />
  </div>
</template>

<style scoped lang="sass">
.detection-off
  background: #eceff1
  border: 1px solid #cfd8dc
  border-radius: 10px
  padding: 14px 16px
  p
    margin: 0 0 8px
    color: #546e7a

.off-link
  color: #00897b
  font-weight: 600
  text-decoration: none

.task-prompt
  font-size: 15px
  background: #fffde7
  border: 1px solid #ffe082
  border-radius: 8px
  padding: 10px 14px

.task-note
  font-size: 12px
  color: #90a4ae

.confusable-entry
  margin-top: 18px

.compare-open
  min-height: 44px
  padding: 4px 18px
  border-radius: 999px
  border: 1px solid #0288d1
  background: #e1f5fe
  color: #01579b
  cursor: pointer
  margin-right: 8px
</style>
