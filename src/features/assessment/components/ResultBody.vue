<script setup lang="ts">
/**
 * ResultBody：检测结果完成态的公共主体（FR-1001–1008）。
 * 关卡页内嵌结果区（InlineResultSection）与独立结果页（ResultPage）共用，
 * 避免同一展示结构两处复制维护：
 *   质量 → 分数 → 音高曲线 / 共振峰 / VOT / 频谱图 → 现象与四步。
 * 两页的少量差异经展示参数与插槽消化，不加行为开关：
 *   headingLevel——区块标题层级（独立页 h2、页内 h3）；
 *   formantHeight——共振峰图高度（页内取紧凑值，独立页用图表默认）；
 *   #after-quality 插槽——独立结果页的未标定引导插在质量提示与分数之间（原位置）；
 *   #score-actions 插槽——页内结果在分数旁并排放回放按钮（提供时分数区为横排）。
 * 回放按钮与底部行动区两页摆放位置不同（页内在分数旁、独立页在「回放与下一步」），
 * 由各页自行保留；处理中/失败/404 分支属页面外围，也不在此组件内。
 */
import { defineAsyncComponent, ref, watch } from 'vue'
import { QCard, QCardSection } from 'quasar'
import { audioFileUrl, audioSpectrogramPngUrl, mediaUrl, type AssessmentResult } from '@/api'
import QualityVerdict from './QualityVerdict.vue'
import ScoreCard from './ScoreCard.vue'
import PhenomenaList from './PhenomenaList.vue'
import FourStepsList from './FourStepsList.vue'

const ToneCurveChart = defineAsyncComponent(() => import('@/renderers/ToneCurveChart.vue'))
const FormantChart = defineAsyncComponent(() => import('@/renderers/FormantChart.vue'))
const VotWaveformChart = defineAsyncComponent(() => import('@/renderers/VotWaveformChart.vue'))

const props = defineProps<{
  /** 检测结果（useRecordingResult 的 result，完成态非空） */
  result: AssessmentResult
  /** 本次录音音频：频谱图与 VOT 波形取数用 */
  audioId: string
  /** 录音记录 id：音高曲线的片段试听等回跳用 */
  recordingId: string
  /** 区块标题层级：独立结果页 h2（默认）、页内结果 h3 */
  headingLevel?: 'h2' | 'h3'
  /** 共振峰图高度（px）：页内结果取紧凑值，独立页用图表默认 */
  formantHeight?: number
}>()

// 频谱图按 audioId 读取派生图片，加载失败时给说明而不是留破图；
// 结果（录音）变化时组件内自动重置，免去各页各自处理
const spectrogramError = ref(false)
watch(
  () => props.audioId,
  () => {
    spectrogramError.value = false
  },
)
</script>

<template>
  <!-- 录音质量提示（不拦截评分与可视化） -->
  <QualityVerdict v-if="result.quality" :quality="result.quality" />

  <!-- 页面专属插入位：独立结果页的未标定引导（保持在质量提示与分数之间） -->
  <slot name="after-quality" />

  <!-- 分数：页内结果经 #score-actions 在分数旁并排操作（否则独立页单独满宽展示） -->
  <div v-if="result.score && $slots['score-actions']" class="score-row">
    <ScoreCard :score="result.score" />
    <slot name="score-actions" />
  </div>
  <ScoreCard v-else-if="result.score" :score="result.score" />

  <!-- 音高曲线对比 -->
  <QCard v-if="result.curve" flat bordered class="result-section" aria-label="音高曲线对比">
    <QCardSection>
      <component :is="headingLevel ?? 'h2'">音高曲线对比</component>
      <p class="curve-note">实线是这次录音，虚线是标准参考；已按你的音域换算到统一标度；点线段表示该片段置信度较低。</p>
      <ToneCurveChart :curve="result.curve" :audio-id="audioId" :recording-id="recordingId" />
    </QCardSection>
  </QCard>

  <!-- 共振峰（单韵母关） -->
  <QCard v-if="result.formants" flat bordered class="result-section" aria-label="共振峰对比">
    <QCardSection>
      <component :is="headingLevel ?? 'h2'">共振峰对比</component>
      <FormantChart :formants="result.formants" :height="formantHeight" />
    </QCardSection>
  </QCard>

  <!-- 送气段波形对比（声母关） -->
  <QCard v-if="result.vot" flat bordered class="result-section" aria-label="送气段波形对比">
    <QCardSection>
      <component :is="headingLevel ?? 'h2'">送气段波形对比（VOT）</component>
      <p class="curve-note">横轴是时间，高亮区域是清辅音（送气/摩擦）噪声段，竖线是嗓音起始；两者间隔即 VOT——送气声母这段明显更长。</p>
      <VotWaveformChart
        :vot="result.vot"
        :user-audio-url="audioFileUrl(audioId)"
        :reference-audio-url="result.vot.referenceMediaId ? mediaUrl(result.vot.referenceMediaId) : undefined"
      />
    </QCardSection>
  </QCard>

  <!-- 频谱图 -->
  <QCard flat bordered class="result-section" aria-label="频谱图">
    <QCardSection>
      <component :is="headingLevel ?? 'h2'">频谱图</component>
      <p class="curve-note">横轴是时间，纵轴是频率，颜色越亮表示这一时刻该频率的能量越强，用来整体查看这次录音的频率能量分布。</p>
      <img
        v-if="!spectrogramError"
        :src="audioSpectrogramPngUrl(audioId)"
        alt="本次录音频谱图（时间×频率热力图）"
        loading="lazy"
        class="spectrogram-img"
        @error="spectrogramError = true"
      />
      <p v-else class="curve-note">频谱图暂时读取不到，可刷新页面重试。</p>
    </QCardSection>
  </QCard>

  <!-- 现象与四步 -->
  <PhenomenaList v-if="result.phenomena" :phenomena="result.phenomena" />
  <FourStepsList v-if="result.fourSteps" :steps="result.fourSteps" />
</template>

<style scoped lang="sass">
.result-section
  h2
    font-size: 18px
    margin: 0 0 10px
  h3
    font-size: 16px
    margin: 0 0 8px

.curve-note
  font-size: 13px
  color: #78909c
  margin: 0 0 8px

.score-row
  display: flex
  align-items: center
  gap: 16px
  flex-wrap: wrap

.spectrogram-img
  max-width: 100%
  border-radius: 8px
  background: #fff
</style>
