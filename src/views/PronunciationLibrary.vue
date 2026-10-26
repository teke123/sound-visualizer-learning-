<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useLevelsStore, type LevelView } from '@/stores/levels'
import { useUserStore } from '@/stores/user'
import { favoritesApi } from '@/api'
import { usePageCopy } from '@/composables/usePageCopy'
import PageState from '@/components/PageState.vue'

const router = useRouter()
const levelsStore = useLevelsStore()
const userStore = useUserStore()

/** 儿童化文案位：P06（D 留位，G / I 定稿） */
const { copy } = usePageCopy('P06')

const searchQuery = ref('')
/** 分组筛选：'all' 或 LevelGroup（final / initial / syllable） */
const groupFilter = ref<string>('all')
const favorites = ref<string[]>([])
const compareIds = ref<string[]>([])

onMounted(async () => {
  await levelsStore.fetchLevels()
  try {
    const res = await favoritesApi.list(userStore.userId)
    favorites.value = res.data
  } catch { /* optional */ }
})

/** 搜索：匹配关卡编号 / 目标音 / 例字 / 拼音 */
function matches(l: LevelView): boolean {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return true
  return (
    l.code.toLowerCase().includes(q) ||
    l.target.toLowerCase().includes(q) ||
    l.char.includes(q) ||
    l.pinyin.toLowerCase().includes(q)
  )
}

/** 筛选标签：全部 + 三个分组（单韵母 / 声母 / 拼读） */
const filterOptions = computed(() => [
  { key: 'all', label: '全部' },
  ...levelsStore.levelGroups.map(g => ({ key: g.key as string, label: g.label })),
])

/** 按分组组织：'all' 出三节；选中某组只出那一节；搜索后为空的组整节隐去 */
const visibleGroups = computed(() =>
  levelsStore.levelGroups
    .filter(g => groupFilter.value === 'all' || g.key === groupFilter.value)
    .map(g => ({ key: g.key, label: g.label, items: g.items.filter(matches) }))
    .filter(g => g.items.length > 0)
)

const visibleCount = computed(() =>
  visibleGroups.value.reduce((n, g) => n + g.items.length, 0),
)

/** 可用状态 → 家长看得懂的说法 */
const AVAILABILITY_TEXT: Record<string, string> = {
  open: '可练可测',
  learn_only: '仅可学习',
  unopened: '未开放',
}

const comparePair = computed(
  () =>
    compareIds.value
      .map(code => levelsStore.levels.find(l => l.code === code))
      .filter(Boolean) as LevelView[],
)

/** 收藏 / 比较都以关卡编号（L01…L30）为准 —— 与 C 的 30 关建库口径一致 */
async function toggleFavorite(code: string, e: Event) {
  e.stopPropagation()
  const on = favorites.value.includes(code)
  try {
    if (on) {
      await favoritesApi.remove(userStore.userId, code)
      favorites.value = favorites.value.filter(x => x !== code)
    } else {
      await favoritesApi.add(userStore.userId, code)
      favorites.value = [...favorites.value, code]
    }
  } catch {
    ElMessage.error('收藏操作失败')
  }
}

function toggleCompare(code: string, e: Event) {
  e.stopPropagation()
  if (compareIds.value.includes(code)) {
    compareIds.value = compareIds.value.filter(x => x !== code)
  } else if (compareIds.value.length < 2) {
    compareIds.value = [...compareIds.value, code]
  } else {
    compareIds.value = [compareIds.value[1]!, code]
  }
}

/**
 * 网格区状态：loading → error → empty。
 * 后端不可用时必须走 error，否则空网格会被误判成「发音库就是空的」。
 */
const gridState = computed<'loading' | 'error' | 'empty' | null>(() => {
  if (levelsStore.loading) return 'loading'
  if (levelsStore.error) return 'error'
  if (visibleCount.value) return null
  return 'empty'
})

/** 空态说明：区分「全库为空」和「筛选 / 搜索后为空」 */
const emptyDetail = computed(() => {
  if (!levelsStore.levels.length) return '仍未有已发布的关卡。'
  const parts: string[] = []
  if (groupFilter.value !== 'all') {
    const g = levelsStore.levelGroups.find(x => x.key === groupFilter.value)
    if (g) parts.push(`分组「${g.label}」`)
  }
  if (searchQuery.value.trim()) parts.push(`搜索词「${searchQuery.value.trim()}」`)
  return `已发布的 ${levelsStore.levels.length} 个关卡里，没有符合${parts.join(' + ')}的条目。`
})

