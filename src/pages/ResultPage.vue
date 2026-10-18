<script setup lang="ts">
/**
 * P09 结果页（FR-1001–1008 / §6.4）：
 * 202 → ProcessingStage 轮询（页面隐藏暂停）；录音质量为友好提示、不拦截展示；
 * 分数、现象、曲线、共振峰（单韵母）、频谱图、四步、回放、AcousticDetail、保存状态；
 * 404 → 「记录不存在或不可见」；同键重试仅当从提交页跳转（FD-15）。
 */
import { computed, defineAsyncComponent, ref } from 'vue'
import { useRoute } from 'vue-router'
import { audioFileUrl, audioSpectrogramPngUrl, mediaUrl } from '@/api'
import { useRecordingResult } from '@/features/result'
import { usePlayerStore } from '@/stores/player'
import { useLevelsStore } from '@/stores/levels'
import { useContextStore } from '@/stores/context'
import QualityVerdict from '@/components/QualityVerdict.vue'
import ScoreCard from '@/components/ScoreCard.vue'
import PhenomenaList from '@/components/PhenomenaList.vue'
import FourStepsList from '@/components/FourStepsList.vue'
import AcousticDetail from '@/components/AcousticDetail.vue'
import SaveStatusBanner from '@/components/SaveStatusBanner.vue'
import ProcessingStage from '@/components/ProcessingStage.vue'
import PageState from '@/components/PageState.vue'

const ToneCurveChart = defineAsyncComponent(() => import('@/renderers/ToneCurveChart.vue'))
const FormantChart = defineAsyncComponent(() => import('@/renderers/FormantChart.vue'))
const VotWaveformChart = defineAsyncComponent(() => import('@/renderers/VotWaveformChart.vue'))

const route = useRoute()
const player = usePlayerStore()
const levelsStore = useLevelsStore()
const contextStore = useContextStore()

const recordingId = computed(() => String(route.params.id ?? ''))
const result = useRecordingResult(recordingId)

const phase = result.phase
const recording = result.recording
const assessment = result.result

const quality = computed(() => assessment.value?.quality)

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

const retryable = computed(
  () => phase.value === 'failed' && result.entry.value?.recordingId === recordingId.value,
)

