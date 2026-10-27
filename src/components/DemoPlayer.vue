<script setup lang="ts">
/**
 * DemoPlayer：正式示范播放（FR-604）：正常 / 慢速、支持多发音人（FV1~3 女声 1~3、MV1~3 男声 1~3）切换试听；
 * 经 player store 全局唯一播放；音频 preload none（§9）。
 */
import { computed } from 'vue'
import { QBtn } from 'quasar'
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
  FV1: '女声 1',
  FV2: '女声 2',
  FV3: '女声 3',
  MV1: '男声 1',
  MV2: '男声 2',
  MV3: '男声 3',
}

function voiceLabel(voice?: string | null): string {
  if (!voice) return ''
  return VOICE_LABELS[voice] ?? voice
}

/** 按钮内紧凑展示：性别 + 数字（如「女 1」），代号不进 UI */
function compactVoiceLabel(voice?: string | null): string {
  const m = /^([FM])V(\d)$/.exec(voice ?? '')
  if (m) return `${m[1] === 'F' ? '女' : '男'} ${m[2]}`
  return voiceLabel(voice)
}

function speedLabel(item: DemoItem): string {
  const voice = voiceLabel(item.voice)
  return voice ? `${voice}${item.speed === 'slow' ? ' · 慢速' : ''}` : item.speed === 'slow' ? '慢速' : '正常语速'
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
        <QBtn
          v-for="item in list"
          :key="item.mediaId"
          class="demo-btn"
          :class="{ active: isPlaying(item), slow: item.speed === 'slow' }"
          no-caps
          color="primary"
          :text-color="isPlaying(item) ? 'white' : 'teal-9'"
          size="13px"
          :unelevated="isPlaying(item)"
          :outline="!isPlaying(item)"
          :icon="isPlaying(item) ? 'pause' : 'play_arrow'"
          :aria-label="`${isPlaying(item) ? '暂停' : '播放'}示范：${speedLabel(item)}`"
          :title="speedLabel(item)"
          @click="play(item)"
        >
          <span>{{ compactVoiceLabel(item.voice) }}</span>
          <span v-if="item.speed === 'slow'" class="demo-speed-tag">慢</span>
        </QBtn>
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

/* 原 .demo-btn 32px 浅青胶囊：未选中浅青底 / 悬停深一档 / 慢速虚线描边由 scoped 补回。
   Quasar outline 底色为 transparent !important，填充需 important（仅限 .q-btn--outline 未选中态，
   不覆盖选中时的实底青）；选中实底青 + 白字 + 600 字重为原版 .active 形态，由 QBtn unelevated + 全局字重承担 */
.demo-btn
  min-height: 32px
  &.q-btn--outline
    background: #e0f2f1 !important
    &:hover
      background: #b2dfdb !important
  &.slow:before
    border-style: dashed

.demo-speed-tag
  font-size: 11px
  line-height: 1
  padding: 2px 4px
  border-radius: 4px
  background: rgba(0, 137, 123, 0.12)
  .demo-btn.active &
    background: rgba(255, 255, 255, 0.25)

.demo-error
  font-size: 13px
  color: #c62828
  margin: 0

.demo-empty
  color: #90a4ae
  font-size: 14px
</style>
