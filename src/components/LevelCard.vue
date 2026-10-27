<script setup lang="ts">
/**
 * LevelCard：P01 / P02 / P06 共用卡片（FR-302 / FR-702）：
 * 名称、拼音、代表字、试听、进入。
 */
import { computed } from 'vue'
import { QBadge, QBtn, QCard, QCardSection } from 'quasar'
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
  <QCard flat bordered tag="article" class="level-card" :data-level-id="level.id">
    <QCardSection class="card-body">
      <div class="card-head">
        <span class="card-id">{{ level.id }}</span>
        <h3 class="card-title">{{ level.title }}</h3>
        <QBadge v-if="completed" color="positive" class="card-done">已学完</QBadge>
      </div>
      <p class="card-sub">
        <span class="card-pinyin">{{ level.pinyin }}</span>
        <span v-if="level.representativeChar" class="card-char">「{{ level.representativeChar }}」</span>
        <span class="card-type">{{ level.type }}</span>
      </p>
      <div class="card-actions">
        <QBtn
          v-if="showListen !== false && level.demoMediaId"
          outline
          no-caps
          color="blue-grey-4"
          text-color="blue-grey-9"
          class="card-btn"
          :label="player.isCurrent(listenKey) ? '⏸ 暂停' : '▶ 试听'"
          @click="playDemo"
        />
        <QBtn
          v-if="level.availability !== 'closed'"
          outline
          no-caps
          color="primary"
          text-color="teal-9"
          class="card-btn primary"
          label="进入关卡"
          :to="`/learn/${level.id}`"
        />
        <QBtn v-else outline no-caps color="blue-grey-3" text-color="blue-grey-3" class="card-btn" label="未开放" disable />
      </div>
    </QCardSection>
  </QCard>
</template>

<style scoped lang="sass">
.level-card
  display: flex
  flex-direction: column

.card-body
  flex: 1
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

/* 原 .card-btn：44px 触达高度 / 8px 圆角（非胶囊）；
   .primary 浅青底 + 字重 600（Quasar outline 底色为 transparent !important，填充需 important 补回） */
.card-btn
  min-height: 44px
  border-radius: 8px
  &.primary
    background: #e0f2f1 !important
    font-weight: 600
</style>