// 频谱图按 audioId 读取派生图片（FR-1005），加载失败时说明而非留破图
const spectrogramError = ref(false)
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
    <div v-else-if="phase === 'failed'" class="result-failed">
      <h1>这次检测没有完成</h1>
      <p class="fail-hint">可能是评分服务繁忙或处理超时。</p>
      <div class="fail-actions">
        <button v-if="retryable" type="button" class="act-btn primary" @click="result.retrySubmission()">
          重试本次提交
        </button>
        <RouterLink :to="result.retakeRoute()" class="act-btn">重新录音</RouterLink>
      </div>
    </div>

    <!-- 已完成 -->
    <template v-else-if="assessment && recording">
      <header class="result-head">
        <h1>{{ levelTitle }} · 检测结果</h1>
      </header>

      <!-- 录音质量提示（FR-1001：友好提示，不拦截评分与可视化） -->
      <QualityVerdict v-if="quality" :quality="quality" />

      <!-- 未标定 → 个人对比入口（FR-1006） -->
      <div v-if="contextStore.isAuthenticated && !contextStore.calibrationValid" class="calib-entry">
        <p>本次结果用的是通用参考范围，还没有你的个人音域与元音空间。</p>
        <RouterLink to="/account#calibration" class="act-btn primary">去标定以获得更精准个人对比</RouterLink>
      </div>

      <!-- 分数（FR-1002） -->
      <ScoreCard v-if="typeof assessment.score === 'number'" :score="assessment.score" />

      <!-- 曲线对比（FR-1005） -->
      <section class="result-section" aria-label="音高曲线对比">
        <h2>音高曲线对比</h2>
        <p class="curve-note">实线是这次录音，虚线是标准参考；已按你的音域换算到统一标度。</p>
        <ToneCurveChart v-if="assessment.curve" :curve="assessment.curve" />
      </section>

      <!-- 共振峰（仅单韵母关，FR-1005） -->
      <section v-if="assessment.formants" class="result-section" aria-label="共振峰对比">
        <h2>共振峰对比</h2>
        <FormantChart :formants="assessment.formants" />
      </section>

      <!-- 送气段波形对比（声母关，FR-1005） -->
      <section v-if="assessment.vot" class="result-section" aria-label="送气段波形对比">
        <h2>送气段波形对比（VOT）</h2>
        <p class="curve-note">横轴是时间，高亮区域是清辅音（送气/摩擦）噪声段，竖线是嗓音起始；两者间隔即 VOT——送气声母这段明显更长。</p>
        <VotWaveformChart
          :vot="assessment.vot"
          :user-audio-url="audioFileUrl(recording.audioId)"
          :reference-audio-url="assessment.vot.referenceMediaId ? mediaUrl(assessment.vot.referenceMediaId) : undefined"
        />
      </section>

      <!-- 频谱图（FR-1005：时间×频率能量分布） -->
      <section class="result-section" aria-label="频谱图">
        <h2>频谱图</h2>
        <p class="curve-note">横轴是时间，纵轴是频率，颜色越亮表示这一时刻该频率的能量越强，用来整体查看这次录音的频率能量分布。</p>
        <img
          v-if="!spectrogramError"
          :src="audioSpectrogramPngUrl(recording.audioId)"
          alt="本次录音频谱图（时间×频率热力图）"
          loading="lazy"
          class="spectrogram-img"
          @error="spectrogramError = true"
        />
        <p v-else class="curve-note">频谱图暂时读取不到，可刷新页面重试。</p>
      </section>

      <!-- 现象（FR-1004） -->
      <PhenomenaList v-if="assessment.phenomena" :phenomena="assessment.phenomena" />

      <!-- 四步（FR-1007） -->
      <FourStepsList v-if="assessment.fourSteps" :steps="assessment.fourSteps" />

      <!-- 回放与行动（FR-1008） -->
      <section class="result-section" aria-label="回放与下一步">
        <h2>回放与下一步</h2>
        <div class="act-row">
          <button type="button" class="act-btn" @click="playRecording">
            {{ player.isCurrent(playbackKey) ? '⏸ 暂停本次录音' : '▶ 回放本次录音' }}
          </button>
          <RouterLink v-if="levelsStore.byId.get(recording.levelId)" :to="`/learn/${recording.levelId}`" class="act-btn">
            回关卡练习
          </RouterLink>
          <RouterLink :to="result.retakeRoute()" class="act-btn">重录一次</RouterLink>
        </div>
      </section>

      <!-- 原始声学折叠区（FD-16） -->
      <AcousticDetail v-if="recording.audioId" :audio-id="recording.audioId" />

      <!-- 保存状态：结果自动保存到声音档案（FR-1008） -->
      <SaveStatusBanner />
    </template>
  </div>
</template>

<style scoped lang="sass">
.result-page
  max-width: 760px
  margin: 0 auto
  display: flex
  flex-direction: column
  gap: 20px

.result-head h1
  margin: 0
  font-size: 22px

.result-section
  h2
    font-size: 18px
    margin: 0 0 10px

.curve-note
  font-size: 13px
  color: #78909c
  margin: 0 0 8px

.calib-entry
  background: #f1f8f6
  border: 1px solid #cce7e1
  border-radius: 14px
  padding: 14px 18px
  display: flex
  align-items: center
  justify-content: space-between
  gap: 14px
  flex-wrap: wrap
  p
    margin: 0
    font-size: 14px
    color: #546e7a

.spectrogram-img
  max-width: 100%
  border-radius: 8px
  background: #fff

.result-failed
  text-align: center
  padding: 32px 0
  h1
    font-size: 20px
    margin: 0 0 6px
  .fail-hint
    color: #78909c
    font-size: 14px
    margin: 0 0 16px

.fail-actions, .act-row
  display: flex
  gap: 12px
  flex-wrap: wrap
  justify-content: center

.act-btn
  min-height: 44px
  display: inline-flex
  align-items: center
  padding: 4px 18px
  border-radius: 999px
  border: 1px solid #90a4ae
  background: #fff
  color: #37474f
  text-decoration: none
  cursor: pointer
  font-size: 14px
  &.primary
    background: #00897b
    border-color: #00897b
    color: #fff
    font-weight: 600
</style>
