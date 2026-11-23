<script setup lang="ts">
/**
 * LayerMap：P03 三层闯关定位图（FR-401/402/404，FD-13）。
 * 固定三层：单韵母 → 声母 → 拼读；已开放可点进；骨架仅身份 + 「未开放」；
 * 不承载专业说明与 IPA；完成标记来自进度门面。
 */
import { computed } from 'vue'
import type { LevelSkeleton, LevelSummary } from '@/api'
import AppIcon from '@/components/ui/AppIcon.vue'

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

const LAYERS: Array<{ key: LevelSummary['layer']; name: string; desc: string }> = [
  { key: 'vowel', name: '单韵母', desc: '先把嘴巴和舌头的固定姿势练稳' },
  { key: 'initial', name: '声母', desc: '再看气从哪里出、舌头挡在哪儿' },
  { key: 'syllable', name: '拼读', desc: '最后把声母和韵母连起来读' },
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
    const nodes = [...published, ...skeleton].sort((a, b) => a.order - b.order)
    return { ...layer, nodes, openCount: published.length }
  }),
)
</script>

<template>
  <div class="layer-map">
    <section
      v-for="(layer, index) in layers"
      :key="layer.key"
      class="map-layer"
      :aria-label="layer.name"
    >
      <header class="layer-head">
        <span class="vs-tag">第 {{ index + 1 }} 层</span>
        <h2>{{ layer.name }}</h2>
        <span class="layer-range">已开放 {{ layer.openCount }} 个音</span>
      </header>
      <p class="layer-desc">{{ layer.desc }}</p>
      <div class="layer-nodes">
        <template v-for="node in layer.nodes" :key="node.id">
          <RouterLink
            v-if="node.published"
            :to="`/learn/${node.id}`"
            class="node"
            :class="{ completed: node.completed }"
            :aria-label="`${node.label}${node.completed ? '（已完成）' : ''}`"
          >
            <span class="node-sound">{{ node.label }}</span>
            <small>
              <AppIcon v-if="node.completed" name="check" size="sm" />
              {{ node.completed ? '已完成' : '能录音' }}
            </small>
          </RouterLink>
          <span v-else class="node locked" aria-label="未开放">
            <span class="node-sound">{{ node.label }}</span>
            <small>未开放</small>
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
  gap: 16px

.map-layer
  background: var(--vs-card)
  border: 1px solid var(--vs-line)
  border-radius: 8px
  padding: 24px
  box-shadow: var(--vs-sh-1)

.layer-head
  display: flex
  align-items: center
  gap: 8px
  flex-wrap: wrap
  h2
    font-size: 22px
    font-weight: 900
    letter-spacing: -0.3px
    margin: 0

.layer-range
  font-size: 12px
  color: var(--vs-mute)

.layer-desc
  margin: 6px 0 0
  font-size: 13px
  color: var(--vs-sub)

.layer-nodes
  display: flex
  flex-wrap: wrap
  gap: 8px
  margin-top: 16px

.node
  border: 1px solid var(--vs-line2)
  background: var(--vs-card)
  color: var(--vs-ink)
  cursor: pointer
  border-radius: 8px
  padding: 8px 12px
  font-size: 15px
  font-weight: 700
  display: flex
  flex-direction: column
  align-items: flex-start
  justify-content: center
  min-width: 72px
  line-height: 1.4
  text-decoration: none
  transition: border-color 0.16s var(--vs-ease), background 0.16s var(--vs-ease)

.node small
  font-weight: 400
  font-size: 11px
  color: var(--vs-sub)
  display: inline-flex
  align-items: center
  gap: 2px

.node:hover
  border-color: var(--vs-line-strong)
  background: var(--vs-brand-soft)

.node.completed
  border-color: var(--vs-green-line)
  background: var(--vs-green-soft)

.node.completed small
  color: var(--vs-green)

.node.locked
  cursor: not-allowed
  background: var(--vs-panel)
  color: var(--vs-mute)
  border-style: dashed
</style>
