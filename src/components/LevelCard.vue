<script setup lang="ts">
/**
 * LevelCard：P01 / P02 / P06 共用卡片（FR-302 / FR-702）：
 * 名称、拼音、代表字、试听、进入。
 */
import { computed } from 'vue'
import type { LevelSummary } from '@/api'
import { mediaUrl } from '@/api'
import { usePlayerStore } from '@/stores/player'

const props = defineProps<{
  level: LevelSummary
  /** 显示完成标记（P01/P02 不带进度时不传） */
  completed?: boolean
  /** 试听开关（P06 目录、P02 结果默认开启） */
  showListen?: boolean
}>()

const player = usePlayerStore()
const listenKey = computed(() => `demo:${props.level.id}`)

function playDemo() {
  if (!props.level.demoMediaId) return
  void player.play({ key: listenKey.value, url: mediaUrl(props.level.demoMediaId), label: props.level.title })
}
</script>

<template>
  <article class="level-card" :data-level-id="level.id">
    <div class="card-head">
      <span class="card-id">{{ level.id }}</span>
      <h3 class="card-title">{{ level.title }}</h3>
      <span v-if="completed" class="card-done">已学完</span>
    </div>
    <p class="card-sub">
      <span class="card-pinyin">{{ level.pinyin }}</span>
      <span v-if="level.representativeChar" class="card-char">「{{ level.representativeChar }}」</span>
      <span class="card-type">{{ level.type }}</span>
    </p>
    <div class="card-actions">
      <button
        v-if="showListen !== false && level.demoMediaId"
        type="button"
        class="card-btn"
        @click="playDemo"
      >
        {{ player.isCurrent(listenKey) ? '⏸ 暂停' : '▶ 试听' }}
      </button>
      <RouterLink v-if="level.availability !== 'closed'" :to="`/learn/${level.id}`" class="card-btn primary">
        进入关卡
      </RouterLink>
      <span v-else class="card-btn disabled">未开放</span>
    </div>
  </article>
</template>

<style scoped lang="sass">
.level-card
  background: #fff
  border: 1px solid #eceff1
  border-radius: 12px
  padding: 16px
  display: flex
  flex-direction: column
  gap: 8px

.card-head
  display: flex
  align-items: center
  gap: 8px

.card-id
  font-size: 12px
  background: #e0f2f1
  color: #00695c
  border-radius: 4px
  padding: 1px 6px

.card-title
  margin: 0
  font-size: 17px

.card-done
  margin-left: auto
  font-size: 12px
  color: #2e7d32
  background: #e8f5e9
  padding: 2px 8px
  border-radius: 999px

.card-sub
  display: flex
  gap: 8px
  align-items: baseline
  margin: 0
  color: #607d8b
  font-size: 14px

.card-type
  font-size: 12px
  border: 1px solid #cfd8dc
  border-radius: 999px
  padding: 0 8px

.card-actions
  display: flex
  gap: 10px
  margin-top: auto

.card-btn
  min-height: 44px
  display: inline-flex
  align-items: center
  padding: 4px 16px
  border-radius: 8px
  border: 1px solid #90a4ae
  background: #fff
  color: #37474f
  text-decoration: none
  font-size: 14px
  cursor: pointer
  &.primary
    border-color: #00897b
    background: #e0f2f1
    color: #00695c
    font-weight: 600
  &.disabled
    color: #b0bec5
    border-color: #eceff1
    cursor: default
</style>
