<script setup lang="ts">
/**
 * P01 首页（FR-201–206）：四个主按钮、搜索框、已开放关入口、下一关推荐；
 * 无已开放关时后三个按钮显示「暂无已开放内容」。
 * 「跟着练」「录音比较」都进入下一关 P05 的练习区 / 录音区（D-03：检测在 P05 完成）。
 */
import { computed, onMounted } from 'vue'
import { useLevelsStore } from '@/stores/levels'
import { useProgressStore } from '@/stores/progress'
import LevelCard from '@/components/LevelCard.vue'
import SearchBox from '@/components/SearchBox.vue'
import PageState from '@/components/PageState.vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const levelsStore = useLevelsStore()
const progressStore = useProgressStore()

onMounted(() => {
  if (!levelsStore.loaded) void levelsStore.refresh()
})

const published = computed(() => levelsStore.published)
const hasPublished = computed(() => published.value.length > 0)
const nextLevelId = computed(() => progressStore.nextLevelId)
const nextLevel = computed(() =>
  nextLevelId.value ? levelsStore.byId.get(nextLevelId.value) : undefined,
)

function onSearch(q: string) {
  void router.push({ path: '/search', query: { q } })
}
</script>

<template>
  <div class="home-page">
    <section class="hero">
      <h1>看得见的声音</h1>
      <p class="hero-sub">看口型、听示范、跟着练、录一录——用眼睛和耳朵一起学普通话发音。</p>
      <SearchBox class="hero-search" @search="onSearch" />
    </section>

    <nav class="main-buttons" aria-label="四个主入口">
      <RouterLink to="/search" class="main-btn">🔍 搜一个音</RouterLink>
      <RouterLink to="/principles" class="main-btn">📖 看懂发音</RouterLink>
      <RouterLink
        v-if="hasPublished"
        :to="nextLevelId ? `/learn/${nextLevelId}#practice` : '/library'"
        class="main-btn"
      >
        🏃 跟着练
      </RouterLink>
      <span v-else class="main-btn disabled">🏃 跟着练<span class="btn-note">暂无已开放内容</span></span>
      <RouterLink
        v-if="hasPublished"
        :to="nextLevelId ? `/learn/${nextLevelId}#record` : '/library'"
        class="main-btn"
      >
        🎤 录音比较
      </RouterLink>
      <span v-else class="main-btn disabled">🎤 录音比较<span class="btn-note">暂无已开放内容</span></span>
    </nav>

    <section v-if="nextLevel" class="next-level" aria-label="下一关推荐">
      <h2>从这一关继续</h2>
      <LevelCard :level="nextLevel" :completed="progressStore.completedIds.has(nextLevel.id)" />
    </section>

    <section class="levels-entry" aria-label="已开放关卡">
      <h2>全部关卡</h2>
      <PageState v-if="levelsStore.loading && !levelsStore.loaded" state="loading" />
      <PageState v-else-if="levelsStore.error && !hasPublished" :state="'error'" :error="levelsStore.error" @retry="levelsStore.refresh()" />
      <p v-else-if="!hasPublished" class="no-levels">暂无已开放关卡，内容正在准备中。</p>
      <template v-else>
        <div class="level-grid">
          <LevelCard
            v-for="level in published.slice(0, 6)"
            :key="level.id"
            :level="level"
            :completed="progressStore.completedIds.has(level.id)"
          />
        </div>
        <RouterLink v-if="published.length > 6" to="/library" class="more-link">
          查看全部 {{ published.length }} 关 →
        </RouterLink>
      </template>
    </section>
  </div>
</template>

<style scoped lang="sass">
.home-page
  display: flex
  flex-direction: column
  gap: 28px

.hero
  text-align: center
  padding: 22px 0 6px
  h1
    margin: 0 0 8px
    font-size: 30px
    color: #00695c

.hero-sub
  color: #546e7a
  margin: 0 auto 16px
  max-width: 480px

.hero-search
  margin: 0 auto

.main-buttons
  display: grid
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))
  gap: 12px

.main-btn
  min-height: 96px
  border-radius: 14px
  background: #fff
  border: 2px solid #b2dfdb
  display: flex
  flex-direction: column
  align-items: center
  justify-content: center
  gap: 6px
  font-size: 17px
  font-weight: 700
  color: #00695c
  text-decoration: none
  padding: 12px
  text-align: center
  &:hover
    background: #e0f2f1
  &.disabled
    border-color: #eceff1
    color: #b0bec5
    cursor: default

.btn-note
  font-size: 12px
  font-weight: 400
  color: #b0bec5

.next-level h2, .levels-entry h2
  font-size: 18px
  margin: 0 0 12px

.level-grid
  display: grid
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr))
  gap: 14px

.no-levels
  color: #90a4ae

.more-link
  display: inline-block
  margin-top: 12px
  color: #00897b
  font-weight: 600
  text-decoration: none
</style>
