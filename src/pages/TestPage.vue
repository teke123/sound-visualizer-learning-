<script setup lang="ts">
/**
 * P08 检测中心（FR-901–908）：/test 选关（仅已发布；熔断关显示故障）；
 * /test/:levelId 任务页（TestTaskSection）。与 P05 内嵌录音同一套评分口径。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError, type LevelDetail } from '@/api'
import { levelDetailCache, loadLevelDetail } from '@/features/compare'
import { useLevelsStore } from '@/stores/levels'
import { useProgressStore } from '@/stores/progress'
import { useRecorderStore } from '@/stores/recorder'
import LevelCard from '@/components/LevelCard.vue'
import TestTaskSection from './TestTaskSection.vue'
import PageState from '@/components/PageState.vue'

const route = useRoute()
const levelsStore = useLevelsStore()
const progressStore = useProgressStore()
const recorder = useRecorderStore()

const levelId = computed(() => (typeof route.params.levelId === 'string' ? route.params.levelId : ''))
const isPicker = computed(() => !levelId.value)

onMounted(() => {
  if (!levelsStore.loaded) void levelsStore.refresh()
})

const pickerLevels = computed(() => levelsStore.published)
const recommended = computed(() => progressStore.nextLevelId)

const level = ref<LevelDetail | null>(null)
const loading = ref(false)
const notVisible = ref(false)
const loadError = ref<unknown>(null)

async function load(): Promise<void> {
  if (!levelId.value) return
  loading.value = true
  notVisible.value = false
  loadError.value = null
  try {
    const cached = levelDetailCache.get(levelId.value)
    if (cached) level.value = cached
    level.value = await loadLevelDetail(levelId.value)
  } catch (err) {
    level.value = null
    if (
      err instanceof ApiError &&
      (err.status === 404 || err.code === 'NOT_FOUND' || err.code === 'LEVEL_NOT_PUBLISHED')
    ) {
      notVisible.value = true
      levelsStore.invalidate()
      void levelsStore.refresh({ background: true })
    } else {
      loadError.value = err
    }
  } finally {
    loading.value = false
  }
}

watch(levelId, () => void load(), { immediate: true })
watch(
  levelId,
  (id) => {
    if (!id) recorder.release()
  },
  { immediate: true },
)

const summary = computed(() => (levelId.value ? levelsStore.byId.get(levelId.value) : undefined))
const detectionOff = computed(
  () => summary.value?.availability === 'temporarily_unavailable' || level.value?.detection?.available === false,
)
</script>

<template>
  <div class="test-page">
    <!-- 选关列表 -->
    <template v-if="isPicker">
      <header class="test-head">
        <h1>检测中心</h1>
        <p>选一关，按要求朗读并提交；与关卡页录音是同一套任务和评分口径。</p>
      </header>

      <p v-if="recommended && levelsStore.byId.get(recommended)" class="recommend">
        建议从
        <RouterLink :to="`/test/${recommended}`">{{ levelsStore.byId.get(recommended)!.title }}</RouterLink>
        继续 →
      </p>

      <PageState v-if="levelsStore.loading && !levelsStore.loaded" state="loading" />
      <PageState
        v-else-if="levelsStore.error && pickerLevels.length === 0"
        state="error"
        :error="levelsStore.error"
        @retry="levelsStore.refresh()"
      />
      <p v-else-if="pickerLevels.length === 0" class="no-levels">暂无已发布关卡。</p>
      <div v-else class="picker-grid">
        <div v-for="item in pickerLevels" :key="item.id" class="picker-cell">
          <span v-if="item.availability === 'temporarily_unavailable'" class="fault-badge">检测暂停</span>
          <LevelCard :level="item" :completed="progressStore.completedIds.has(item.id)" />
        </div>
      </div>
    </template>

    <!-- 任务页 -->
    <template v-else>
      <nav class="back-nav">
        <RouterLink to="/test">← 换一关</RouterLink>
      </nav>

      <PageState v-if="loading && !level" state="loading" />
      <PageState v-else-if="notVisible" state="not-visible" text="这一关不存在或暂不可见" />
      <PageState v-else-if="loadError" state="error" :error="loadError" @retry="load" />

      <template v-if="level">
        <header class="test-head">
          <h1>{{ level.title }} · 录音检测</h1>
          <p class="task-goal">{{ level.oneLiner }}</p>
        </header>

        <!-- 熔断：故障说明 + 学习入口保留（D-05） -->
        <div v-if="detectionOff" class="detection-off" role="note">
          <h2>🎤 这一关的录音检测暂停中</h2>
          <p>检测服务正在维护，恢复后可以照常录音评分；学习内容不受影响。</p>
          <RouterLink :to="`/learn/${level.id}`" class="off-link">先去学习这一关 →</RouterLink>
        </div>
        <TestTaskSection v-else :key="level.id" :level="level" />
      </template>
    </template>
  </div>
</template>

<style scoped lang="sass">
.test-page
  display: flex
  flex-direction: column
  gap: 20px

.test-head
  h1
    margin: 0 0 4px
    font-size: 24px
  p
    margin: 0
    color: #78909c
    font-size: 14px

.task-goal
  color: #00695c !important

.recommend
  font-size: 14px
  a
    color: #00897b
    font-weight: 600

.no-levels
  color: #90a4ae

.picker-grid
  display: grid
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr))
  gap: 14px

.picker-cell
  position: relative

.fault-badge
  position: absolute
  top: 10px
  right: 10px
  z-index: 2
  background: #ffe0b2
  color: #8d5b00
  font-size: 12px
  border-radius: 999px
  padding: 2px 10px

.back-nav a
  color: #00897b
  text-decoration: none
  font-size: 14px

.detection-off
  background: #eceff1
  border: 1px solid #cfd8dc
  border-radius: 12px
  padding: 18px
  h2
    margin: 0 0 6px
    font-size: 17px
  p
    margin: 0 0 10px
    color: #546e7a
    font-size: 14px

.off-link
  color: #00897b
  font-weight: 700
  text-decoration: none
</style>
