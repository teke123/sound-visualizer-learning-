<script setup lang="ts">
/**
 * LevelLearnSection：关卡页内容区（level 已就绪，P05 = 学习与录音检测一体，FR-609）。
 * 在此一次性建立 quiz / practice / assessment 流程（level 引用稳定）。
 */
import { computed, onBeforeUnmount, ref, toRef } from 'vue'
import { detectionApi, mediaUrl, type LevelDetail } from '@/api'
import { useAssessmentFlow } from '@/features/assessment'
import { useContextStore } from '@/stores/context'
import { useRecorderStore } from '@/stores/recorder'
import LevelView from '@/renderers/LevelView.vue'
import LevelNav from '@/components/LevelNav.vue'
import CompactReferenceBar from '@/components/CompactReferenceBar.vue'
import RecorderPanel from './RecorderPanel.vue'
import CalibrationPanel from './CalibrationPanel.vue'
import FeedbackWidget from '@/components/FeedbackWidget.vue'
import InlineResultSection from './InlineResultSection.vue'
import { toneOfPinyin, type PitchRangeHz } from '@/utils/realtimeAcoustics'

const props = defineProps<{ level: LevelDetail }>()
const emit = defineEmits<{ (e: 'reload'): void }>()

const recorder = useRecorderStore()
const contextStore = useContextStore()

const levelRef = toRef(props, 'level')

/** 页内结果区当前展示的记录（null = 未提交/已重录，隐藏结果区） */
const activeRecordingId = ref<string | null>(null)

const flow = useAssessmentFlow({
  level: levelRef,
  reloadLevel: async () => {
    emit('reload')
  },
  // 页内结果闭环（docs §3.2）：提交成功不跳转，结果区原地展开并滚动到录音区附近
  onSubmitted: (recordingId) => {
    activeRecordingId.value = recordingId
    document.getElementById('record')?.scrollIntoView({ behavior: 'smooth' })
  },
})

/** 「再录一次」：收起页内结果，回到待录状态 */
function onReRecord() {
  activeRecordingId.value = null
  flow.reRecord()
}

const calibrating = computed(() => flow.state.value === 'calibrating')

/** 实时反馈主视图按关卡层聚焦：声母关看送气/摩擦包络，其余看音高轨迹（FR-907） */
const realtimeFocus = computed<'pitch' | 'onset'>(() => (props.level.layer === 'initial' ? 'onset' : 'pitch'))
/** 目标调型：从关卡 pinyin 声调符号推导，推不出则不画五度刻度 */
const realtimeTargetTone = computed(() => toneOfPinyin(props.level.pinyin))

/** 个人音域（已标定时读一次并冻结，练习期间不重建；docs §1/§6.1） */
const realtimeRangeHz = ref<PitchRangeHz | null>(null)
function loadRealtimeRange() {
  if (!contextStore.isAuthenticated) return Promise.resolve()
  return detectionApi
    .getCalibration()
    .then((info) => {
      const r = info.data.pitchRange
      if (r && typeof r.fLo === 'number' && typeof r.fHi === 'number' && r.fLo < r.fHi) {
        realtimeRangeHz.value = { fLo: r.fLo, fHi: r.fHi }
      }
    })
    .catch(() => {
      /* 未标定/读取失败：回落自适应窗口 */
    })
}
const rangeReady = loadRealtimeRange()

async function startRecording() {
  await rangeReady
  await flow.startRecording()
}

/** 一键直录入口：先等音域数据就绪（通常挂载时已加载完），再走 begin 授权并自动开播 */
async function beginRecording() {
  await rangeReady
  await flow.begin()
}

async function onCalibrationDone() {
  await loadRealtimeRange()
  await flow.onCalibrationDone()
}

/** 直接关闭标定（× / 去登录）：回到待录状态，不进入录音流程 */
function onCalibrationDismiss() {
  flow.reRecord()
}

onBeforeUnmount(() => recorder.release())
</script>

<template>
  <div class="level-learn">
    <!-- 窄屏（<1024px）滚动到 #record 时的顶部紧凑参照栏（docs §3.1 响应式退化），自身 fixed 定位 -->
    <CompactReferenceBar :level="level" />

    <LevelView :level="level" :media-resolver="mediaUrl" :has-result="Boolean(activeRecordingId)">
      <template #assessment>
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
          @begin="beginRecording"
          @retry-mic="flow.requestMic"
          @start="startRecording"
          @stop="flow.stopRecording"
          @re-record="flow.reRecord"
          @submit="flow.submit"
        />
      </template>

      <template #result>
        <InlineResultSection
          v-if="activeRecordingId"
          :recording-id="activeRecordingId"
          :level-id="level.id"
          @re-record="onReRecord"
        />
      </template>
    </LevelView>

    <LevelNav :level="level" />

    <FeedbackWidget :source-page="`/learn/${level.id}`" :level-id="level.id" />

    <CalibrationPanel
      :open="calibrating"
      @done="onCalibrationDone"
      @cancel="flow.onCalibrationCancel"
      @dismiss="onCalibrationDismiss"
    />
  </div>
</template>

<style scoped lang="sass">
.level-learn
  padding-bottom: 4px
</style>
