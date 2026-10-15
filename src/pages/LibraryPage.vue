<script setup lang="ts">
/**
 * P06 发音库（FR-701–703）：已发布关目录（分层）、试听、任选两关比较、易混快捷项。
 * 工具页：不承载进度（进度呈现归 P03）。
 */
import { computed, onMounted, ref } from 'vue'
import { useLevelsStore } from '@/stores/levels'
import { useComparePanel } from '@/features/compare'
import LevelCard from '@/components/LevelCard.vue'
import ComparePanel from '@/components/ComparePanel.vue'
import PageState from '@/components/PageState.vue'

const levelsStore = useLevelsStore()
const compare = useComparePanel()

const pickMode = ref(false)
const selected = ref<string[]>([])

onMounted(() => {
  if (!levelsStore.loaded) void levelsStore.refresh()
})

const LAYERS = [
  { key: 'vowel', name: '单韵母' },
  { key: 'initial', name: '声母' },
  { key: 'fusion', name: '拼读' },
] as const

const byLayer = computed(() =>
  LAYERS.map((layer) => ({
    ...layer,
    levels: levelsStore.published.filter((level) => level.layer === layer.key),
  })),
)

const compareOpen = computed(() => compare.pair.value !== null)

function togglePick(levelId: string) {
  if (selected.value.includes(levelId)) {
    selected.value = selected.value.filter((id) => id !== levelId)
  } else {
    selected.value = [...selected.value.slice(-1), levelId]
  }
}

function compareSelection() {
  if (selected.value.length === 2) {
    void compare.open(selected.value[0]!, selected.value[1]!)
    selected.value = []
    pickMode.value = false
  }
}

function comparePair(aId: string, bId: string) {
  void compare.open(aId, bId)
}
</script>

<template>
  <div class="library-page">
    <header class="lib-head">
      <div>
        <h1>发音库</h1>
        <p>全部已发布关卡：可试听、可进关，也可以任选两关并排比较。</p>
      </div>
      <button type="button" :class="['pick-toggle', { active: pickMode }]" @click="pickMode = !pickMode; selected = []">
        {{ pickMode ? '退出选择' : '任选两关比较' }}
      </button>
    </header>

    <div v-if="pickMode" class="pick-bar">
      <span>已选 {{ selected.length }} / 2</span>
      <button type="button" class="pick-go" :disabled="selected.length !== 2" @click="compareSelection">
        打开比较
      </button>
    </div>

    <!-- 易混对快捷项（FR-703） -->
    <section v-if="levelsStore.confusablePairs.length > 0 && !pickMode" class="quick-pairs" aria-label="易混关快捷比较">
      <h2>易混关快捷比较</h2>
      <div class="quick-row">
        <button
          v-for="pair in levelsStore.confusablePairs"
          :key="`${pair.aId}-${pair.bId}`"
          type="button"
          class="quick-btn"
          @click="comparePair(pair.aId, pair.bId)"
        >
          {{ levelsStore.byId.get(pair.aId)?.targetSound ?? pair.aId }} vs
          {{ levelsStore.byId.get(pair.bId)?.targetSound ?? pair.bId }}
        </button>
      </div>
    </section>

    <PageState v-if="levelsStore.loading && !levelsStore.loaded" state="loading" />
    <PageState
      v-else-if="levelsStore.error && levelsStore.levels.length === 0"
      state="error"
      :error="levelsStore.error"
      @retry="levelsStore.refresh()"
    />
    <template v-else>
      <section v-for="layer in byLayer" :key="layer.key" class="lib-layer" :aria-label="layer.name">
        <h2>{{ layer.name }}</h2>
        <p v-if="layer.levels.length === 0" class="layer-empty">暂无已发布关卡</p>
        <div class="lib-grid">
          <div v-for="level in layer.levels" :key="level.id" class="lib-cell">
            <button v-if="pickMode" type="button" :class="['pick-check', { checked: selected.includes(level.id) }]" @click="togglePick(level.id)">
              {{ selected.includes(level.id) ? '✓ 已选' : '选择' }}
            </button>
            <LevelCard :level="level" :show-listen="!pickMode" />
          </div>
        </div>
      </section>
    </template>

    <ComparePanel
      :open="compareOpen"
      :detail-a="compare.detailA.value"
      :detail-b="compare.detailB.value"
      :loading="compare.loading.value"
      :error="compare.error.value"
      @close="compare.close()"
    />
  </div>
</template>

<style scoped lang="sass">
.library-page
  display: flex
  flex-direction: column
  gap: 24px

.lib-head
  display: flex
  justify-content: space-between
  align-items: center
  gap: 12px
  flex-wrap: wrap
  h1
    margin: 0 0 4px
    font-size: 24px
  p
    margin: 0
    color: #78909c
    font-size: 14px

.pick-toggle
  min-height: 44px
  padding: 4px 18px
  border-radius: 999px
  border: 1px solid #0288d1
  background: #e1f5fe
  color: #01579b
  cursor: pointer
  font-weight: 600
  &.active
    background: #0288d1
    color: #fff

.pick-bar
  display: flex
  align-items: center
  justify-content: space-between
  background: #e1f5fe
  border-radius: 10px
  padding: 8px 14px
  span
    color: #01579b
    font-size: 14px

.pick-go
  min-height: 40px
  padding: 2px 16px
  border: none
  border-radius: 8px
  background: #0288d1
  color: #fff
  cursor: pointer
  &:disabled
    opacity: 0.5

.quick-pairs
  h2
    font-size: 16px
    margin: 0 0 8px

.quick-row
  display: flex
  flex-wrap: wrap
  gap: 8px

.quick-btn
  min-height: 40px
  padding: 2px 14px
  border-radius: 999px
  border: 1px solid #b39ddb
  background: #ede7f6
  color: #4527a0
  cursor: pointer

.lib-layer h2
  font-size: 17px
  margin: 0 0 12px

.layer-empty
  color: #b0bec5
  font-size: 13px

.lib-grid
  display: grid
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr))
  gap: 14px

.lib-cell
  display: flex
  flex-direction: column
  gap: 6px

.pick-check
  align-self: flex-end
  min-height: 36px
  padding: 2px 14px
  border-radius: 999px
  border: 1px solid #90a4ae
  background: #fff
  cursor: pointer
  font-size: 13px
  &.checked
    border-color: #0288d1
    background: #e1f5fe
    color: #01579b
    font-weight: 600
</style>
