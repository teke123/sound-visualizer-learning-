<script setup lang="ts">
/**
 * FormantChart：共振峰对比散点图（仅单韵母关，FR-1005）。
 * 按本人元音空间归一化；不可用时显示原因，不伪造。
 * 参考区域 = 归一化平面上的圆（center + radius）；我的位置为单点。
 */
import { computed } from 'vue'
import { use as echartsUse } from 'echarts/core'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { ResultFormants } from '@/api'

echartsUse([ScatterChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  formants: ResultFormants
  height?: number
}>()

const unavailable = computed(() => props.formants.status !== 'ok' || !props.formants.user)

/** 参考区域圆周采样（虚线圆） */
function regionCircle(): Array<[number, number]> {
  const region = props.formants.referenceRegion
  const [cx, cy] = region?.center ?? []
  if (cx == null || cy == null || region?.radius == null) return []
  const radius = region.radius
  return Array.from({ length: 49 }, (_, i) => {
    const angle = (i / 48) * Math.PI * 2
    return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)] as [number, number]
  })
}

const option = computed(() => {
  if (unavailable.value) return undefined
  const user = props.formants.user!
  const f1 = user.f1 ?? 0
  const f2 = user.f2 ?? 0
  const userPoint: Array<[number, number]> = [[f1, f2]]
  const circle = regionCircle()
  const xs = [...circle.map((p) => p[0]!), f1]
  const ys = [...circle.map((p) => p[1]!), f2]
  const pad = 0.5
  return {
    animationDuration: 200,
    grid: { left: 52, right: 20, top: 40, bottom: 40 },
    legend: { data: ['我的位置', '参考区域'], top: 4, textStyle: { fontSize: 12 } },
    tooltip: {
      trigger: 'item',
      formatter: (params: { seriesName: string; data: [number, number] }) =>
        `${params.seriesName}<br/>轴1: ${params.data[0].toFixed(2)} · 轴2: ${params.data[1].toFixed(2)}`,
    },
    xAxis: {
      name: '归一化轴 1',
      nameLocation: 'middle',
      nameGap: 28,
      min: Math.min(...xs) - pad,
      max: Math.max(...xs) + pad,
    },
    yAxis: {
      name: '归一化轴 2',
      min: Math.min(...ys) - pad,
      max: Math.max(...ys) + pad,
    },
    series: [
      ...(circle.length > 0
        ? [
            {
              name: '参考区域',
              type: 'line' as const,
              data: circle,
              showSymbol: false,
              smooth: true,
              lineStyle: { width: 2, type: 'dashed' as const, color: '#6a4c93' },
              itemStyle: { color: '#6a4c93' },
              silent: true,
            },
          ]
        : []),
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
        {{ formants.note ?? '共振峰对比需要先完成元音空间标定；没有有效数据时不做伪造展示。' }}
      </p>
    </div>
    <VChart v-else :option="option" :style="{ height: `${height ?? 300}px`, width: '100%' }" autoresize />
    <p v-if="!unavailable && formants.referenceRegion?.vowel" class="formant-region-note">
      虚线圆为参考发音人「{{ formants.referenceRegion.vowel }}」的元音区域（按元音空间归一化）。
    </p>
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

.formant-region-note
  font-size: 12px
  color: #90a4ae
  margin: 6px 0 0
</style>
