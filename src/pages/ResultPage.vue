<script setup lang="ts">
/**
 * P09 结果页（FR-1001–1008 / §6.4）：
 * 202 → ProcessingStage 轮询（页面隐藏暂停）；
 * 完成态主体复用 ResultBody（质量/分数/曲线/共振峰/频谱图/现象/四步，与页内结果共用），
 * 页面专属：标题、未标定引导（插在质量与分数之间的原位置）、回放与下一步、
 * AcousticDetail；404 → 「记录不存在或不可见」；同键重试仅当从提交页跳转（FD-15）。
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { audioFileUrl } from '@/api'
import { useRecordingResult } from '@/features/result'
import { usePlayerStore } from '@/stores/player'
import { useLevelsStore } from '@/stores/levels'
import { useContextStore } from '@/stores/context'
import AcousticDetail from '@/components/AcousticDetail.vue'
import ProcessingStage from '@/features/assessment/components/ProcessingStage.vue'
import PageState from '@/components/PageState.vue'
import PageHead from '@/components/ui/PageHead.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import ResultBody from '@/features/assessment/components/ResultBody.vue'

const route = useRoute()
const router = useRouter()
const player = usePlayerStore()
const levelsStore = useLevelsStore()
const contextStore = useContextStore()

const recordingId = computed(() => String(route.params.id ?? ''))
const result = useRecordingResult(recordingId)

const phase = result.phase
const recording = result.recording
const assessment = result.result

const playbackKey = computed(() => `audio:${recording.value?.audioId ?? ''}`)

function playRecording() {
  const audioId = recording.value?.audioId
  if (!audioId) return
  void player.play({ key: playbackKey.value, url: audioFileUrl(audioId), label: '本次录音' })
}

const levelTitle = computed(() => {
  const levelId = recording.value?.levelId ?? assessment.value?.levelId
  return levelId ? (levelsStore.byId.get(levelId)?.title ?? levelId) : ''
})

/** 专业与声学说明（FR-610 改版）：正文从关卡页后移到完整检测结果页 */
const professionalText = ref<string | null>(null)

watch(
  () => recording.value?.levelId ?? null,
  (levelId) => {
    professionalText.value = null
    if (!levelId) return
    // 与关卡页共用 levels store 的详情入口：保持一次性拉取（不套用先缓存后刷新）
    levelsStore
      .loadLevelDetail(levelId, { force: true })
      .then((detail) => {
        professionalText.value = detail.professional?.description || null
      })
      .catch(() => {
        professionalText.value = null
      })
  },
  { immediate: true },
)

const retryable = computed(
  () => phase.value === 'failed' && result.entry.value?.recordingId === recordingId.value,
)

/** 同键重试：后端重放产生新记录 ID 时跟随跳转（其余情况原地重查） */
async function onRetrySubmission() {
  const outcome = await result.retrySubmission()
  if (outcome?.changed) void router.push(`/result/${outcome.recordingId}`)
}
</script>

<template>
  <div class="result-page">
    <!-- 处理中（202 轮询） -->
    <ProcessingStage
      v-if="phase === 'processing' || phase === 'loading'"
      :stage="result.stage.value"
    />

    <!-- 404：过期或不可见 -->
    <PageState
      v-else-if="phase === 'not-found'"
      state="not-visible"
      text="记录不存在或不可见"
    />

    <!-- 失败（504 / 500 等） -->
    <div v-else-if="phase === 'failed'" class="result-failed vs-card">
      <h1>这次检测没有完成</h1>
      <p class="fail-hint">可能是评分服务繁忙或处理超时。</p>
      <div class="fail-actions">
        <button v-if="retryable" type="button" class="vs-btn" @click="onRetrySubmission">重试本次提交</button>
        <RouterLink :to="result.retakeRoute()" class="vs-btn vs-btn--ghost">重新录音</RouterLink>
      </div>
    </div>

    <!-- 已完成 -->
    <template v-else-if="assessment && recording">
      <PageHead :title="`${levelTitle} · 检测结果`" icon="wave" />

      <!-- 完成态公共主体：质量 / 分数 / 声学对比图 / 现象与四步（与页内结果共用） -->
      <ResultBody :result="assessment" :audio-id="recording.audioId" :recording-id="recordingId">
        <!-- 未标定 → 个人对比入口（FR-1006）：经插槽保持在质量提示与分数之间 -->
        <template #after-quality>
          <div v-if="contextStore.isAuthenticated && !contextStore.calibrationValid" class="calib-entry">
            <p>本次结果用的是通用参考范围，还没有你的个人音域与元音空间。</p>
            <RouterLink to="/account#calibration" class="vs-btn vs-btn--small">去标定以获得更精准对比</RouterLink>
          </div>
        </template>
      </ResultBody>

      <!-- 专业与声学说明（FR-610 改版）：正文自关卡页后移至此 -->
      <section v-if="professionalText" class="result-section vs-card" aria-label="专业与声学说明">
        <h2>专业与声学说明</h2>
        <p class="pro-content">{{ professionalText }}</p>
      </section>

      <!-- 回放与行动（FR-1008） -->
      <section class="result-section vs-card" aria-label="回放与下一步">
        <h2>回放与下一步</h2>
        <div class="act-row">
          <button type="button" class="vs-btn vs-btn--ghost" @click="playRecording">
            <AppIcon :name="player.isCurrent(playbackKey) ? 'pause' : 'play'" size="sm" />
            {{ player.isCurrent(playbackKey) ? '暂停本次录音' : '回放本次录音' }}
          </button>
          <RouterLink
            v-if="levelsStore.byId.get(recording.levelId)"
            :to="`/learn/${recording.levelId}`"
            class="vs-btn vs-btn--ghost"
          >
            回关卡练习
          </RouterLink>
          <RouterLink :to="result.retakeRoute()" class="vs-btn vs-btn--ghost">重录一次</RouterLink>
        </div>
      </section>

      <!-- 原始声学折叠区（FD-16） -->
      <AcousticDetail v-if="recording.audioId" :audio-id="recording.audioId" />
    </template>
  </div>
</template>

<style scoped lang="sass">
.result-page
  max-width: 820px
  margin: 0 auto
  display: flex
  flex-direction: column
  gap: 16px

.result-section
  padding: 24px
  h2
    font-size: 20px
    font-weight: 900
    letter-spacing: -0.3px
    margin: 0 0 10px

.pro-content
  white-space: pre-wrap
  line-height: 1.8
  color: var(--vs-ink2)
  margin: 0
  font-size: 13.5px

.calib-entry
  background: var(--vs-brand-soft)
  border: 1px solid var(--vs-brand-line)
  border-radius: 8px
  padding: 14px 18px
  display: flex
  align-items: center
  justify-content: space-between
  gap: 14px
  flex-wrap: wrap
  p
    margin: 0
    font-size: 13.5px
    color: var(--vs-sub)

.result-failed
  text-align: center
  padding: 40px 24px
  h1
    font-size: 20px
    font-weight: 900
    margin: 0 0 6px
  .fail-hint
    color: var(--vs-sub)
    font-size: 14px
    margin: 0 0 16px

.fail-actions, .act-row
  display: flex
  gap: 12px
  flex-wrap: wrap
  justify-content: center
</style>
