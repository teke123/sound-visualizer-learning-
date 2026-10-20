<script setup lang="ts">
/**
 * RealtimeAcousticCanvas：录音端实时声学反馈画布（FR-907 / FD-03）。
 *
 * - 声调/韵母关（focus='pitch'）主视图为 F0 音高轨迹（半音纵轴）+ 调型目标引导带，
 *   声母关（focus='onset'')主视图为时域能量包络，清音送气/摩擦段按谱重心配色；
 * - 录音中滚动显示最近 4 秒；停止后整段轨迹定格，供本地试听时画播放游标回看；
 * - PCM 经 AudioWorklet 采集、Worker 按固定采样步长分析；rAF 只负责绘制。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRecorderStore } from '@/stores/recorder'
import {
  AdaptivePitchWindow,
  degreeToSemitone,
  hzToSemitone,
  QUIET_RMS_HINT,
  rangeDegreeToSemitone,
  spectralCentroidHz,
  semitoneToHz,
  toneTargetContour,
  type PitchRangeHz,
  type AcousticFrame,
  type ToneValue,
} from '@/utils/realtimeAcoustics'

const props = withDefaults(
  defineProps<{
    /** 录音进行中；false 时定格整段回看 */
    active: boolean
    /** 主视图：声调/韵母关 'pitch'，声母关 'onset'（包络为主） */
    focus?: 'pitch' | 'onset'
    /** 本关目标调型（可从关卡 pinyin 声调符号推导）；无则不画引导带 */
    targetTone?: ToneValue | null
    /** 个人音域（前置标定）：1 度线=ST(fLo)、5 度线=ST(fHi)，画布 ±2 ST（docs §6.1） */
    rangeHz?: PitchRangeHz | null
    /** 试听播放游标（秒）；仅定格回看时生效 */
    playheadSec?: number | null
    takeDurationSec?: number | null
  }>(),
  { focus: 'pitch', targetTone: null, rangeHz: null, playheadSec: null, takeDurationSec: null },
)

const recorder = useRecorderStore()

const wrapEl = ref<HTMLDivElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)

/* ------------------------------ 展示态（节流） ------------------------------ */

const volumeLevel = ref<'quiet' | 'ok' | 'loud'>('ok')
const currentHz = ref<number | null>(null)
const centroidLabel = ref<string | null>(null)
let headerUpdatedAt = 0

const volumeText = computed(
  () => ({ quiet: '音量偏轻，凑近一点', ok: '音量适中', loud: '爆音！离麦克风远一点' })[volumeLevel.value],
)

const toneHint = computed(() => {
  if (!props.targetTone) return null
  return { 1: '一声 · 保持高平 →', 2: '二声 · 由中爬高 ↗', 3: '三声 · 先降后升 ∨', 4: '四声 · 果断下降 ↘' }[
    props.targetTone
  ]
})

/* ------------------------------ 分析与绘制状态（非响应式） ------------------------------ */

const LIVE_WINDOW_SEC = 4
let frames: AcousticFrame[] = []
let analysisWorker: Worker | null = null
let unsubscribePcm: (() => void) | null = null
let pitchWindow = new AdaptivePitchWindow()
let rafHandle: number | null = null
let lastFrameT = 0
let freqBuf: Uint8Array<ArrayBuffer> | null = null
let cssW = 0
let cssH = 0
let dpr = 1

function resetSession(): void {
  frames = []
  pitchWindow = new AdaptivePitchWindow()
  lastFrameT = 0
  headerUpdatedAt = 0
  currentHz.value = null
  centroidLabel.value = null
  volumeLevel.value = 'ok'
}

/* ------------------------------ 帧循环 ------------------------------ */

