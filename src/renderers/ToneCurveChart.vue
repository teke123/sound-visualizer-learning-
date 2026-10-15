<script setup lang="ts">
/**
 * ToneCurveChart：结果快照音高曲线（T 值、按音节分段；FR-1005 / FD-16）。
 * 「我的曲线」实线、「标准曲线」虚线 + 图例（不只靠颜色区分，NFR-07）；
 * 声学数据由后端计算，前端只渲染。P09 / P10 共用。
 * 本组件由页面异步加载，echarts 不进首屏包（§9）。
 */
import { computed, provide, ref } from 'vue'
import { use as echartsUse } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { ResultCurve } from '@/api'

echartsUse([LineChart, GridComponent, LegendComponent, TooltipComponent, MarkLineComponent, CanvasRenderer])

const props = defineProps<{
  curve: ResultCurve
  /** 图表高度（px） */
  height?: number
}>()

provide('echartsTheme', undefined)

const chartHeight = computed(() => `${props.height ?? 300}px`)

const unavailable = computed(() => props.curve.status !== 'ok')

/** 分段拼接：段间用 null 断开；记录音节分隔线 */
const option = computed(() => {
  if (unavailable.value) return undefined
  const userPoints: Array<[number, number] | null> = []
  const referencePoints: Array<[number, number] | null> = []
  const markLines: Array<{ xAxis: number; label: { formatter: string } }> = []
  let cursor = 0
  for (const segment of props.curve.segments ?? []) {
    if (cursor > 0) {
      userPoints.push(null)
      referencePoints.push(null)
    }
    const span = Math.max(
      segment.user?.at(-1)?.t ?? 0,
      segment.reference?.at(-1)?.t ?? 0,
      0.2,
    )
    for (const point of segment.user ?? []) userPoints.push([cursor + point.t, point.v])
    for (const point of segment.reference ?? []) referencePoints.push([cursor + point.t, point.v])
    cursor += span
    markLines.push({ xAxis: cursor, label: { formatter: segment.syllable ?? ''} })
  }
  return {
    animationDuration: 200,
    grid: { left: 44, right: 16, top: 40, bottom: 32 },
    legend: {
      data: ['我的曲线', '标准曲线'],
      top: 4,
      textStyle: { fontSize: 12 },
    },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: unknown) => `T 值 ${Number(value).toFixed(2)}`,
    },
    xAxis: {
      type: 'value',
      name: '时间（秒）',
      nameLocation: 'middle',
      nameGap: 24,
      min: 0,
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'T 值',
      min: 0,
      max: 5,
      interval: 1,
    },
    series: [
      {
        name: '我的曲线',
        type: 'line',
        data: userPoints,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 3, type: 'solid', color: '#0288d1' },
        itemStyle: { color: '#0288d1' },
        connectNulls: false,
      },
      {
        name: '标准曲线',
        type: 'line',
        data: referencePoints,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 2.5, type: 'dashed', color: '#6a4c93' },
        itemStyle: { color: '#6a4c93' },
        connectNulls: false,
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

const fallback = ref<HTMLElement | null>(null)
</script>

<template>
  <div class="tone-curve-chart">
    <div v-if="unavailable" class="curve-unavailable">
      <p>本次没有可用的音高曲线。</p>
      <p class="reason">{{ curve.note ?? '这条录音未能提取有效音高，不做伪造展示。' }}</p>
    </div>
    <VChart v-else :option="option" :style="{ height: chartHeight, width: '100%' }" autoresize />
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
</style>
