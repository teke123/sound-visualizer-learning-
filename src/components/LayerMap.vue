<script setup lang="ts">
/**
 * LayerMap：P03 三层闯关定位图（FR-401/402/404，FD-13）。
 * 固定三层：单韵母 → 声母 → 拼读；已开放可点进；骨架仅身份 + 「未开放」；
 * 不承载专业说明与 IPA；完成标记来自进度门面。
 */
import { computed } from 'vue'
import { QBadge, QCard, QCardSection } from 'quasar'
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

const LAYERS: Array<{ key: LevelSummary['layer']; name: string }> = [
  { key: 'vowel', name: '单韵母' },
  { key: 'initial', name: '声母' },
  { key: 'syllable', name: '拼读' },
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
    <QCard
      v-for="layer in layers"
      :key="layer.key"
      tag="section"
      flat
      bordered
      class="map-layer"
      :aria-label="layer.name"
    >
      <QCardSection>
        <header class="layer-head">
          <h2>{{ layer.name }}</h2>
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
              <QBadge v-if="node.completed" class="node-done" color="positive" aria-label="已完成">✓</QBadge>
            </RouterLink>
            <span v-else class="map-node skeleton" aria-label="未开放">
              <span class="node-sound">{{ node.label }}</span>
              <QBadge class="node-id" color="grey-3" text-color="grey-7">未开放</QBadge>
            </span>
          </template>
        </div>
      </QCardSection>
    </QCard>
  </div>
</template>

<style scoped lang="sass">
.layer-map
  display: flex
  flex-direction: column
  gap: 24px

.layer-head
  h2
    margin: 0 0 12px
    font-size: 17px

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

.node-done
  position: absolute
  top: 4px
  right: 6px
</style>