function startAnalysis(): void {
  const analyser = recorder.getAnalyser()
  if (!analyser) return
  const sampleRate = analyser.context.sampleRate
  const windowSize = 2 ** Math.ceil(Math.log2(Math.max(2048, sampleRate * 3 / 50)))
  const worker = new Worker(new URL('../workers/realtimeAcoustics.worker.ts', import.meta.url), { type: 'module' })
  analysisWorker = worker
  worker.postMessage({ type: 'init', sampleRate, windowSize, startSample: recorder.getRecordingStartSample() })
  worker.onmessage = ({ data }: MessageEvent<AcousticFrame[] | { type: 'flushed' }>) => {
    if (analysisWorker !== worker) return
    if (!Array.isArray(data)) {
      worker.terminate()
      analysisWorker = null
      draw()
      return
    }
    for (const frame of data) {
      if (frame.kind === 'unvoicedNoise') {
        freqBuf ??= new Uint8Array(new ArrayBuffer(analyser.frequencyBinCount))
        analyser.getByteFrequencyData(freqBuf)
        frame.centroidHz = spectralCentroidHz(freqBuf, sampleRate)
      }
      frames.push(frame)
      if (frame.f0Hz !== null) {
        pitchWindow.update(hzToSemitone(frame.f0Hz), Math.max(0, frame.t - lastFrameT))
      }
      lastFrameT = frame.t
    }
    const frame = data.at(-1)
    if (!frame) return
    const now = performance.now()
    if (now - headerUpdatedAt > 120) {
      headerUpdatedAt = now
      volumeLevel.value = frame.clipping ? 'loud' : frame.rms < QUIET_RMS_HINT ? 'quiet' : 'ok'
      currentHz.value = frame.f0Hz
      centroidLabel.value =
        frame.kind === 'unvoicedNoise' && frame.centroidHz && frame.centroidHz > 5000
          ? `摩擦偏高频 ≈${(frame.centroidHz / 1000).toFixed(1)}kHz（接近平舌）`
          : frame.kind === 'unvoicedNoise' && frame.centroidHz
            ? `摩擦偏中低频 ≈${(frame.centroidHz / 1000).toFixed(1)}kHz（接近翘舌）`
            : null
    }
  }
  unsubscribePcm = recorder.subscribePcm((samples, startSample) => {
    worker.postMessage({ type: 'pcm', samples, startSample }, [samples.buffer])
  })
}

function loop(): void {
  if (!props.active) return
  draw()
  rafHandle = requestAnimationFrame(loop)
}

function stopLoop(drain = false): void {
  if (rafHandle !== null) cancelAnimationFrame(rafHandle)
  rafHandle = null
  unsubscribePcm?.()
  unsubscribePcm = null
  if (drain && analysisWorker) {
    // 消费已发送的 PCM 后再定格，保留 Worker 队列中的录音尾段。
    analysisWorker.postMessage({ type: 'flush' })
  } else {
    analysisWorker?.terminate()
    analysisWorker = null
  }
}

/* ------------------------------ 绘制 ------------------------------ */

const COLOR = {
  voiced: '#26a69a',
  head: '#00897b',
  noiseHigh: '#00acc1',
  noiseLow: '#fb8c00',
  silence: '#cfd8dc',
  clip: '#d32f2f',
  band: 'rgba(38, 166, 154, 0.14)',
  bandLine: 'rgba(0, 137, 123, 0.55)',
  grid: '#eceff1',
  text: '#90a4ae',
} as const

function draw(): void {
  const canvas = canvasEl.value
  const ctx = canvas?.getContext('2d')
  if (!canvas || !ctx || cssW === 0 || cssH === 0) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cssW, cssH)

  if (frames.length === 0) {
    ctx.fillStyle = COLOR.text
    ctx.font = '12px system-ui, sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(props.active ? '开始发声后这里会出现你的声音' : '本次未录到声音', cssW / 2, cssH / 2)
    return
  }

  const lastT = frames.at(-1)!.t
  const tMin = props.active ? Math.max(0, lastT - LIVE_WINDOW_SEC) : 0
  const tMax = Math.max(lastT, 0.2)
  const padX = 8
  const plotW = cssW - padX * 2
  const xOf = (t: number) => padX + ((t - tMin) / (tMax - tMin)) * plotW

  // 主副视图占比：声调关 F0 为主，声母关包络为主
  const gap = 10
  const f0Ratio = props.focus === 'pitch' ? 0.72 : 0.34
  const f0Top = 12
  const f0H = Math.max(40, (cssH - f0Top - gap - 16) * f0Ratio)
  const envTop = f0Top + f0H + gap
  const envH = cssH - envTop - 4

  drawPitchLane(ctx, frames, tMin, tMax, padX, plotW, f0Top, f0H, xOf)
  drawEnvelopeLane(ctx, frames, xOf, envTop, envH, tMin, tMax)

  // 定格回看：试听游标
  if (!props.active && props.playheadSec != null && props.takeDurationSec && props.takeDurationSec > 0) {
    const x = padX + (props.playheadSec / props.takeDurationSec) * plotW
    ctx.strokeStyle = '#455a64'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.moveTo(x, 4)
    ctx.lineTo(x, cssH - 4)
    ctx.stroke()
  }
}

