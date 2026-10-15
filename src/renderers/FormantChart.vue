<script setup lang="ts">
/**
 * FormantChart：共振峰对比散点图（仅单韵母关，FR-1005）。
 * 按本人元音空间归一化；不可用时显示原因，不伪造。
 * 轴：F1（横向，左右无关紧要的示意）/ F2；参考区域用点簇 + 网格示意。
 */
import { computed } from 'vue'
import { use as echartsUse } from 'echarts/core'
import { ScatterChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, MarkAreaComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { ResultFormants } from '@/api'

echartsUse([ScatterChart, GridComponent, LegendComponent, TooltipComponent, MarkAreaComponent, CanvasRenderer])

const props = defineProps<{
  formants: ResultFormants
  height?: number
}>()

const unavailable = computed(() => props.formants.status !== 'ok' || !props.formants.user)

const option = computed(() => {
  if (unavailable.value) return undefined
  const regionPoints = (props.formants.referenceRegion?.points ?? []).map((point) => [point.f1, point.f2])
  const userPoint = [[props.formants.user!.f1, props.formants.user!.f2]]
  const xs = [...regionPoints, ...userPoint].map((p) => p[0]!)
  const ys = [...regionPoints, ...userPoint].map((p) => p[1]!)
  const pad = 60
  return {
    animationDuration: 200,
    grid: { left: 52, right: 20, top: 40, bottom: 40 },
    legend: { data: ['我的位置', '参考区域'], top: 4, textStyle: { fontSize: 12 } },
    tooltip: {
      trigger: 'item',
      formatter: (params: { seriesName: string; data: [number, number] }) =>
        `${params.seriesName}<br/>F1: ${params.data[0].toFixed(0)} Hz · F2: ${params.data[1].toFixed(0)} Hz`,
    },
    xAxis: {
      name: 'F1（归一化）',
      nameLocation: 'middle',
      nameGap: 28,
      min: Math.min(...xs) - pad,
      max: Math.max(...xs) + pad,
    },
    yAxis: {
      name: 'F2（归一化）',
      min: Math.min(...ys) - pad,
      max: Math.max(...ys) + pad,
    },
    series: [
      {
        name: '参考区域',
        type: 'scatter',
        data: regionPoints,
        symbolSize: 10,
        itemStyle: { color: 'rgba(106, 76, 147, 0.35)', borderColor: '#6a4c93', borderWidth: 1 },
      },
      {
        name: '我的位置',
        type: 'scatter',
        data: userPoint,
        symbolSize: 18,
        itemStyle: { color: '#0288d1', borderColor: '#01579b', borderWidth: 2 },
        z: 10,
      },
    ],
  }
})
</script>

<template>
  <div class="formant-chart">
    <div v-if="unavailable" class="formant-unavailable">
      <p>本次没有可用的共振峰对比。</p>
      <p class="reason">
        {{
          formants.notAvailableReason ??
          '共振峰对比需要先完成元音空间标定；没有有效数据时不做伪造展示。'
        }}
      </p>
    </div>
    <VChart v-else :option="option" :style="{ height: `${height ?? 300}px`, width: '100%' }" autoresize />
  </div>
</template>

<style scoped lang="sass">
.formant-chart
  width: 100%

.formant-unavailable
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
