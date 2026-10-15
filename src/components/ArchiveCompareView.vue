<script setup lang="ts">
/**
 * ArchiveCompareView：本人同关两条存档比较（FR-1103 / V1-AC27）：
 * 并排播放、曲线对比、可比范围提示、主要差异（仅可比维度）。
 * 后端比较响应为嵌套结构：a/b = {recording, result, rangeSnapshot}。
 */
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { audioFileUrl, type ArchiveCompareResponse } from '@/api'
import { usePlayerStore } from '@/stores/player'
import { errorCopy } from '@/copy/usePageCopy'
import { formatDateTime } from '@/utils'
import PageState from './PageState.vue'

const ToneCurveChart = defineAsyncComponent(() => import('@/renderers/ToneCurveChart.vue'))

const props = defineProps<{
  aId: string
  bId: string
}>()

const emit = defineEmits<{ (e: 'back'): void }>()

const player = usePlayerStore()
const data = ref<ArchiveCompareResponse | null>(null)
const loading = ref(true)
const error = ref<unknown>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    const { archiveApi } = await import('@/api')
    const res = await archiveApi.compare(props.aId, props.bId)
    data.value = res.data
  } catch (err) {
    error.value = err
  } finally {
    loading.value = false
  }
}

watch(() => [props.aId, props.bId] as const, () => void load(), { immediate: true })

function play(audioId: string) {
  void player.play({ key: `audio:${audioId}`, url: audioFileUrl(audioId), label: '存演回放' })
}

const comparableNotes = computed(() => data.value?.reasons ?? [])
const sides = computed(() => (data.value ? [data.value.a, data.value.b] : []))
</script>

<template>
  <div class="archive-compare">
    <header class="ac-head">
      <button type="button" class="ac-back" @click="emit('back')">← 返回档案</button>
      <h2>同关记录比较</h2>
    </header>

    <PageState v-if="loading" state="loading" />
    <PageState v-else-if="error" state="not-visible" :text="errorCopy(error).title" />

    <template v-if="data">
      <p v-if="comparableNotes.length > 0" class="ac-notes" role="note">
        <template v-for="note in comparableNotes" :key="note">· {{ note }}<br /></template>
      </p>

      <div class="ac-grid">
        <section v-for="side in sides" :key="side.recording.recordingId" class="ac-side">
          <header class="ac-side-head">
            <span class="ac-date">{{ formatDateTime(side.recording.createdAt ?? undefined) }}</span>
            <span v-if="typeof side.result?.score === 'number'" class="ac-score">
              {{ Math.round(side.result.score!) }} 分
            </span>
            <span v-else class="ac-score muted">未评分</span>
            <button type="button" class="ac-play" @click="play(side.recording.audioId)">
              {{ player.isCurrent(`audio:${side.recording.audioId}`) ? '⏸ 暂停' : '▶ 播放' }}
            </button>
          </header>
          <ToneCurveChart v-if="side.result?.curve" :curve="side.result.curve" :height="240" />
          <p v-else class="ac-no-curve">无曲线数据</p>
        </section>
      </div>

      <section v-if="(data.differences?.length ?? 0) > 0" class="ac-diff" aria-label="主要差异">
        <h3>主要差异</h3>
        <ul>
          <li v-for="(diff, index) in data.differences ?? []" :key="index">
            <strong>{{ diff.dimension }}</strong>：{{ diff.description }}
          </li>
        </ul>
      </section>
      <p v-else class="ac-diff-empty">两次记录在可比维度上没有明显差异。</p>
    </template>
  </div>
</template>

<style scoped lang="sass">
.archive-compare
  max-width: 920px
  margin: 0 auto

.ac-head
  display: flex
  align-items: center
  gap: 14px
  h2
    margin: 0
    font-size: 20px

.ac-back
  min-height: 44px
  padding: 4px 14px
  border: 1px solid #cfd8dc
  border-radius: 8px
  background: #fff
  cursor: pointer

.ac-notes
  background: #fff8e1
  border: 1px solid #ffe082
  border-radius: 8px
  padding: 10px 14px
  font-size: 13px
  color: #5d4037
  line-height: 1.8

.ac-grid
  display: grid
  grid-template-columns: 1fr 1fr
  gap: 14px
  margin-top: 14px

.ac-side
  border: 1px solid #eceff1
  border-radius: 12px
  padding: 12px
  background: #fff

.ac-side-head
  display: flex
  align-items: center
  gap: 10px
  flex-wrap: wrap
  margin-bottom: 8px

.ac-date
  font-size: 13px
  color: #546e7a

.ac-score
  font-weight: 800
  font-size: 18px
  &.muted
    color: #b0bec5
    font-size: 13px

.ac-play
  margin-left: auto
  min-height: 40px
  padding: 2px 14px
  border-radius: 999px
  border: 1px solid #00897b
  background: #e0f2f1
  color: #00695c
  cursor: pointer

.ac-no-curve
  color: #b0bec5
  font-size: 13px
  text-align: center
  padding: 20px 0

.ac-diff
  margin-top: 18px
  h3
    margin: 0 0 8px
    font-size: 16px
  ul
    margin: 0
    padding-left: 18px
    line-height: 1.9
    font-size: 14px
    color: #455a64

.ac-diff-empty
  margin-top: 14px
  color: #90a4ae
  font-size: 14px

@media (max-width: 640px)
  .ac-grid
    grid-template-columns: 1fr
</style>
