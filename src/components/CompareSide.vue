<script setup lang="ts">
/** CompareSide：比较面板单侧（示范播放 + 构形主图 + 说明） */
import { computed } from 'vue'
import type { LevelDetail } from '@/api'
import { mediaUrl } from '@/api'
import { usePlayerStore } from '@/stores/player'

const props = defineProps<{ level: LevelDetail }>()

const player = usePlayerStore()
const demos = computed(() => props.level.demos ?? [])
const demo = computed(() => demos.value.find((item) => item.speed === 'normal') ?? demos.value[0])
const mainMedia = computed(() => (props.level.articulation?.media ?? [])[0])
const articulationDesc = computed(() => props.level.articulation?.description ?? '')
const listenKey = computed(() => `demo:${props.level.id}`)

function playDemo() {
  if (!demo.value) return
  void player.play({ key: listenKey.value, url: mediaUrl(demo.value.mediaId), label: props.level.title })
}
</script>

<template>
  <div class="compare-side">
    <h3>{{ level.title }}（{{ level.pinyin }}）</h3>
    <figure v-if="mainMedia" class="compare-figure">
      <img :src="mediaUrl(mainMedia.mediaId)" :alt="mainMedia.altText" loading="lazy" />
      <figcaption>{{ mainMedia.altText }}</figcaption>
    </figure>
    <p v-else class="compare-nofigure">（无构形图）</p>
    <button v-if="demo" type="button" class="compare-demo-btn" @click="playDemo">
      {{ player.isCurrent(listenKey) ? '⏸ 暂停示范' : '▶ 播放示范' }}
    </button>
    <p class="compare-desc">{{ articulationDesc }}</p>
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

.compare-figure
  margin: 0
  img
    width: 100%
    border-radius: 8px
    background: #f5f5f5
  figcaption
    font-size: 12px
    color: #90a4ae
    margin-top: 4px

.compare-nofigure
  color: #b0bec5
  font-size: 13px
  margin: 0

.compare-demo-btn
  min-height: 44px
  padding: 4px 18px
  width: fit-content
  border-radius: 999px
  border: 1px solid #00897b
  background: #e0f2f1
  color: #00695c
  cursor: pointer

.compare-desc
  font-size: 13px
  color: #546e7a
  margin: 0
</style>
