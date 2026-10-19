<script setup lang="ts">
/**
 * ToneCurveChart：结果音高曲线（degree 1-5 五度坐标 / 相对半音 / Hz 三视图，
 * 按音节分段拼接；docs/f0展示修改测试版1.md §6.2）。
 * - 「我的曲线」与「标准曲线」同屏叠加：原生网格帧、connectNulls:false，
 *   静音/清音缺口自然断开；可靠段实线、低置信度段同色点线（共享图例）。
 * - 历史 0-5 T 值数据按 D = 1 + 0.8·T 版本转换显示（docs §4.3）。
 * - 哼鸣 A/B 试听：听标准音高 / 听我的音高 / 按我的音域听标准，播放游标同步。
 * 本组件由页面异步加载，echarts 不进首屏包（§9）。
 */
import { computed, provide, ref } from 'vue'
import { use as echartsUse } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { ResultCurve, SyllableCurveSide, CurvePoint } from '@/api'
import { usePlayerStore } from '@/stores/player'
import { audioF0HumUrl, mediaF0HumUrl } from '@/api'

echartsUse([LineChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer])

type ViewMode = 'degree' | 'st' | 'hz'
type Pt = { x: number; y: number | null; conf: number; src: string | null }

const SOLID_CONF = 0.5

const props = defineProps<{
  curve: ResultCurve
  /** 图表高度（px） */
  height?: number
  /** 用户录音 id（提供时显示「听我的音高」哼鸣） */
  audioId?: string
}>()

provide('echartsTheme', undefined)

const player = usePlayerStore()
const view = ref<ViewMode>('degree')

const chartHeight = computed(() => `${props.height ?? 320}px`)
const unavailable = computed(() => props.curve.status !== 'ok')

/** 历史数据（user/reference 为 {t,v} 点列）按 T→degree 转换 */
function isLegacySide(side: unknown): side is CurvePoint[] {
  return Array.isArray(side)
}

function sideRange(side: 'user' | 'reference'): { fLo: number; fHi: number } | null {
  const c = props.curve
  const r = side === 'user' ? c.userRange : c.referenceRange
  return r && typeof r.fLo === 'number' && typeof r.fHi === 'number' ? { fLo: r.fLo, fHi: r.fHi } : null
}

function relSt(hz: number, range: { fLo: number; fHi: number }): number {
  return 12 * Math.log2(hz / Math.sqrt(range.fLo * range.fHi))
}

/** 单侧曲线 → 绘图点列（x = 音节序号 + 音节内相对时间 u） */
function sidePoints(segIndex: number, side: unknown, range: { fLo: number; fHi: number } | null): Pt[] {
  if (isLegacySide(side)) {
    // 历史 0-5 T 值：x 已是归一化 t，v → degree
    return side.map((p) => ({
      x: segIndex + p.t,
      y: 1 + 0.8 * p.v,
      conf: 1,
      src: 'measured',
    }))
  }
  const s = side as SyllableCurveSide | null
  const frames = s?.frames
  if (!frames || !s || s.analysisStart == null || s.analysisEnd == null) return []
  const dur = Math.max(s.analysisEnd - s.analysisStart, 1e-6)
  return frames.map((fr) => {
    const u = (fr.t - s.analysisStart!) / dur
    let y: number | null = null
    if (fr.hz != null) {
      if (view.value === 'degree') y = fr.degree ?? null
      else if (view.value === 'st') y = range ? relSt(fr.hz, range) : null
      else y = fr.hz
    }
    return { x: segIndex + Math.min(Math.max(u, 0), 1), y, conf: fr.confidence ?? 0, src: fr.source ?? null }
  })
}

interface SegMeta {
  syllable: string
  toneValue?: number | null
  chao?: string | null
  userDur?: number | null
  refDur?: number | null
  hasNewData: boolean
}

const segments = computed(() => {
  const out: { meta: SegMeta; user: Pt[]; ref: Pt[] }[] = []
  let idx = 0
  const userRange = sideRange('user')
  const refRange = sideRange('reference')
  for (const seg of props.curve.segments ?? []) {
    const user = sidePoints(idx, seg.user, userRange)
    const ref = sidePoints(idx, seg.reference, refRange ?? userRange)
    const userSide = isLegacySide(seg.user) ? null : (seg.user as SyllableCurveSide | null)
    const refSide = isLegacySide(seg.reference) ? null : (seg.reference as SyllableCurveSide | null)
    out.push({
      meta: {
        syllable: seg.syllable ?? '',
        toneValue: seg.toneValue,
        chao: userSide?.chao ?? undefined,
        userDur: userSide?.analysisDuration ?? userSide?.duration ?? null,
        refDur: refSide?.analysisDuration ?? refSide?.duration ?? null,
        hasNewData: !!(userSide?.frames?.length),
      },
      user,
      ref,
    })
    idx += 1
  }
  return out
})

