<script setup lang="ts">
/**
 * DemoPlayer：正式示范播放（FR-604）：正常 / 慢速、男声 / 女声、字幕；
 * 经 player store 全局唯一播放；音频 preload none（§9）。
 */
import { computed } from 'vue'
import type { DemoItem } from '@/api'
import { usePlayerStore } from '@/stores/player'

const props = defineProps<{
  items: DemoItem[]
  mediaResolver: (mediaId: string) => string
}>()

const player = usePlayerStore()

function speedLabel(item: DemoItem): string {
  const voice = item.voice === 'male' ? '男声' : item.voice === 'female' ? '女声' : ''
  return `${item.speed === 'slow' ? '慢速' : '正常语速'}${voice ? ` · ${voice}` : ''}`
}

function play(item: DemoItem) {
  void player.play({ key: `demo:${item.mediaId}`, url: props.mediaResolver(item.mediaId), label: '示范' })
}

const grouped = computed(() => ({
  normal: props.items.filter((item) => item.speed === 'normal'),
  slow: props.items.filter((item) => item.speed === 'slow'),
}))
</script>

<template>
  <div class="demo-player" v-if="items.length > 0">
    <div class="demo-groups">
      <div v-for="(list, speed) in grouped" :key="speed" class="demo-group">
        <button
          v-for="item in list"
          :key="item.mediaId"
          type="button"
          class="demo-btn"
          @click="play(item)"
        >
          <span class="demo-icon" aria-hidden="true">▶</span>
          <span>{{ speedLabel(item) }}</span>
        </button>
      </div>
    </div>
    <p v-for="item in items" :key="`text-${item.mediaId}`" v-show="false" class="sr-only">
      {{ item.text ?? '示范音频' }}
    </p>
    <p v-if="items[0]?.text" class="demo-subtitle">示范文字：{{ items[0].text }}</p>
    <p v-if="player.current?.key?.startsWith('demo:') && player.errorMessage" class="demo-error">
      {{ player.errorMessage }}
    </p>
  </div>
  <p v-else class="demo-empty">本关示范音频暂缺</p>
</template>

<style scoped lang="sass">
.demo-player
  display: flex
  flex-direction: column
  gap: 8px

.demo-groups
  display: flex
  flex-wrap: wrap
  gap: 10px

.demo-btn
  display: inline-flex
  align-items: center
  gap: 8px
  min-height: 44px
  padding: 6px 18px
  border-radius: 999px
  border: 1px solid #00897b
  background: #e0f2f1
  color: #00695c
  font-size: 15px
  cursor: pointer
  &:hover
    background: #b2dfdb

.demo-icon
  font-size: 12px

.demo-subtitle
  font-size: 14px
  color: #546e7a
  margin: 0

.demo-error
  font-size: 13px
  color: #c62828
  margin: 0

.demo-empty
  color: #90a4ae
  font-size: 14px

.sr-only
  position: absolute
  width: 1px
  height: 1px
  overflow: hidden
  clip: rect(0 0 0 0)
</style>
