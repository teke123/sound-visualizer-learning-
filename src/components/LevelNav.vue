<script setup lang="ts">
/**
 * LevelNav：上一关 / 下一关（FR-610 改版）。
 * 页面底部附属模块（样式口径与报错模块一致）：整行左右均匀分布、视觉对称，
 * 不受关卡页两栏布局限制；目标未开放时禁用，不产生可进入链接。
 */
import { computed } from 'vue'
import { QBtn } from 'quasar'
import type { LevelDetail } from '@/api'
import { useLevelsStore } from '@/stores/levels'

const props = defineProps<{
  level: LevelDetail
}>()

const levelsStore = useLevelsStore()

interface NavItem {
  id: string
  label: string
  title: string
  available: boolean
}

function toItem(id: string | null | undefined, label: string): NavItem | null {
  if (!id) return null
  const summary = levelsStore.byId.get(id)
  return {
    id,
    label,
    title: summary?.title ?? id,
    available: Boolean(summary && summary.availability === 'open'),
  }
}

const prev = computed(() => toItem(props.level.nav?.prev, '上一关'))
const next = computed(() => toItem(props.level.nav?.next, '下一关'))
</script>

<template>
  <nav class="level-nav" aria-label="关卡导航">
    <div class="nav-slot nav-prev">
      <QBtn v-if="prev?.available" outline no-caps color="blue-grey-4" text-color="blue-grey-9" class="nav-link" :to="`/learn/${prev.id}`">
        <span class="nav-text">
          <span class="nav-label">← {{ prev.label }}</span>
          <span class="nav-title">{{ prev.title }}</span>
        </span>
      </QBtn>
      <QBtn v-else-if="prev" outline no-caps color="blue-grey-4" text-color="blue-grey-9" class="nav-link" disable>
        <span class="nav-text">
          <span class="nav-label">← {{ prev.label }}</span>
          <span class="nav-title">{{ prev.title }}（暂不可进入）</span>
        </span>
      </QBtn>
    </div>
    <div class="nav-slot nav-next">
      <QBtn v-if="next?.available" outline no-caps color="blue-grey-4" text-color="blue-grey-9" class="nav-link" :to="`/learn/${next.id}`">
        <span class="nav-text">
          <span class="nav-label">{{ next.label }} →</span>
          <span class="nav-title">{{ next.title }}</span>
        </span>
      </QBtn>
      <QBtn v-else-if="next" outline no-caps color="blue-grey-4" text-color="blue-grey-9" class="nav-link" disable>
        <span class="nav-text">
          <span class="nav-label">{{ next.label }} →</span>
          <span class="nav-title">{{ next.title }}（暂不可进入）</span>
        </span>
      </QBtn>
    </div>
  </nav>
</template>

<style scoped lang="sass">
/* 页底整行模块：两列等宽均分，左右锚定对称；宽度跟随页面容器，不受关卡页两栏限制 */
.level-nav
  display: grid
  grid-template-columns: 1fr 1fr
  gap: 12px
  margin-top: 28px

.nav-slot
  display: flex

.nav-prev
  justify-content: flex-start

.nav-next
  justify-content: flex-end
  text-align: right

.nav-link
  max-width: min(100%, 340px)
  /* 原 .nav-link 为 10px 圆角（非胶囊），覆盖全局胶囊 */
  border-radius: 10px
  :deep(.q-btn__content)
    max-width: 100%

.nav-text
  display: flex
  flex-direction: column
  align-items: flex-start
  gap: 2px
  min-width: 0
  max-width: 100%

.nav-next
  .nav-text
    align-items: flex-end

.nav-label
  font-size: 12px
  color: #90a4ae

.nav-title
  font-size: 15px
  color: inherit
  max-width: 100%
  overflow: hidden
  text-overflow: ellipsis
  white-space: nowrap
</style>
