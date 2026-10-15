<script setup lang="ts">
/**
 * SagittalView：声道剖面渲染器（FR-603 / #20）。
 * 静态底图（上颚、牙齿、咽腔、喉）+ 可动部件（下颌、双唇、舌尖、舌面、软腭、气流、声带），
 * 按 keyframes 器官参数驱动，帧间插值；播放 / 暂停 / 单帧；
 * 遵循 prefers-reduced-motion，默认停在首帧；帧 label 作为文字说明。
 * 纯展示：不调 api、不读 store。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePreferredReducedMotion } from '@vueuse/core'
import type { SagittalKeyframe } from '@/api'
import { buildSagittalGeometry, buildTimeline, interpolateKeyframes, sampleTimeline } from './sagittal'

const props = defineProps<{
  keyframes: SagittalKeyframe[]
  /** 逐帧文字说明（articulation.description 由父级传入） */
  description?: string
}>()

const reducedMotion = usePreferredReducedMotion()
const playing = ref(false)
const currentTimeMs = ref(0)

const timeline = computed(() => buildTimeline(props.keyframes))
const frameCount = computed(() => props.keyframes.length)

const activeFrameIndex = computed(() => {
  const sample = sampleTimeline(timeline.value.entries, currentTimeMs.value)
  if (!sample) return frameCount.value - 1
  return sample.t < 0.5 ? sample.a : Math.min(sample.b, frameCount.value - 1)
})

const effective = computed(() => {
  const sample = sampleTimeline(timeline.value.entries, currentTimeMs.value)
  if (!sample) {
    const last = props.keyframes[frameCount.value - 1]
    if (!last) return null
    return interpolateKeyframes(last, last, 0)
  }
  const a = props.keyframes[sample.a]!
  const b = props.keyframes[Math.min(sample.b, frameCount.value - 1)]!
  return interpolateKeyframes(a, b, sample.t)
})

const geometry = computed(() => (effective.value ? buildSagittalGeometry(effective.value) : null))
const frameLabel = computed(() => props.keyframes[activeFrameIndex.value]?.label ?? '')

let rafHandle: number | null = null
let lastTick = 0

function tick(now: number) {
  if (!playing.value) return
  const delta = now - lastTick
  lastTick = now
  currentTimeMs.value += delta
  if (currentTimeMs.value >= timeline.value.totalMs) {
    currentTimeMs.value = 0
  }
  rafHandle = requestAnimationFrame(tick)
}

function play() {
  if (frameCount.value < 2) return
  playing.value = true
  lastTick = performance.now()
  rafHandle = requestAnimationFrame(tick)
}
function pause() {
  playing.value = false
  if (rafHandle !== null) cancelAnimationFrame(rafHandle)
  rafHandle = null
}
function toggle() {
  if (playing.value) pause()
  else play()
}
function stepTo(index: number) {
  pause()
  const clamped = Math.max(0, Math.min(frameCount.value - 1, index))
  const entry = timeline.value.entries[clamped]
  currentTimeMs.value = entry ? entry.holdStart : 0
}

onMounted(() => {
  // prefers-reduced-motion：默认停在首帧，不自动播放
  if (!reducedMotion.value) play()
})
onBeforeUnmount(pause)
watch(reducedMotion, (value) => {
  if (value) pause()
})
</script>

