<script setup lang="ts">
/**
 * DemoPlayer：正式示范播放（FR-604）：正常 / 慢速、支持多发音人（FV1~3 女声 1~3、MV1~3 男声 1~3）切换试听；
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

const VOICE_LABELS: Record<string, string> = {
  male: '男声',
  female: '女声',
  FV1: '女声 1 (FV1)',
  FV2: '女声 2 (FV2)',
  FV3: '女声 3 (FV3)',
  MV1: '男声 1 (MV1)',
  MV2: '男声 2 (MV2)',
  MV3: '男声 3 (MV3)',
}

function voiceLabel(voice?: string | null): string {
  if (!voice) return ''
  return VOICE_LABELS[voice] ?? voice
}

function speedLabel(item: DemoItem): string {
  const voice = voiceLabel(item.voice)
  const prefix = item.speed === 'slow' ? '慢速' : '正常语速'
  return voice ? `${voice}${item.speed === 'slow' ? ' · 慢速' : ''}` : prefix
}

function itemKey(item: DemoItem): string {
  return `demo:${item.mediaId}`
}

function isPlaying(item: DemoItem): boolean {
  return player.isCurrent(itemKey(item))
}

function play(item: DemoItem) {
  void player.play({
    key: itemKey(item),
    url: props.mediaResolver(item.mediaId),
    label: speedLabel(item),
  })
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
          :class="{ active: isPlaying(item) }"
          @click="play(item)"
        >
          <span class="demo-icon" aria-hidden="true">{{ isPlaying(item) ? '⏸' : '▶' }}</span>
          <span>{{ speedLabel(item) }}</span>
        </button>
      </div>
    </div>
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
  flex-direction: column
  gap: 8px

.demo-group
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
  transition: background 0.15s ease, color 0.15s ease
  &:hover
    background: #b2dfdb
  &.active
    background: #00897b
    color: #fff
    font-weight: 600

.demo-icon
  font-size: 12px

.demo-error
  font-size: 13px
  color: #c62828
  margin: 0

.demo-empty
  color: #90a4ae
  font-size: 14px
</style>
