<script setup lang="ts">
/**
 * LevelLearnSection：关卡页内容区（level 已就绪，P05 = 学习与录音检测一体，FR-609）。
 * 在此一次性建立 quiz / practice / assessment 流程（level 引用稳定）。
 */
import { computed, onBeforeUnmount, ref, toRef } from 'vue'
import { detectionApi, mediaUrl, type LevelDetail } from '@/api'
import { useQuiz } from '@/features/quiz'
import { usePractice } from '@/features/practice'
import { useAssessmentFlow } from '@/features/assessment'
import { useComparePanel } from '@/features/compare'
import { useLevelsStore } from '@/stores/levels'
import { useContextStore } from '@/stores/context'
import { usePlayerStore } from '@/stores/player'
import { useRecorderStore } from '@/stores/recorder'
import LevelView from '@/renderers/LevelView.vue'
import LevelNav from '@/components/LevelNav.vue'
import ComparePanel from '@/components/ComparePanel.vue'
import RecorderPanel from '@/components/RecorderPanel.vue'
import CalibrationPanel from '@/components/CalibrationPanel.vue'
import FeedbackWidget from '@/components/FeedbackWidget.vue'
import { toneOfPinyin, type PitchRangeHz } from '@/utils/realtimeAcoustics'

const props = defineProps<{ level: LevelDetail }>()
const emit = defineEmits<{ (e: 'reload'): void }>()

const levelsStore = useLevelsStore()
const player = usePlayerStore()
const recorder = useRecorderStore()
const contextStore = useContextStore()

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

/** 本关录音区参考示范（FR-902：录音前可听示范） */
const sampleKey = computed(() => `demo:${props.level.detection?.sampleMediaId ?? ''}`)

function playSample() {
  const mediaId = props.level.detection?.sampleMediaId
  if (!mediaId) return
  void player.play({ key: sampleKey.value, url: mediaUrl(mediaId), label: '参考示范' })
}

function openPair(aId: string, bId: string) {
  void compare.open(aId, bId)
}

const confusablePairsHere = computed(() =>
  levelsStore.confusablePairs.filter((pair) => pair.a === props.level.id || pair.b === props.level.id),
)

function otherId(pair: { a: string; b: string }): string {
  return pair.a === props.level.id ? pair.b : pair.a
}

/** 实时反馈主视图按关卡层聚焦：声母关看送气/摩擦包络，其余看音高轨迹（FR-907） */
const realtimeFocus = computed<'pitch' | 'onset'>(() => (props.level.layer === 'initial' ? 'onset' : 'pitch'))
/** 目标调型：从关卡 pinyin 声调符号推导，推不出则不画引导带 */
const realtimeTargetTone = computed(() => toneOfPinyin(props.level.pinyin))

/** 个人音域（已标定时读一次并冻结，练习期间不重建；docs §1/§6.1） */
const realtimeRangeHz = ref<PitchRangeHz | null>(null)
if (contextStore.isAuthenticated) {
  void detectionApi
    .getCalibration()
    .then((info) => {
      const r = info.pitchRange
      if (r && typeof r.fLo === 'number' && typeof r.fHi === 'number' && r.fLo < r.fHi) {
        realtimeRangeHz.value = { fLo: r.fLo, fHi: r.fHi }
      }
    })
    .catch(() => {
      /* 未标定/读取失败：回落自适应窗口 */
    })
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
        <!-- 录音前可听示范并看到朗读内容（FR-902） -->
        <p class="task-prompt">
          朗读内容：<strong>{{ level.detection?.promptText }}</strong>
        </p>
        <button
          v-if="level.detection?.sampleMediaId"
          type="button"
          class="sample-btn"
          @click="playSample"
        >
          {{ player.isCurrent(sampleKey) ? '⏸ 暂停参考示范' : '▶ 听参考示范' }}
        </button>
        <RecorderPanel
          :state="flow.state.value"
          :recorder-status="recorder.status"
          :elapsed-ms="recorder.elapsedMs"
          :blob-url="recorder.blobUrl"
          :has-take="recorder.hasPendingTake"
          :error="flow.flowError.value"
          :busy="flow.busy.value"
          :recorder-error="recorder.error"
          :focus="realtimeFocus"
          :target-tone="realtimeTargetTone"
          :range-hz="realtimeRangeHz"
          @begin="flow.begin"
          @retry-mic="flow.requestMic"
          @start="flow.startRecording"
          @stop="flow.stopRecording"
          @re-record="flow.reRecord"
          @submit="flow.submit"
        />
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

    <FeedbackWidget :source-page="`/learn/${level.id}`" :level-id="level.id" />

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
.task-prompt
  font-size: 15px
  background: #fffde7
  border: 1px solid #ffe082
  border-radius: 8px
  padding: 10px 14px
  margin: 0 0 10px

.sample-btn
  min-height: 44px
  padding: 4px 18px
  border-radius: 999px
  border: 1px solid #00897b
  background: #e0f2f1
  color: #00695c
  cursor: pointer
  margin-bottom: 12px

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
