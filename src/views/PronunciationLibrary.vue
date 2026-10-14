<script setup lang="ts">
// 发音库（P06，FR-701~703）：按单韵母 / 声母 / 拼读分层，只索引当前已发布关；
// 卡片含名称、拼音、代表汉字（若有）、示范播放、进入关卡；支持选择两个已发布
// 相近关比较示范（比较规则与 P03 / P05 相同）。
// 以下为占位状态与动作（不包含任何假实现），重构时按意图恢复。
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useLevelsStore, type LevelAvailability } from '@/stores/levels'
import { usePageCopy } from '@/composables/usePageCopy'
import PageState from '@/components/PageState.vue'

const router = useRouter()
const levelsStore = useLevelsStore()
const { copy } = usePageCopy('P06')

const searchQuery = ref('')
const groupFilter = ref('all')

const AVAILABILITY_TEXT: Record<LevelAvailability, string> = {
  open: '可练可测',
  learn_only: '只学不测',
  unopened: '未发布',
}

const filterOptions = [
  { key: 'all', label: '全部' },
  { key: 'vowel', label: '单韵母' },
  { key: 'initial', label: '声母' },
  { key: 'syllable', label: '拼读' },
]

const visibleGroups = computed(() => levelsStore.levelGroups)

const gridState = computed<'loading' | 'error' | 'empty' | null>(() => {
  // TODO(重构): 接 store 的 loading；当前仅能判错误与空
  if (levelsStore.error) return 'error'
  if (!levelsStore.levels.length) return 'empty'
  return null
})
const emptyDetail = computed(() =>
  levelsStore.error ? levelsStore.error : '还没有已发布的关卡；CMS 发布后会出现在这里（FR-701）。',
)

function reloadLevels(): void { levelsStore.fetchLevels(true) }

/** 已发布相近关比较（FR-703）：最多选两个 */
const compareIds = ref<string[]>([])
const comparePair = computed(() =>
  compareIds.value
    .map(code => levelsStore.levels.find(l => l.code === code))
    .filter((l): l is NonNullable<typeof l> => !!l),
)
function toggleCompare(code: string, ev: Event): void {
  ev.stopPropagation()
  const idx = compareIds.value.indexOf(code)
  if (idx >= 0) compareIds.value.splice(idx, 1)
  else if (compareIds.value.length < 2) compareIds.value.push(code)
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
        </div>
      </div>
      <p class="hint">关键差异请进入各关卡听示范与检测对比（FR-703）。</p>
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
          </div>

          <div class="meta">
            <span class="code">{{ l.code }}</span>
            <span class="target">{{ l.target }}</span>
          </div>

          <!-- 重构时恢复：示范播放（FR-702） -->

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
