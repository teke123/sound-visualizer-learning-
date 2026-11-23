<script setup lang="ts">
/**
 * CompareSide：比较面板单侧（示范播放 + 构形主图 + 语音学属性标签）。
 * 构形由静态 img 升级为 ArticulationFigure（媒体 / 声道剖面 / 3D 多视图，§2.7），
 * 容器限高 240px；语音学标签来自 matchLevel，差异项（仅本侧有、对侧没有）
 * 由 ComparePanel 计算后经 diff-labels 下发高亮（§2.7）。
 */
import { computed } from 'vue'
import { QBadge, QBtn } from 'quasar'
import type { LevelDetail } from '@/api'
import { mediaUrl } from '@/api'
import { usePlayerStore } from '@/stores/player'
import ArticulationFigure from '@/renderers/ArticulationFigure.vue'
import { matchLevel } from '@/phonology/mandarin'

const props = defineProps<{
  level: LevelDetail
  /** 与对侧不同的语音学标签（ComparePanel 计算）：高亮提示差异维度 */
  diffLabels?: string[]
}>()

const player = usePlayerStore()
const demos = computed(() => props.level.demos ?? [])
const demo = computed(() => demos.value.find((item) => item.speed === 'normal') ?? demos.value[0])
const listenKey = computed(() => `demo:${props.level.id}`)

const phonologyLabels = computed(() =>
  matchLevel({
    layer: props.level.layer,
    targetSound: props.level.targetSound,
    pinyin: props.level.pinyin,
    phonology: props.level.phonology,
  }).labels,
)

function isDiff(label: string): boolean {
  return (props.diffLabels ?? []).includes(label)
}

function playDemo() {
  if (!demo.value) return
  void player.play({ key: listenKey.value, url: mediaUrl(demo.value.mediaId), label: props.level.title })
}
</script>

<template>
  <div class="compare-side">
    <h3>{{ level.title }}（{{ level.pinyin }}）</h3>
    <div v-if="phonologyLabels.length > 0" class="compare-labels" :title="phonologyLabels.join(' | ')">
      <QBadge v-for="label in phonologyLabels" :key="label" class="compare-label" :class="{ diff: isDiff(label) }">
        {{ label }}<span v-if="isDiff(label)" class="diff-mark"> ≠</span>
      </QBadge>
    </div>
    <div v-if="level.articulation" class="compare-figure">
      <ArticulationFigure :articulation="level.articulation" :media-resolver="mediaUrl" />
    </div>
    <p v-else class="compare-nofigure">（无构形图）</p>
    <QBtn
      v-if="demo"
      outline
      no-caps
      color="primary"
      text-color="primary"
      class="compare-demo-btn"
      @click="playDemo"
    >
      {{ player.isCurrent(listenKey) ? '⏸ 暂停示范' : '▶ 播放示范' }}
    </QBtn>
  </div>
</template>

<style scoped lang="sass">
.compare-side
  border: 1px solid var(--vs-line)
  border-radius: 8px
  background: var(--vs-card)
  box-shadow: 0 1px 2px rgba(var(--vs-shadow-rgb), 0.05), 0 1px 3px rgba(var(--vs-shadow-rgb), 0.04)
  padding: 14px
  display: flex
  flex-direction: column
  gap: 8px
  min-width: 0
  h3
    margin: 0
    font-size: 16px

.compare-labels
  display: flex
  flex-wrap: wrap
  gap: 6px

.compare-label
  color: var(--vs-coffee)
  background: var(--vs-soft)
  border: 1px solid transparent
  max-width: 100%
  white-space: normal
  &.diff
    color: var(--vs-brand-d)
    background: var(--vs-amber-soft)
    border-color: var(--vs-sand)
    font-weight: 600

.diff-mark
  font-size: 11px

.compare-figure
  max-height: 240px
  overflow: auto
  border-radius: 8px

.compare-nofigure
  color: var(--vs-mute-2)
  font-size: 13px
  margin: 0

.compare-demo-btn
  min-height: 44px
  width: fit-content
</style>
