<script setup lang="ts">
/**
 * LayerMap：P03 三层闯关定位图（FR-401/402/404，FD-13）。
 * 固定三层：单韵母 → 声母 → 拼读；已开放可点进；骨架仅身份 + 「未开放」；
 * 不承载专业说明与 IPA；完成标记来自进度门面。
 */
import { computed } from 'vue'
import type { LevelSkeleton, LevelSummary } from '@/api'

const props = withDefaults(
  defineProps<{
    levels: LevelSummary[]
    skeletons?: LevelSkeleton[]
    completedIds?: ReadonlySet<string>
  }>(),
  { skeletons: () => [], completedIds: () => new Set<string>() },
)

interface MapNode {
  id: string
  label: string
  order: number
  published: boolean
  completed: boolean
}

const LAYERS: Array<{ key: LevelSummary['layer']; name: string; hint: string }> = [
  { key: 'vowel', name: '第一层 · 单韵母', hint: '把六个单韵母的口型摆稳' },
  { key: 'initial', name: '第二层 · 声母', hint: '逐个声母过关，重点区分易混音' },
  { key: 'syllable', name: '第三层 · 拼读', hint: '把声母和韵母拼起来' },
]

const layers = computed(() =>
  LAYERS.map((layer) => {
    const published: MapNode[] = [...props.levels]
      .filter((level) => level.layer === layer.key)
      .sort((a, b) => a.order - b.order)
      .map((level) => ({
        id: level.id,
        label: level.targetSound,
        order: level.order,
        published: true,
        completed: props.completedIds.has(level.id),
      }))
    const skeleton: MapNode[] = props.skeletons
      .filter((item) => item.layer === layer.key)
      .sort((a, b) => a.order - b.order)
      .map((item) => ({
        id: item.id,
        label: item.targetSound,
        order: item.order,
        published: false,
        completed: false,
      }))
    return { ...layer, nodes: [...published, ...skeleton].sort((a, b) => a.order - b.order) }
  }),
)
</script>

<template>
  <div class="layer-map">
    <section v-for="layer in layers" :key="layer.key" class="map-layer" :aria-label="layer.name">
      <header class="layer-head">
        <h2>{{ layer.name }}</h2>
        <p>{{ layer.hint }}</p>
      </header>
      <div class="layer-nodes">
        <template v-for="node in layer.nodes" :key="node.id">
          <RouterLink
            v-if="node.published"
            :to="`/learn/${node.id}`"
            class="map-node published"
            :class="{ completed: node.completed }"
          >
            <span class="node-sound">{{ node.label }}</span>
            <span v-if="node.completed" class="node-done" aria-label="已完成">✓</span>
          </RouterLink>
          <span v-else class="map-node skeleton" aria-label="未开放">
            <span class="node-sound">{{ node.label }}</span>
            <span class="node-id">未开放</span>
          </span>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped lang="sass">
.layer-map
  display: flex
  flex-direction: column
  gap: 24px

.map-layer
  background: #fff
  border: 1px solid #eceff1
  border-radius: 12px
  padding: 16px

.layer-head
  h2
    margin: 0
    font-size: 17px
  p
    margin: 4px 0 12px
    font-size: 13px
    color: #90a4ae

.layer-nodes
  display: flex
  flex-wrap: wrap
  gap: 10px

.map-node
  width: 72px
  height: 72px
  border-radius: 12px
  display: flex
  flex-direction: column
  align-items: center
  justify-content: center
  gap: 2px
  position: relative
  text-decoration: none

  &.published
    background: #e0f2f1
    border: 2px solid #26a69a
    color: #004d40
    &:hover
      background: #b2dfdb
    &.completed
      background: #c8e6c9
      border-color: #66bb6a

  &.skeleton
    background: #fafafa
    border: 2px dashed #cfd8dc
    color: #b0bec5

.node-sound
  font-size: 20px
  font-weight: 700

.node-id
  font-size: 11px

.node-done
  position: absolute
  top: 4px
  right: 6px
  color: #2e7d32
  font-size: 13px
</style>