function drawPitchLane(
  ctx: CanvasRenderingContext2D,
  frames: Array<{ t: number; f0Hz: number | null; weak: boolean }>,
  tMin: number,
  tMax: number,
  padX: number,
  plotW: number,
  top: number,
  height: number,
  xOf: (t: number) => number,
): void {
  const fixed = props.rangeHz
  const stMin = fixed ? hzToSemitone(fixed.fLo) - 2 : pitchWindow.minSt
  const stMax = fixed ? hzToSemitone(fixed.fHi) + 2 : pitchWindow.maxSt
  const yOf = (st: number) => top + height - 4 - ((st - stMin) / (stMax - stMin)) * (height - 8)
  const degreeSt = (d: number) =>
    fixed ? rangeDegreeToSemitone(fixed, d) : degreeToSemitone(pitchWindow.centerSt, d)

  // 度数网格（有引导带时画五度刻度）
  if (props.targetTone) {
    ctx.font = '10px system-ui, sans-serif'
    ctx.textAlign = 'left'
    for (let d = 1; d <= 5; d += 1) {
      const st = degreeSt(d)
      if (st < stMin || st > stMax) continue
      const y = yOf(st)
      ctx.strokeStyle = COLOR.grid
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(padX, y)
      ctx.lineTo(padX + plotW, y)
      ctx.stroke()
      ctx.fillStyle = COLOR.text
      ctx.fillText(String(d), 2, y + 3)
    }
    // 目标引导带（半透明轨道 + 虚线中心线）；带宽 ±0.45 度（按当前度映射）
    const contour = toneTargetContour(props.targetTone)
    const stPerDegree = (degreeSt(5) - degreeSt(1)) / 4
    const bandHalf = 0.45 * stPerDegree
    ctx.beginPath()
    contour.forEach(([tn, degree], i) => {
      const st = degreeSt(degree)
      const x = padX + tn * plotW
      const y = yOf(st + bandHalf)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    for (let i = contour.length - 1; i >= 0; i -= 1) {
      const [tn, degree] = contour[i]!
      ctx.lineTo(padX + tn * plotW, yOf(degreeSt(degree) - bandHalf))
    }
    ctx.closePath()
    ctx.fillStyle = COLOR.band
    ctx.fill()
    ctx.setLineDash([4, 4])
    ctx.strokeStyle = COLOR.bandLine
    ctx.lineWidth = 1
    ctx.beginPath()
    contour.forEach(([tn, degree], i) => {
      const x = padX + tn * plotW
      const y = yOf(degreeSt(degree))
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()
    ctx.setLineDash([])
  } else {
    // 无调型：标出纵轴音高范围（Hz）
    ctx.font = '10px system-ui, sans-serif'
    ctx.textAlign = 'left'
    ctx.fillStyle = COLOR.text
    ctx.fillText(`${Math.round(semitoneToHz(stMax))}Hz`, padX + 2, top + 10)
    ctx.fillText(`${Math.round(semitoneToHz(stMin))}Hz`, padX + 2, top + height - 4)
  }

  // 用户实时轨迹：有声段连线，无声/清音段断开留白；
  // 弱周期延续帧（weak）用同色半透明段区分（docs §6.1）
  ctx.lineWidth = 2.2
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  type Seg = { pts: Array<[number, number]>; weak: boolean }
  const segs: Seg[] = []
  let cur: Seg | null = null
  let headX = 0
  let headY = 0
  for (const frame of frames) {
    if (frame.t < tMin - 0.05) continue
    if (frame.f0Hz === null) {
      cur = null
      continue
    }
    const x = xOf(frame.t)
    const y = yOf(hzToSemitone(frame.f0Hz))
    if (cur === null || cur.weak !== frame.weak) {
      // 分段边界共享端点：段首复用上一段末点，视觉连续
      const shared = cur?.pts.at(-1)
      cur = { pts: [], weak: frame.weak }
      if (shared) cur.pts.push(shared)
      segs.push(cur)
    }
    cur.pts.push([x, y])
    headX = x
    headY = y
  }
  for (const seg of segs) {
    if (seg.pts.length < 2) continue
    ctx.strokeStyle = COLOR.voiced
    ctx.globalAlpha = seg.weak ? 0.45 : 1
    ctx.beginPath()
    seg.pts.forEach(([x, y], i) => {
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()
  }
  ctx.globalAlpha = 1

  // 当前发声点（发光圆头）
  if (props.active && headX > 0) {
    ctx.save()
    ctx.shadowColor = COLOR.head
    ctx.shadowBlur = 8
    ctx.fillStyle = COLOR.head
    ctx.beginPath()
    ctx.arc(headX, headY, 3.5, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  }
}

function drawEnvelopeLane(
  ctx: CanvasRenderingContext2D,
  frames: Array<{ t: number; rms: number; kind: string; centroidHz: number | null; clipping: boolean }>,
  xOf: (t: number) => number,
  top: number,
  height: number,
  tMin: number,
  tMax: number,
): void {
  const mid = top + height / 2
  const maxRms = 0.35 // 展示满格音量（超过按满格画）
  const nVisible = frames.filter((f) => f.t >= tMin).length || 1
  const barW = Math.max(1, ((xOf(tMax) - xOf(tMin)) / nVisible) * 0.8)
  for (const frame of frames) {
    if (frame.t < tMin) continue
    const halfH = Math.max(1, (Math.min(frame.rms, maxRms) / maxRms) * (height / 2 - 2))
    const x = xOf(frame.t)
    ctx.fillStyle = frame.clipping
      ? COLOR.clip
      : frame.kind === 'voiced'
        ? COLOR.voiced
        : frame.kind === 'unvoicedNoise'
          ? frame.centroidHz && frame.centroidHz > 5000
            ? COLOR.noiseHigh
            : COLOR.noiseLow
          : COLOR.silence
    ctx.fillRect(x - barW / 2, mid - halfH, barW, halfH * 2)
  }
}

/* ------------------------------ 生命周期与尺寸 ------------------------------ */

let resizeObserver: ResizeObserver | null = null

function resize(): void {
  const canvas = canvasEl.value
  const wrap = wrapEl.value
  if (!canvas || !wrap) return
  dpr = window.devicePixelRatio || 1
  cssW = wrap.clientWidth
  cssH = canvas.clientHeight || 150
  canvas.width = Math.round(cssW * dpr)
  canvas.height = Math.round(cssH * dpr)
  draw()
}

watch(
  () => props.active,
  (active) => {
    stopLoop(!active)
    if (active) {
      resetSession()
      startAnalysis()
      resize()
      rafHandle = requestAnimationFrame(loop)
    } else {
      draw() // 定格整段
    }
  },
  { immediate: true },
)

// 定格回看时的游标推进 / 窗口变化触发重绘
watch([() => props.playheadSec, () => props.takeDurationSec], () => {
  if (!props.active) draw()
})

watch(canvasEl, (el) => {
  if (!el) return
  resizeObserver?.disconnect()
  resizeObserver = new ResizeObserver(() => resize())
  resizeObserver.observe(el.parentElement ?? el)
  resize()
})

onBeforeUnmount(() => {
  stopLoop()
  resizeObserver?.disconnect()
  resizeObserver = null
})

const ariaLabel = computed(() =>
  props.active ? '实时声学反馈：音高轨迹与音量' : '刚才录音的音高轨迹与音量（已定格）',
)
</script>

<template>
  <div ref="wrapEl" class="rt-wrap">
    <div class="rt-header">
      <span class="rt-pill" :class="`vol-${volumeLevel}`">● {{ volumeText }}</span>
      <span v-if="focus === 'pitch'" class="rt-pill pitch">
        当前音高 <strong>{{ currentHz !== null ? `${Math.round(currentHz)} Hz` : '—' }}</strong>
        <em v-if="toneHint">{{ toneHint }}</em>
      </span>
      <span v-if="centroidLabel" class="rt-pill centroid">{{ centroidLabel }}</span>
    </div>
    <canvas ref="canvasEl" class="rt-canvas" :aria-label="ariaLabel"></canvas>
    <p v-if="!active" class="rt-frozen-hint">已定格刚才的整段轨迹：点「试听」可见游标回放，不满意直接重录。</p>
  </div>
</template>

<style scoped lang="sass">
.rt-wrap
  width: 100%

.rt-header
  display: flex
  flex-wrap: wrap
  gap: 6px
  margin-bottom: 6px
  font-size: 12px
  color: #546e7a

.rt-pill
  display: inline-flex
  align-items: center
  gap: 4px
  padding: 2px 10px
  border-radius: 999px
  background: #eceff1
  strong
    color: #37474f
  em
    font-style: normal
    color: #00897b
  &.vol-ok
    background: #e0f2f1
    color: #00695c
  &.vol-quiet
    background: #fff8e1
    color: #8d6e00
  &.vol-loud
    background: #ffebee
    color: #c62828
  &.centroid
    background: #e1f5fe
    color: #0277bd

.rt-canvas
  display: block
  width: 100%
  height: 168px
  background: #fafafa
  border-radius: 8px

.rt-frozen-hint
  margin: 6px 0 0
  font-size: 12px
  color: #90a4ae
</style>