<template>
  <figure class="sagittal-view" v-if="geometry">
    <svg viewBox="0 0 400 320" role="img" aria-label="声道剖面示意">
      <!-- 头部轮廓（静态底图） -->
      <path
        class="head-outline"
        d="M118,26 C60,52 40,120 52,150 C44,166 42,178 44,188 L52,208 C40,224 34,250 40,268 L48,310 L120,310 L114,268 C130,236 152,224 170,214 C150,206 140,192 136,172 C168,186 210,186 238,196 L238,180 C200,172 178,150 176,116 C176,80 150,34 118,26 Z"
      />
      <!-- 鼻腔（静态） -->
      <path class="nasal-cavity" d="M76,114 L210,126 L210,136 L78,124 Z" />
      <ellipse class="nostril" cx="72" cy="118" rx="6" ry="4" />
      <!-- 硬腭（静态） -->
      <path class="palate" d="M104,140 Q150,116 206,150" />
      <!-- 上前牙（静态） -->
      <rect class="teeth" x="94" y="142" width="9" height="18" rx="2" />
      <!-- 咽腔后壁（静态） -->
      <path class="pharynx" d="M238,132 L238,262" />
      <!-- 鼻咽通道开合（软腭） -->
      <path class="velum" :d="geometry.velumPath" :class="{ lowered: geometry.nasalPortOpen }" />
      <!-- 喉与声带 -->
      <g class="larynx">
        <path class="larynx-outline" d="M196,258 L226,258 L232,286 L190,286 Z" />
        <g v-if="geometry.voicing" class="voicing">
          <path class="voicing-wave" d="M200,266 q4,-4 8,0 t8,0" />
          <path class="voicing-wave" d="M200,274 q4,-4 8,0 t8,0" />
        </g>
      </g>
      <!-- 下颌组（旋转开口） -->
      <g class="jaw-group" :style="{ transform: `rotate(${geometry.jawRotateDeg}deg)`, transformOrigin: '232px 182px' }">
        <!-- 下前牙 -->
        <rect class="teeth lower" x="94" y="164" width="9" height="14" rx="2" />
        <!-- 下唇 -->
        <path class="lip lower-lip" :d="geometry.lowerLip" />
        <!-- 舌 -->
        <path class="tongue" :d="geometry.tonguePath" />
      </g>
      <!-- 上唇（不随下颌旋转） -->
      <path class="lip upper-lip" :d="geometry.upperLip" />
      <!-- 收紧点标注（成阻/摩擦/舌面收紧） -->
      <g v-if="geometry.constriction" class="constriction">
        <circle :cx="geometry.constriction.x" :cy="geometry.constriction.y" r="3.5" />
      </g>
      <!-- 气流路径 -->
      <g v-if="geometry.airflowPath">
        <path class="airflow" :d="geometry.airflowPath" :class="{ nasal: effective?.airflow === 'nasal' }" />
        <!-- 送气/爆破的唇外箭头 -->
        <g v-if="['burst', 'aspirated_burst', 'affricate'].includes(effective?.airflow ?? '')" class="burst">
          <path d="M60,140 l-12,-6 M60,148 l-14,0 M60,156 l-12,6" />
        </g>
      </g>
    </svg>
    <figcaption class="sagittal-caption">
      <span class="frame-label">{{ frameLabel || '声道剖面' }}</span>
      <span v-if="geometry.airflowLabel" class="airflow-label">{{ geometry.airflowLabel }}</span>
      <span v-if="geometry.voicing" class="voicing-label">声带振动</span>
      <span v-else class="voicing-label muted">声带不振动</span>
    </figcaption>
    <div class="sagittal-controls" v-if="frameCount > 0">
      <button type="button" class="sagittal-btn" :disabled="frameCount < 2" @click="toggle" aria-label="播放或暂停">
        {{ playing ? '暂停' : '播放' }}
      </button>
      <button
        type="button"
        class="sagittal-btn"
        :disabled="activeFrameIndex <= 0"
        @click="stepTo(activeFrameIndex - 1)"
        aria-label="上一帧"
      >
        上一帧
      </button>
      <span class="frame-counter">{{ activeFrameIndex + 1 }} / {{ frameCount }}</span>
      <button
        type="button"
        class="sagittal-btn"
        :disabled="activeFrameIndex >= frameCount - 1"
        @click="stepTo(activeFrameIndex + 1)"
        aria-label="下一帧"
      >
        下一帧
      </button>
    </div>
    <p v-if="description" class="sagittal-description">{{ description }}</p>
  </figure>
</template>

<style scoped lang="sass">
.sagittal-view
  max-width: 420px

svg
  width: 100%
  height: auto
  background: #fff
  border-radius: 12px
  border: 1px solid #e0e0e0

.head-outline
  fill: #fafafa
  stroke: #b0bec5
  stroke-width: 2

.nasal-cavity
  fill: none
  stroke: #b0bec5
  stroke-width: 2

.nostril
  fill: #eceff1
  stroke: #b0bec5

.palate
  fill: none
  stroke: #78909c
  stroke-width: 3

.pharynx
  stroke: #90a4ae
  stroke-width: 3

.teeth
  fill: #fffde7
  stroke: #cfd8dc
  stroke-width: 1

.velum
  fill: none
  stroke: #8d6e63
  stroke-width: 5
  stroke-linecap: round
  &.lowered
    stroke: #a1887f

.larynx-outline
  fill: #efebe9
  stroke: #a1887f
  stroke-width: 1.5

.voicing-wave
  fill: none
  stroke: #e91e63
  stroke-width: 2
  animation: voicing-wave 0.6s ease-in-out infinite alternate

@keyframes voicing-wave
  from
    transform: translateX(0)
  to
    transform: translateX(3px)

.tongue
  fill: #ffcdd2
  stroke: #e57373
  stroke-width: 2

.lip
  fill: #f8bbd0
  stroke: #ec407a
  stroke-width: 1.5

.constriction circle
  fill: #d84315

.airflow
  fill: none
  stroke: #29b6f6
  stroke-width: 3
  stroke-dasharray: 8 6
  animation: airflow-dash 0.9s linear infinite

@keyframes airflow-dash
  from
    stroke-dashoffset: 14
  to
    stroke-dashoffset: 0

.burst path
  stroke: #29b6f6
  stroke-width: 2.5
  fill: none
  animation: airflow-dash 0.5s linear infinite

.sagittal-caption
  display: flex
  gap: 12px
  flex-wrap: wrap
  font-size: 13px
  color: #546e7a
  margin-top: 6px

.frame-label
  color: #263238
  font-weight: 600

.sagittal-controls
  display: flex
  align-items: center
  gap: 8px
  margin-top: 6px

.sagittal-btn
  min-height: 32px
  min-width: 64px
  padding: 4px 10px
  border: 1px solid #cfd8dc
  border-radius: 6px
  background: #fff
  cursor: pointer
  font-size: 13px
  &:disabled
    opacity: 0.45
    cursor: default

.frame-counter
  font-size: 12px
  color: #78909c
  min-width: 44px
  text-align: center

.sagittal-description
  font-size: 13px
  color: #455a64
  margin: 6px 0 0
</style>