function reloadLevels() {
  levelsStore.fetchLevels(true)
}
</script>

<template>
  <div class="library-view">
    <div class="header">
      <div>
        <h2>发音库</h2>
        <!-- 页面主旨走文案位；不再用「首批 N 个已发布单元」这种后端没起就变 0 的计数 -->
        <p class="subtitle">{{ copy.subtitle }}</p>
      </div>
      <el-input
        v-model="searchQuery"
        placeholder="搜索关卡编号、目标音或例字..."
        prefix-icon="Search"
        clearable
        style="max-width: 280px"
      />
    </div>

    <!-- MAP-02 分类筛选：口径为 SRS 的三分组（单韵母 / 声母 / 拼读） -->
    <div class="filters">
      <el-tag
        v-for="g in filterOptions"
        :key="g.key"
        :type="groupFilter === g.key ? 'primary' : 'info'"
        effect="plain"
        style="cursor: pointer; margin-right: 8px"
        @click="groupFilter = g.key"
      >{{ g.label }}</el-tag>
    </div>

    <div v-if="comparePair.length === 2" class="compare-bar card">
      <h4>并排比较</h4>
      <div class="compare-row">
        <div v-for="l in comparePair" :key="l.code">
          <strong>{{ l.char }}</strong> {{ l.pinyin }}
          <p>{{ l.childHint }}</p>
        </div>
      </div>
      <p class="hint">关键差异请进入各关卡听示范与检测对比。</p>
    </div>

    <!-- 加载 / 错误 / 空态统一走文案位：后端没起时给 error + 原始错误信息，不让人误判成「发音库是空的」 -->
    <PageState
      :state="gridState"
      :copy="copy"
      :detail="gridState === 'error' ? (levelsStore.error || undefined) : (gridState === 'empty' ? emptyDetail : undefined)"
      @action="reloadLevels"
    />

    <section v-for="g in visibleGroups" :key="g.key" class="group-block">
      <h3 class="group-title">
        {{ g.label }}
        <span class="group-count">{{ g.items.length }} 关</span>
      </h3>

      <div class="grid">
        <el-card
          v-for="l in g.items"
          :key="l.code"
          shadow="hover"
          class="level-card"
          @click="router.push(`/learn/${l.code}`)"
        >
          <div class="top">
            <span class="char">{{ l.char }}</span>
            <el-button
              :icon="favorites.includes(l.code) ? 'StarFilled' : 'Star'"
              circle
              size="small"
              @click="toggleFavorite(l.code, $event)"
            />
          </div>

          <div class="meta">
            <span class="code">{{ l.code }}</span>
            <span class="target">{{ l.target }}</span>
          </div>

          <div class="status" :class="`status--${l.availability}`">
            {{ AVAILABILITY_TEXT[l.availability] }}
          </div>

          <el-button
            size="small"
            :type="compareIds.includes(l.code) ? 'primary' : 'default'"
            @click="toggleCompare(l.code, $event)"
          >{{ compareIds.includes(l.code) ? '已选比较' : '加入比较' }}</el-button>
        </el-card>
      </div>
    </section>
  </div>
</template>

<style scoped>
.library-view { max-width: 1000px; margin: 0 auto; }
.header { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.subtitle { color: #909399; font-size: 13px; margin: 4px 0 0; }
.filters { margin-bottom: 16px; }

.group-block { margin-bottom: 20px; }
.group-title { margin: 0 0 10px; font-size: 15px; color: #303133; }
.group-count { margin-left: 6px; font-size: 12px; font-weight: 400; color: #909399; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.level-card { cursor: pointer; }
.top { display: flex; justify-content: space-between; align-items: center; }
.char { font-size: 30px; font-weight: 700; }
.meta { display: flex; align-items: baseline; gap: 8px; margin: 4px 0 8px; }
.code { font-size: 12px; color: #909399; }
.target { font-size: 15px; color: #409eff; }

/* 三态：与 availability 的取值一一对应 */
.status { display: inline-block; font-size: 12px; border-radius: 4px; padding: 1px 8px; margin-bottom: 8px; }
.status--open { color: #67c23a; background: #f0f9eb; }
.status--learn_only { color: #e6a23c; background: #fdf6ec; }
.status--unopened { color: #909399; background: #f4f4f5; }

.card { background: #fff; padding: 16px; border-radius: 12px; margin-bottom: 16px; }
.compare-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.hint { font-size: 12px; color: #909399; }
@media (max-width: 600px) { .compare-row { grid-template-columns: 1fr; } }
</style>
