<script lang="ts">
/**
 * 模块级音频解码：<script setup> 顶层每实例执行，跨实例复用的
 * AudioContext 须放这里；只用来 decodeAudioData，不播放。
 */
let decodeContext: AudioContext | null = null
function getDecodeContext(): AudioContext {
  decodeContext ??= new AudioContext()
  return decodeContext
}
</script>

<script setup lang="ts">
/**
 * VotWaveformChart：送气段波形对比（VOT；FR-1005 / FD-16）。
 * 前端只取两侧音频解码出时域包络，后端下发的 onset/voicingOnset 时段做高亮与竖线；
 * 波形读取失败的一侧给占位说明，不阻断另一侧。
 * 本组件由页面异步加载，echarts 不进首屏包（§9）。
 */
import { computed, onMounted, provide, shallowRef } from 'vue'
import { use as echartsUse } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkAreaComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { ResultVot, VotSpan } from '@/api'

echartsUse([LineChart, GridComponent, TooltipComponent, MarkAreaComponent, MarkLineComponent, CanvasRenderer])

provide('echartsTheme', undefined)

const props = defineProps<{
  vot: ResultVot
  userAudioUrl: string
  referenceAudioUrl?: string
}>()

/* ------------------------------ 包络与解码 ------------------------------ */

interface WaveformEnvelope {
  durationSec: number
  /** 每桶 max |sample|（约 240 桶，值域 0–1） */
  peaks: number[]
}

const ENVELOPE_BUCKETS = 240

/** PCM 下采样为包络：每桶取最大绝对值 */
function toEnvelope(buffer: AudioBuffer): WaveformEnvelope {
  const channel = buffer.getChannelData(0)
  const bucketSize = Math.max(1, Math.floor(channel.length / ENVELOPE_BUCKETS))
  const peaks: number[] = []
  for (let i = 0; i * bucketSize < channel.length && i < ENVELOPE_BUCKETS; i += 1) {
    const start = i * bucketSize
    const end = Math.min(start + bucketSize, channel.length)
    let peak = 0
    for (let j = start; j < end; j += 1) {
      const value = Math.abs(channel[j] ?? 0)
      if (value > peak) peak = value
    }
    peaks.push(peak)
  }
  return { durationSec: buffer.duration, peaks }
}

async function decodeEnvelope(url: string): Promise<WaveformEnvelope> {
  const response = await fetch(url) // 默认同源带 cookie
  if (!response.ok) throw new Error(`audio fetch failed: ${response.status}`)
  const arrayBuffer = await response.arrayBuffer()
  const buffer = await getDecodeContext().decodeAudioData(arrayBuffer)
  return toEnvelope(buffer)
}

const userEnvelope = shallowRef<WaveformEnvelope | null>(null)
const userFailed = shallowRef(false)
const referenceEnvelope = shallowRef<WaveformEnvelope | null>(null)
const referenceFailed = shallowRef(false)

const hasReference = computed(() => Boolean(props.referenceAudioUrl))

onMounted(() => {
  // 任一侧失败不阻断另一侧
  void Promise.allSettled([
    decodeEnvelope(props.userAudioUrl)
      .then((envelope) => {
        userEnvelope.value = envelope
      })
      .catch(() => {
        userFailed.value = true
      }),
    props.referenceAudioUrl
      ? decodeEnvelope(props.referenceAudioUrl)
          .then((envelope) => {
            referenceEnvelope.value = envelope
          })
          .catch(() => {
            referenceFailed.value = true
          })
      : Promise.resolve(),
  ])
})

/* ------------------------------ 顶部摘要（FR-1005） ------------------------------ */

const ASPIRATION_GUIDANCE: Record<NonNullable<ResultVot['aspiration']>, string> = {
  aspirated: '送气越长，清辅音后面的气流越强；对比你和示范的送气段长度。',
  unaspirated: '不送气声母的除阻应干脆，送气段应很短。',
  fricative: '擦音的摩擦段（噪声）之后应尽快转入嗓音。',
  voiced: '对比清辅音起始到嗓音起始的时段。',
}

const unavailable = computed(() => props.vot.status !== 'ok')

/** aspiration 分类的一句话 + 本次与示范的差值 */
const summaryText = computed(() => {
  if (unavailable.value) return ''
  const guidance = ASPIRATION_GUIDANCE[props.vot.aspiration ?? 'voiced']
  const userMs = props.vot.user?.votMs
  const referenceMs = props.vot.reference?.votMs
  if (typeof userMs !== 'number' || typeof referenceMs !== 'number') return guidance
  const delta = Math.round(userMs - referenceMs)
  const diff = delta === 0 ? '本次与示范的 VOT 长度基本一致。' : `本次比示范${delta > 0 ? '长' : '短'}约 ${Math.abs(delta)} ms。`
  return `${guidance}${diff}`
})

/* ------------------------------ 每侧图表 ------------------------------ */

interface SideView {
  key: 'user' | 'reference'
  title: string
  envelope: WaveformEnvelope | null
  failed: boolean
  span: VotSpan | null | undefined
  color: string
}

