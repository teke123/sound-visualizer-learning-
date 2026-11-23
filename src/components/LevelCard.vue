<script setup lang="ts">
/**
 * LevelCard：首页 / 搜索 / 发音库目录共用的关卡卡（V3 卡片语言）：
 * 编号 + 拼音大字 + 代表字 + 类型标签 + 可录音状态 + 试听 / 进入。
 */
import { computed } from 'vue'
import { mediaUrl, type LevelSummary } from '@/api'
import { usePlayerStore } from '@/stores/player'
import AppIcon from '@/components/ui/AppIcon.vue'

const props = defineProps<{
  level: LevelSummary
  /** 显示完成标记（首页 / 搜索带进度时） */
  completed?: boolean
  /** 试听开关（默认开启） */
  showListen?: boolean
}>()

const player = usePlayerStore()
const listenKey = computed(() => `demo:${props.level.id}`)
const canEnter = computed(() => props.level.availability !== 'closed')
const longPinyin = computed(() => props.level.pinyin.length > 2)

function playDemo() {
  if (!props.level.demoMediaId) return
  void player.play({ key: listenKey.value, url: mediaUrl(props.level.demoMediaId), label: props.level.title })
}
</script>

<template>
  <article class="lv" :data-level-id="level.id">
    <div class="lv-top">
      <span class="lv-id">{{ level.id }}</span>
      <span v-if="completed" class="vs-tag vs-tag--ok">已学完</span>
    </div>
    <div class="lv-py" :class="{ long: longPinyin }">{{ level.pinyin }}</div>
    <div class="lv-hz">{{ level.representativeChar ? `「${level.representativeChar}」` : level.targetSound }}</div>
    <div class="lv-foot">
      <span class="vs-tag">{{ level.type }}</span>
      <span class="lv-state" :class="{ on: canEnter }">
        <i class="lv-dot" />{{ canEnter ? '能录音' : '未开放' }}
      </span>
    </div>
    <div class="lv-actions">
      <button
        v-if="showListen !== false && level.demoMediaId"
        type="button"
        class="vs-btn vs-btn--ghost vs-btn--small"
        @click="playDemo"
      >
        <AppIcon :name="player.isCurrent(listenKey) ? 'pause' : 'sound'" size="sm" />
        {{ player.isCurrent(listenKey) ? '暂停' : '试听' }}
      </button>
      <RouterLink v-if="canEnter" :to="`/learn/${level.id}`" class="vs-btn vs-btn--small">
        进入关卡
      </RouterLink>
      <span v-else class="vs-btn vs-btn--small" aria-disabled="true">暂未开放</span>
    </div>
  </article>
</template>

<style scoped lang="sass">
.lv
  border: 1px solid var(--vs-line)
  border-radius: 8px
  background: var(--vs-card)
  box-shadow: var(--vs-sh-1)
  padding: 16px
  display: flex
  flex-direction: column
  transition: transform 0.2s var(--vs-ease), box-shadow 0.2s var(--vs-ease), border-color 0.2s var(--vs-ease)

.lv:hover
  transform: translateY(-2px)
  box-shadow: var(--vs-sh-2)
  border-color: var(--vs-line-hover)

.lv-top
  display: flex
  align-items: center
  justify-content: space-between
  gap: 8px

.lv-id
  font-size: 11.5px
  font-weight: 600
  color: var(--vs-mute)
  letter-spacing: 0.4px

.lv-py
  margin-top: 4px
  font-size: 26px
  font-weight: 800
  color: var(--vs-ink)
  line-height: 1.25
  letter-spacing: -0.5px
  &.long
    font-size: 18px

.lv-hz
  margin-top: 2px
  font-size: 13px
  color: var(--vs-sub)

.lv-foot
  margin-top: 16px
  display: flex
  align-items: center
  justify-content: space-between
  gap: 8px
  flex-wrap: wrap

.lv-state
  font-size: 11.5px
  color: var(--vs-sub)
  display: inline-flex
  align-items: center
  gap: 4px

.lv-dot
  width: 6px
  height: 6px
  border-radius: 50%
  display: inline-block
  flex: none
  background: var(--vs-line2)

.lv-state.on .lv-dot
  background: var(--vs-brand)

.lv-actions
  margin-top: 12px
  display: flex
  gap: 8px
  flex-wrap: wrap

.lv-actions .vs-btn
  flex: 1 1 auto
</style>
