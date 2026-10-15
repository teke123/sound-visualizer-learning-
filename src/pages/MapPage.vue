<script setup lang="ts">
/** P03 发音地图（FR-401–404 / FD-13）：三层闯关定位 + 骨架 + 易混对 + ?compare= */
import { computed, onMounted } from 'vue'
import { useLevelsStore } from '@/stores/levels'
import { useProgressStore } from '@/stores/progress'
import { useComparePanel } from '@/features/compare'
import LayerMap from '@/components/LayerMap.vue'
import ConfusablePairList from '@/components/ConfusablePairList.vue'
import ComparePanel from '@/components/ComparePanel.vue'
import PageState from '@/components/PageState.vue'

const levelsStore = useLevelsStore()
const progressStore = useProgressStore()
const compare = useComparePanel()

onMounted(() => {
  if (!levelsStore.loaded) void levelsStore.refresh()
})

const compareOpen = computed(() => compare.pair.value !== null)

function openPair(pair: { a: string; b: string }) {
  void compare.open(pair.a, pair.b)
}
</script>

<template>
  <div class="map-page">
    <header class="map-head">
      <h1>发音地图</h1>
      <p>从单韵母到声母再到拼读，一关一关往前走；已点亮的关卡都能进去学。</p>
    </header>

    <PageState v-if="levelsStore.loading && !levelsStore.loaded" state="loading" />
    <PageState
      v-else-if="levelsStore.error && levelsStore.levels.length === 0"
      state="error"
      :error="levelsStore.error"
      @retry="levelsStore.refresh()"
    />
    <template v-else>
      <LayerMap
        :levels="levelsStore.levels"
        :skeletons="levelsStore.skeletons"
        :completed-ids="progressStore.completedIds"
      />
      <ConfusablePairList :pairs="levelsStore.confusablePairs" :levels-by-id="levelsStore.byId" @compare="openPair" />
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
.map-page
  display: flex
  flex-direction: column
  gap: 24px

.map-head
  h1
    margin: 0 0 4px
    font-size: 24px
  p
    margin: 0
    color: #78909c
    font-size: 14px
</style>
