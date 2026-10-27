<script setup lang="ts">
/**
 * P02 搜索（FR-301–304）：q 写入 URL，可刷新可后退；
 * 无结果时相近已开放关 + 「希望增加」（WishDialog 携 searchQuery）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { QBtn } from 'quasar'
import { contentApi, type LevelSummary } from '@/api'
import LevelCard from '@/components/LevelCard.vue'
import SearchBox from '@/components/SearchBox.vue'
import WishDialog from '@/components/WishDialog.vue'
import PageState from '@/components/PageState.vue'

const route = useRoute()
const router = useRouter()

const q = computed(() => (typeof route.query.q === 'string' ? route.query.q : ''))
const queryInput = ref(q.value)
const results = ref<LevelSummary[]>([])
const nearLevels = ref<LevelSummary[]>([])
const loading = ref(false)
const error = ref<unknown>(null)
const wishOpen = ref(false)

watch(q, (value) => {
  queryInput.value = value
})

async function runSearch(term: string) {
  if (!term) return
  loading.value = true
  error.value = null
  try {
    const res = await contentApi.search(term)
    results.value = res.data.results
    nearLevels.value = res.data.near ?? []
  } catch (err) {
    error.value = err
    results.value = []
    nearLevels.value = []
  } finally {
    loading.value = false
  }
}

watch(
  q,
  (value) => {
    if (value) void runSearch(value)
  },
  { immediate: true },
)

onMounted(() => {
  if (!q.value) void router.replace('/search')
})

function onSearch(term: string) {
  void router.push({ path: '/search', query: { q: term } })
}
</script>

<template>
  <div class="search-page">
    <h1>搜一个音</h1>
    <SearchBox :model-value="queryInput" @search="onSearch" />

    <PageState v-if="loading" state="loading" />
    <PageState v-else-if="error" state="error" :error="error" @retry="runSearch(q)" />

    <template v-else-if="q">
      <section v-if="results.length > 0" class="result-section" aria-label="搜索结果">
        <h2>找到 {{ results.length }} 关</h2>
        <div class="result-grid">
          <LevelCard v-for="level in results" :key="level.id" :level="level" />
        </div>
      </section>

      <section v-else class="result-section" aria-label="无结果">
        <h2>没有找到「{{ q }}」</h2>
        <p class="no-hit-hint">可能是这个音还没有开放，或者名字不太一样。可以试试相近的关卡：</p>
        <div v-if="nearLevels.length > 0" class="result-grid">
          <LevelCard v-for="level in nearLevels" :key="level.id" :level="level" />
        </div>
        <p v-else class="no-suggestion">暂时没有相近的已开放关卡。</p>
        <QBtn
          outline
          no-caps
          color="primary"
          class="wish-open"
          :label="`希望增加「${q}」`"
          @click="wishOpen = true"
        />
      </section>
    </template>
    <p v-else class="empty-hint">输入拼音开始搜索。</p>

    <WishDialog :open="wishOpen" :search-query="q" @close="wishOpen = false" />
  </div>
</template>

<style scoped lang="sass">
.search-page
  display: flex
  flex-direction: column
  gap: 20px

  h1
    font-size: 24px
    margin: 0

.result-section h2
  font-size: 17px
  margin: 0 0 12px

.result-grid
  display: grid
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr))
  gap: 14px

.no-hit-hint, .no-suggestion, .empty-hint
  color: #78909c
  font-size: 14px

.wish-open
  margin-top: 14px
</style>