/** 按置信度拆分实线/点线数据（相邻两端较小值 < 0.5 → 点线；分段边界共享端点） */
function splitByConfidence(pts: Pt[]): { solid: Array<[number, number] | null>; dotted: Array<[number, number] | null> } {
  const solid: Array<[number, number] | null> = []
  const dotted: Array<[number, number] | null> = []
  let prev: Pt | null = null
  let prevSide: 'solid' | 'dotted' | null = null
  for (const p of pts) {
    if (p.y == null) {
      solid.push(null)
      dotted.push(null)
      prev = null
      prevSide = null
      continue
    }
    if (prev && prevSide && prev.y != null) {
      const weak = Math.min(prev.conf, p.conf) < SOLID_CONF
      const target = weak ? dotted : solid
      const name = weak ? 'dotted' : 'solid'
      if (prevSide !== name) target.push([prev.x, prev.y!])
      target.push([p.x, p.y])
      prevSide = name
    } else {
      solid.push([p.x, p.y])
      prevSide = 'solid'
    }
    prev = p
  }
  return { solid, dotted }
}

const showUser = ref(true)
const showRef = ref(true)

const allY = computed(() => {
  const ys: number[] = []
  for (const s of segments.value) {
    for (const p of [...s.user, ...s.ref]) if (p.y != null) ys.push(p.y)
  }
  return ys
})

const yMin = computed(() => {
  const ys = allY.value
  if (!ys.length) return view.value === 'degree' ? 0.5 : 0
  if (view.value === 'degree') return Math.min(0.5, Math.floor(Math.min(...ys) * 2) / 2)
  return Math.floor(Math.min(...ys))
})
const yMax = computed(() => {
  const ys = allY.value
  if (!ys.length) return view.value === 'degree' ? 5.5 : 1
  if (view.value === 'degree') return Math.max(5.5, Math.ceil(Math.max(...ys) * 2) / 2)
  return Math.ceil(Math.max(...ys))
})

const DEGREE_LABELS = ['1（低）', '2（半低）', '3（中）', '4（半高）', '5（高）']