function sideTitle(label: string, span: VotSpan | null | undefined): string {
  return span ? `${label} · VOT ${Math.round(span.votMs)} ms` : label
}

const sides = computed<SideView[]>(() => {
  const list: SideView[] = [
    {
      key: 'user',
      title: sideTitle('我的录音', props.vot.user),
      envelope: userEnvelope.value,
      failed: userFailed.value,
      span: props.vot.user,
      color: '#0288d1',
    },
  ]
  if (hasReference.value) {
    list.push({
      key: 'reference',
      title: sideTitle('参考示范', props.vot.reference),
      envelope: referenceEnvelope.value,
      failed: referenceFailed.value,
      span: props.vot.reference,
      color: '#6a4c93',
    })
  }
  return list
})

/** env 与 -env 两条 line + 同色 areaStyle（默认以 0 为基线）拼出对称波形带 */
function optionFor(side: SideView) {
  const envelope = side.envelope!
  const points = envelope.peaks.map((peak, index) => {
    const t = Number((((index + 0.5) / envelope.peaks.length) * envelope.durationSec).toFixed(3))
    return [t, Number(peak.toFixed(3))] as [number, number]
  })
  const mirrored = points.map(([t, peak]) => [t, -peak] as [number, number])
  const span = side.span
  const areaColor = 'rgba(77, 182, 172, 0.16)'
  return {
    animationDuration: 200,
    grid: { left: 20, right: 20, top: 10, bottom: 26 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const first = (Array.isArray(params) ? params[0] : params) as { data: [number, number] } | undefined
        const t = first?.data?.[0]
        return typeof t === 'number' ? `${t.toFixed(2)} 秒` : ''
      },
    },
    xAxis: {
      type: 'value' as const,
      name: '时间（秒）',
      nameLocation: 'middle' as const,
      nameGap: 22,
      min: 0,
      max: envelope.durationSec,
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value' as const,
      min: -1.05,
      max: 1.05,
      show: false,
    },
    series: [
      {
        name: side.title,
        type: 'line' as const,
        data: points,
        showSymbol: false,
        lineStyle: { width: 1, color: side.color },
        itemStyle: { color: side.color },
        areaStyle: { color: side.color, opacity: 0.3 },
        markArea: {
          silent: true,
          itemStyle: { color: areaColor },
          label: { show: false },
          data: span ? [[{ xAxis: span.onsetSec }, { xAxis: span.voicingOnsetSec }]] : [],
        },
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          lineStyle: { color: '#00897b', type: 'solid' as const, width: 1.5 },
          label: { formatter: '嗓音起始', position: 'insideEndTop' as const, fontSize: 11, color: '#546e7a' },
          data: span ? [{ xAxis: span.voicingOnsetSec }] : [],
        },
      },
      {
        name: `${side.title}（负包络）`,
        type: 'line' as const,
        data: mirrored,
        showSymbol: false,
        lineStyle: { width: 1, color: side.color },
        itemStyle: { color: side.color },
        areaStyle: { color: side.color, opacity: 0.3 },
        silent: true,
      },
    ],
  }
}
</script>

<template>
  <div class="vot-waveform-chart">
    <div v-if="unavailable" class="curve-unavailable">
      <p>本次没有可用的送气段对比。</p>
      <p class="reason">{{ vot.note ?? '这条录音未能定位清辅音起始与嗓音起始，不做伪造展示。' }}</p>
    </div>

    <template v-else>
      <p class="vot-summary">{{ summaryText }}</p>

      <div v-for="side in sides" :key="side.key" class="vot-side">
        <p class="side-title">{{ side.title }}</p>
        <VChart
          v-if="side.envelope"
          :option="optionFor(side)"
          :style="{ height: '150px', width: '100%' }"
          autoresize
        />
        <div v-else-if="side.failed" class="side-placeholder">
          波形读取不到，可能是音频已过期或网络中断；刷新页面可重试。送气段标注仍以后端时段为准。
        </div>
        <div v-else class="side-placeholder loading">正在读取波形…</div>
      </div>

      <p v-if="!hasReference" class="reference-missing-note">这一关暂无参考示范音频，只展示本次录音的波形与标注。</p>
    </template>
  </div>
</template>

<style scoped lang="sass">
.vot-waveform-chart
  width: 100%

.vot-summary
  font-size: 13px
  color: #546e7a
  margin: 0 0 10px

.vot-side
  & + .vot-side
    margin-top: 10px

.side-title
  font-size: 13px
  font-weight: 600
  color: #37474f
  margin: 0 0 4px

.side-placeholder
  height: 150px
  display: flex
  align-items: center
  justify-content: center
  padding: 0 16px
  text-align: center
  font-size: 13px
  color: #90a4ae
  background: #fafafa
  border: 1px dashed #cfd8dc
  border-radius: 8px

  &.loading
    color: #b0bec5

.reference-missing-note
  font-size: 12px
  color: #90a4ae
  margin: 8px 0 0

.curve-unavailable
  padding: 20px 12px
  text-align: center
  color: #546e7a
  background: #fafafa
  border: 1px dashed #cfd8dc
  border-radius: 8px
  p
    margin: 4px 0
  .reason
    font-size: 13px
    color: #90a4ae
</style>
