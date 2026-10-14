<script setup lang="ts">
// 关卡数据与三态来自 levels store；易混关并排入口（FR-403）为固定清单，
// 仅显示双方都已发布的比较。专业说明默认折叠（FR-404）。
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useLevelsStore } from '@/stores/levels'
import { usePageCopy } from '@/composables/usePageCopy'
import LevelRoadmap from '@/components/LevelRoadmap.vue'
import PageState from '@/components/PageState.vue'
import PageFeedback from '@/components/PageFeedback.vue'

const router = useRouter()
const levelsStore = useLevelsStore()
const { copy } = usePageCopy('P03')

/** 易混关清单（FR-403 固定十对；仅显示双方都已发布的比较） */
const CONFUSABLE_PAIRS: Array<[string, string]> = [
  ['n', 'l'], ['b', 'p'], ['d', 't'], ['g', 'k'], ['j', 'q'],
  ['z', 'zh'], ['c', 'ch'], ['s', 'sh'], ['f', 'h'], ['u', 'ü'],
]

const publishedTargets = computed(() =>
  new Set(levelsStore.levels.filter(l => l.availability !== 'unopened').map(l => l.char)),
)

const visiblePairs = computed(() =>
  CONFUSABLE_PAIRS
    .map(([a, b]) => ({ a, b }))
    .filter(p => publishedTargets.value.has(p.a) && publishedTargets.value.has(p.b)),
)

const mapState = computed(() => {
  // TODO(重构): store 补 loading/error 状态后接入错误态；当前仅能判空
  if (!levelsStore.levels.length) return 'empty' as const
  return null
})

function openByTarget(target: string) {
  const hit = levelsStore.levels.find(l => l.char === target)
  if (hit) router.push(`/learn/${hit.code}`)
}
</script>

<template>
  <div class="map-view">
    <header class="map-header">
      <h3>发音地图</h3>
      <p>{{ copy.subtitle }}</p>
    </header>

    <!-- 加载 / 空态统一走 P03 文案位 -->
    <PageState :state="mapState" :copy="copy" @action="levelsStore.fetchLevels()" />

    <template v-if="!mapState">
      <!-- 三层闯关定位图（FR-401：单韵母 L01–L06 → 声母 L07–L29 → 拼读 L30；
           未发布或检测未开放显示「未开放」，已发布可点进，FR-402） -->
      <section class="roadmap-card card" @click="levelsStore.fetchLevels()">
        <LevelRoadmap />
        <p class="legend">
          <span class="dot dot--open" /> 可练可测
          <span class="dot dot--learn_only" /> 只学不测
          <span class="dot dot--unopened" /> 未开放
        </p>
      </section>

      <!-- 易混关并排入口（FR-403） -->
      <section class="confusable card">
        <h4>易混的音，并排来练</h4>
        <div v-if="visiblePairs.length" class="pair-list">
          <el-button v-for="p in visiblePairs" :key="`${p.a}-${p.b}`" size="large" class="pair-btn" @click="openByTarget(p.a)">
            <strong>{{ p.a }}</strong><span class="vs">vs</span><strong>{{ p.b }}</strong>
          </el-button>
        </div>
        <p v-else class="hint">双方都已发布的易混关出现后，这里可以并排进入比较。</p>
      </section>

      <!-- 专业说明默认折叠（FR-404：IPA、发音部位学术分类） -->
      <el-collapse class="pro-collapse">
        <el-collapse-item title="专业说明（IPA 与发音部位分类，点击展开）" name="pro">
          <p class="hint">专业内容与对应已发布关的说明，由内容服务提供（默认折叠，需要时再展开）。</p>
        </el-collapse-item>
      </el-collapse>
    </template>

    <PageFeedback page="map" type="learning" />
  </div>
</template>

<style scoped>
.map-view { max-width: 1000px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.map-header h3 { margin: 0; font-size: 20px; }
.map-header p { margin: 8px 0 0; color: #909399; font-size: 14px; }
.card { background: #fff; border-radius: 12px; padding: 16px 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.roadmap-card .legend { display: flex; align-items: center; gap: 8px; margin: 12px 0 0; font-size: 12px; color: #909399; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-left: 8px; }
.dot--open { background: #f0f9eb; border: 2px solid #67c23a; }
.dot--learn_only { background: #fdf6ec; border: 2px dashed #e6a23c; }
.dot--unopened { background: #f4f4f5; border: 2px dashed #dcdfe6; }
.confusable h4 { margin: 0 0 12px; font-size: 15px; color: #303133; }
.pair-list { display: flex; flex-wrap: wrap; gap: 10px; }
.pair-btn { display: inline-flex; align-items: baseline; gap: 8px; }
.pair-btn strong { font-size: 18px; }
.pair-btn .vs { font-size: 12px; color: #909399; }
.hint { font-size: 13px; color: #909399; margin: 0; }
.pro-collapse { background: #fff; border-radius: 12px; padding: 4px 16px; }
</style>