const option = computed(() => {
  if (unavailable.value) return undefined
  const nSeg = segments.value.length
  const userSolid: Array<[number, number] | null> = []
  const userDotted: Array<[number, number] | null> = []
  const refSolid: Array<[number, number] | null> = []
  const refDotted: Array<[number, number] | null> = []
  const markLines: Array<{ xAxis: number; label: { formatter: string } }> = []
  segments.value.forEach((s, i) => {
    if (i > 0) {
      userSolid.push(null); userDotted.push(null); refSolid.push(null); refDotted.push(null)
    }
    const u = splitByConfidence(s.user)
    const r = splitByConfidence(s.ref)
    userSolid.push(...u.solid); userDotted.push(...u.dotted)
    refSolid.push(...r.solid); refDotted.push(...r.dotted)
    markLines.push({ xAxis: i, label: { formatter: s.meta.syllable } })
  })
  markLines.push({ xAxis: nSeg, label: { formatter: '' } })

  const lineSeries = (
    name: string, data: Array<[number, number] | null>, color: string,
    dotted: boolean, dashedBase: boolean,
  ) => ({
    name,
    type: 'line' as const,
    data,
    showSymbol: false,
    smooth: false,
    connectNulls: false,
    lineStyle: {
      width: dashedBase ? 2.5 : 3,
      type: dotted ? 'dotted' : dashedBase ? 'dashed' : 'solid',
      color,
    },
    itemStyle: { color },
    emphasis: { disabled: true },
    silent: true,
  })

  const cursorX = humCursorX.value
  if (cursorX != null) {
    markLines.push({ xAxis: cursorX, label: { formatter: '' } })
  }

  return {
    animationDuration: 200,
    grid: { left: 52, right: 16, top: 34, bottom: 40 },
    tooltip: {
      trigger: 'axis' as const,
      valueFormatter: (value: unknown) =>
        view.value === 'hz' ? `${Number(value).toFixed(0)} Hz`
          : view.value === 'st' ? `${Number(value).toFixed(1)} ST`
            : `五度 ${Number(value).toFixed(2)}`,
    },
    xAxis: {
      type: 'value' as const,
      name: '音节内相对时间',
      nameLocation: 'middle' as const,
      nameGap: 26,
      min: 0,
      max: Math.max(nSeg, 1),
      interval: 1,
      axisLabel: { show: false },
      splitLine: { show: false },
    },
    yAxis: (() => {
      if (view.value === 'hz') {
        return { type: 'log' as const, name: 'Hz（对数）', min: 50, max: 800, splitLine: { show: true, lineStyle: { color: '#eceff1' } } }
      }
      if (view.value === 'st') {
        return {
          type: 'value' as const, name: '相对半音（音域中心 = 0）',
          min: yMin.value, max: yMax.value,
          splitLine: { show: true, lineStyle: { color: '#eceff1' } },
        }
      }
      return {
        type: 'value' as const, name: '五度值',
        min: yMin.value, max: yMax.value, interval: 1,
        axisLabel: {
          formatter: (v: number) => (DEGREE_LABELS[v - 1] ?? String(v)),
        },
      }
    })(),
    series: [
      ...(showUser.value ? [lineSeries('我的曲线', userSolid, '#0288d1', false, false)] : []),
      ...(showUser.value ? [lineSeries('我的曲线', userDotted, '#0288d1', true, false)] : []),
      ...(showRef.value ? [lineSeries('标准曲线', refSolid, '#6a4c93', false, true)] : []),
      ...(showRef.value ? [lineSeries('标准曲线', refDotted, '#6a4c93', true, true)] : []),
      {
        name: '分隔',
        type: 'line' as const,
        data: [],
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          lineStyle: { color: '#b0bec5', type: 'solid', width: 1 },
          label: { position: 'insideEndTop', fontSize: 11, color: '#546e7a' },
          data: markLines,
        },
      },
    ],
  }
})

/** 哼鸣试听（docs §5.2）：三个按钮 + 播放游标同步 */
const sampleMediaId = computed(() => props.curve.sampleMediaId ?? null)
const userRange = computed(() => sideRange('user'))
const humReady = computed(
  () => !!(sampleMediaId.value || props.audioId),
)

function playHum(kind: 'ref' | 'user' | 'ref-remap') {
  if (kind === 'user' && props.audioId) {
    void player.play({ key: 'hum:user', url: audioF0HumUrl(props.audioId), label: '我的音高哼鸣' })
  } else if (kind === 'ref' && sampleMediaId.value) {
    void player.play({ key: 'hum:ref', url: mediaF0HumUrl(sampleMediaId.value), label: '标准音高哼鸣' })
  } else if (kind === 'ref-remap' && sampleMediaId.value && userRange.value) {
    void player.play({
      key: 'hum:ref-remap',
      url: mediaF0HumUrl(sampleMediaId.value, userRange.value),
      label: '按我的音域听标准',
    })
  }
}

const HUM_KEYS = new Set(['hum:user', 'hum:ref', 'hum:ref-remap'])

/** 播放哼鸣时：currentTime（秒）→ 图表游标 x（音节序号 + u） */
const humCursorX = computed<number | null>(() => {
  const key = player.current?.key ?? ''
  if (!HUM_KEYS.has(key) || player.state !== 'playing') return null
  const t = player.currentTime
  const isUser = key === 'hum:user'
  for (let i = 0; i < segments.value.length; i += 1) {
    const seg = props.curve.segments?.[i]
    if (!seg) continue
    const side = (isUser ? seg.user : seg.reference) as SyllableCurveSide | null
    if (!side || Array.isArray(side)) continue
    const { analysisStart, analysisEnd } = side
    if (analysisStart == null || analysisEnd == null) continue
    if (t >= analysisStart - 0.02 && t <= analysisEnd + 0.02) {
      const u = (t - analysisStart) / Math.max(analysisEnd - analysisStart, 1e-6)
      return i + Math.min(Math.max(u, 0), 1)
    }
  }
  return null
})

