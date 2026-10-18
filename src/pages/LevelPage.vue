<script setup lang="ts">
/**
 * P05 关卡页（FR-601–610）：加载与 404 态在此处理，内容交 LevelLearnSection；
 * 进入时校验已开放；404/LEVEL_NOT_PUBLISHED → 统一不可见并刷新 levels（NFR-11）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError, contentApi, type LevelDetail } from '@/api'
import { levelDetailCache } from '@/features/compare'
import { useLevelsStore } from '@/stores/levels'
import LevelLearnSection from './LevelLearnSection.vue'
import PageState from '@/components/PageState.vue'

const route = useRoute()
const levelsStore = useLevelsStore()

const levelId = computed(() => String(route.params.id ?? ''))
const level = ref<LevelDetail | null>(null)
const loading = ref(true)
const notVisible = ref(false)
const loadError = ref<unknown>(null)

async function load(): Promise<void> {
  loading.value = true
  notVisible.value = false
  loadError.value = null
  try {
    const cached = levelDetailCache.get(levelId.value)
    if (cached) level.value = cached
    const res = await contentApi.level(levelId.value)
    level.value = res.data
    levelDetailCache.set(levelId.value, res.data)
  } catch (err) {
    level.value = null
    if (
      err instanceof ApiError &&
      (err.status === 404 || err.code === 'NOT_FOUND' || err.code === 'LEVEL_NOT_PUBLISHED')
    ) {
      notVisible.value = true
      // 详情 404：立即刷新 levels（下架同步）
      levelsStore.invalidate()
      void levelsStore.refresh({ background: true })
    } else {
      loadError.value = err
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!levelsStore.loaded) void levelsStore.refresh()
})

watch(levelId, () => void load(), { immediate: true })

/* 锚点滚动（#quiz / #practice / #record / #step-{id}） */
watch(
  () => route.hash,
  (hash) => {
    if (!hash) return
    requestAnimationFrame(() => {
      document.querySelector(hash)?.scrollIntoView({ behavior: 'smooth' })
    })
  },
  { immediate: true },
)
</script>

<template>
  <div class="level-page">
    <PageState v-if="loading && !level" state="loading" />
    <PageState v-else-if="notVisible" state="not-visible" text="这一关不存在或暂不可见（可能已下架）" />
    <PageState v-else-if="loadError" state="error" :error="loadError" @retry="load" />
    <LevelLearnSection v-else-if="level" :key="level.id" :level="level" @reload="load" />
  </div>
</template>

<style scoped lang="sass">
.level-page
  padding-bottom: 20px
</style>
