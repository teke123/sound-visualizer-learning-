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
      text-color="teal-9"
      class="compare-demo-btn"
      @click="playDemo"
    >
      {{ player.isCurrent(listenKey) ? '⏸ 暂停示范' : '▶ 播放示范' }}
    </QBtn>
  </div>
</template>

<style scoped lang="sass">
.compare-side
  border: 1px solid #eceff1
  border-radius: 10px
  padding: 14px
  display: flex
  flex-direction: column
  gap: 8px
  h3
    margin: 0
    font-size: 16px

.compare-labels
  display: flex
  flex-wrap: wrap
  gap: 6px

.compare-label
  color: #00695c
  background: #e0f2f1
  border: 1px solid transparent
  &.diff
    color: #bf360c
    background: #fff3e0
    border-color: #ffb74d
    font-weight: 600

.diff-mark
  font-size: 11px

.compare-figure
  max-height: 240px
  overflow: auto
  border-radius: 8px

.compare-nofigure
  color: #b0bec5
  font-size: 13px
  margin: 0

.compare-demo-btn
  min-height: 44px
  width: fit-content
  background: #e0f2f1 !important /* Quasar outline 底色 transparent !important，覆盖需同为 important */
</style>