/** 音节实际时长对比文本（图表下方） */
const durationNotes = computed(() =>
  segments.value
    .filter((s) => s.meta.userDur != null || s.meta.refDur != null)
    .map((s) => {
      const u = s.meta.userDur
      const r = s.meta.refDur
      const ratio = u != null && r ? `（我的/标准 = ${(u / r).toFixed(2)}）` : ''
      return `「${s.meta.syllable || '·'}」我 ${u != null ? `${u.toFixed(2)} 秒` : '—'}，`
        + `标准 ${r != null ? `${r.toFixed(2)} 秒` : '—'}${ratio}`
        + (s.meta.chao ? `，近似调值 ${s.meta.chao}` : '')
    }),
)
</script>

<template>
  <div class="tone-curve-chart">
    <div v-if="unavailable" class="curve-unavailable">
      <p>本次没有可用的音高曲线。</p>
      <p class="reason">{{ curve.note ?? '这条录音未能提取有效音高，不做伪造展示。' }}</p>
    </div>
    <template v-else>
      <div class="chart-toolbar">
        <div class="view-switch" role="tablist" aria-label="纵轴坐标切换">
          <button
            v-for="m in (['degree', 'st', 'hz'] as const)"
            :key="m"
            type="button"
            class="view-btn"
            :class="{ active: view === m }"
            @click="view = m"
          >
            {{ m === 'degree' ? '五度值 (1–5)' : m === 'st' ? '相对半音 (ST)' : '频率 (Hz)' }}
          </button>
        </div>
        <div class="legend-chips">
          <button type="button" class="chip user" :class="{ off: !showUser }" @click="showUser = !showUser">
            <span class="chip-line solid" /> 我的曲线
          </button>
          <button type="button" class="chip ref" :class="{ off: !showRef }" @click="showRef = !showRef">
            <span class="chip-line dashed" /> 标准曲线
          </button>
        </div>
      </div>

      <VChart :option="option" :style="{ height: chartHeight, width: '100%' }" autoresize />

      <div v-if="durationNotes.length" class="duration-notes">
        <p v-for="(note, i) in durationNotes" :key="i">{{ note }}</p>
      </div>

      <div v-if="humReady" class="hum-row">
        <button
          v-if="sampleMediaId" type="button" class="hum-btn"
          @click="playHum('ref')"
        >
          {{ player.isCurrent('hum:ref') ? '⏸ 停止' : '🎵 听标准音高' }}
        </button>
        <button
          v-if="audioId" type="button" class="hum-btn"
          @click="playHum('user')"
        >
          {{ player.isCurrent('hum:user') ? '⏸ 停止' : '🎵 听我的音高' }}
        </button>
        <button
          v-if="sampleMediaId && userRange" type="button" class="hum-btn"
          @click="playHum('ref-remap')"
        >
          {{ player.isCurrent('hum:ref-remap') ? '⏸ 停止' : '🎵 按我的音域听标准' }}
        </button>
        <span class="hum-hint">哼鸣只保留音高旋律，用于 A/B 对比起伏与拐点</span>
      </div>
    </template>
  </div>
</template>

<style scoped lang="sass">
.tone-curve-chart
  width: 100%

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

.chart-toolbar
  display: flex
  align-items: center
  justify-content: space-between
  gap: 10px
  flex-wrap: wrap
  margin-bottom: 6px

.view-switch
  display: inline-flex
  border: 1px solid #cfd8dc
  border-radius: 999px
  overflow: hidden

.view-btn
  border: none
  background: #fff
  color: #546e7a
  font-size: 12px
  padding: 6px 12px
  cursor: pointer
  &.active
    background: #00897b
    color: #fff
  & + &
    border-left: 1px solid #cfd8dc

.legend-chips
  display: inline-flex
  gap: 8px

.chip
  display: inline-flex
  align-items: center
  gap: 6px
  border: 1px solid #eceff1
  background: #fff
  border-radius: 999px
  padding: 4px 10px
  font-size: 12px
  color: #37474f
  cursor: pointer
  &.off
    opacity: 0.4
  .chip-line
    display: inline-block
    width: 18px
    height: 0
    border-top: 2.5px solid #0288d1
    &.dashed
      border-top: 2.5px dashed #6a4c93

.duration-notes
  font-size: 12px
  color: #78909c
  p
    margin: 2px 0

.hum-row
  display: flex
  align-items: center
  gap: 8px
  flex-wrap: wrap
  margin-top: 8px

.hum-btn
  min-height: 36px
  padding: 4px 14px
  border-radius: 999px
  border: 1px solid #4db6ac
  background: #e0f2f1
  color: #00695c
  font-size: 13px
  cursor: pointer

.hum-hint
  font-size: 12px
  color: #90a4ae
</style>
