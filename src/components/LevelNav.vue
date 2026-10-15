<script setup lang="ts">
/**
 * LevelNav：上一关 / 下一关 / 易混关 / 关联关（FR-610）。
 * L30 提供回到 L01 与 L09 的关系；目标未发布时禁用，不产生可进入链接。
 */
import { computed } from 'vue'
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

function toItem(id: string, label: string): NavItem | null {
  if (!id) return null
  const summary = levelsStore.byId.get(id)
  return {
    id,
    label,
    title: summary?.title ?? id,
    available: Boolean(summary && summary.availability === 'open'),
  }
}

const items = computed<NavItem[]>(() => {
  const nav = props.level.nav
  const list: Array<NavItem | null> = [
    nav.prevId ? toItem(nav.prevId, '上一关') : null,
    nav.nextId ? toItem(nav.nextId, '下一关') : null,
    ...(nav.confusableIds ?? []).map((id) => toItem(id, '易混关')),
    ...(nav.relatedIds ?? []).map((id) => toItem(id, `回看 ${id}`)),
  ]
  return list.filter((item): item is NavItem => item !== null)
})
</script>

<template>
  <nav class="level-nav" aria-label="关卡导航">
    <template v-for="item in items" :key="`${item.label}-${item.id}`">
      <RouterLink v-if="item.available" :to="`/learn/${item.id}`" class="nav-link">
        <span class="nav-label">{{ item.label }}</span>
        <span class="nav-title">{{ item.title }}</span>
      </RouterLink>
      <span v-else class="nav-link disabled">
        <span class="nav-label">{{ item.label }}</span>
        <span class="nav-title">{{ item.title }}（暂不可进入）</span>
      </span>
    </template>
  </nav>
</template>

<style scoped lang="sass">
.level-nav
  display: flex
  flex-wrap: wrap
  gap: 10px
  margin-top: 24px

.nav-link
  display: flex
  flex-direction: column
  gap: 2px
  padding: 10px 16px
  border: 1px solid #cfd8dc
  border-radius: 10px
  text-decoration: none
  min-width: 140px
  &:hover
    border-color: #26a69a
  &.disabled
    color: #b0bec5
    border-style: dashed

.nav-label
  font-size: 12px
  color: #90a4ae

.nav-title
  font-size: 15px
  color: inherit
</style>
