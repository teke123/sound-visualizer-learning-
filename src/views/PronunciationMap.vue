<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUnitsStore } from '@/stores/units'
import { useSpeechDemo } from '@/composables/useSpeechDemo'
import { buildMapNodes, LAYER_LABELS, LAYER_ORDER, type MapNode, type MapLayer } from '@/data/mapNodes'
import { PLACE_FILTERS, METHOD_FILTERS } from '@/data/unitSearchMeta'
import PageFeedback from '@/components/PageFeedback.vue'

const router = useRouter()
const unitsStore = useUnitsStore()
const speech = useSpeechDemo()

const selectedNode = ref<MapNode | null>(null)
const drawerOpen = computed({
  get: () => selectedNode.value !== null,
  set: (open: boolean) => { if (!open) selectedNode.value = null },
})
const activeLayer = ref<MapLayer | 'all'>('all')
const filterPlace = ref('')
const filterMethod = ref('')
const filterAspiration = ref('')
const filterNasal = ref('')
const filterTone = ref('')
const proExpanded = ref<string[]>([])

onMounted(() => unitsStore.fetchPublished())

const allNodes = computed(() => buildMapNodes(unitsStore.coreUnits))

const filteredNodes = computed(() => {
  return allNodes.value.filter(n => {
    if (activeLayer.value !== 'all' && n.layer !== activeLayer.value) return false
    if (filterPlace.value && !n.meta.place.includes(filterPlace.value)) return false
    if (filterMethod.value && !n.meta.method.includes(filterMethod.value)) return false
    if (filterAspiration.value && n.meta.aspiration !== filterAspiration.value) return false
    if (filterNasal.value === '鼻音' && !n.meta.nasal) return false
    if (filterNasal.value === '口音' && n.meta.nasal) return false
    if (filterTone.value && n.meta.tone !== filterTone.value && n.layer !== 'tone') return false
    return true
  })
})

const nodesByLayer = computed(() => {
  const map = new Map<MapLayer, MapNode[]>()
  for (const layer of LAYER_ORDER) map.set(layer, [])
  for (const n of filteredNodes.value) {
    map.get(n.layer)?.push(n)
  }
  return map
})

/** 层级配色：颜色本身就承担"这是第几层"的信息 */
const LAYER_COLORS: Record<MapLayer, { fill: string; stroke: string }> = {
  initial: { fill: '#ecf5ff', stroke: '#409eff' },
  final: { fill: '#f0f9eb', stroke: '#67c23a' },
  tone: { fill: '#fdf6ec', stroke: '#e6a23c' },
  syllable: { fill: '#fef0f0', stroke: '#f56c6c' },
  character: { fill: '#f4f4f5', stroke: '#909399' },
}

/** 布局表：每层自己的位置（不再是等距横排） */
const LAYER_POS: Record<MapLayer, { cx: number; cy: number }> = {
  initial: { cx: 80, cy: 60 },     // 声母
  final: { cx: 80, cy: 170 },      // 韵母
  syllable: { cx: 340, cy: 115 },  // 音节 ← 正好在声母/韵母的正中间
  tone: { cx: 340, cy: 250 },      // 声调
  character: { cx: 600, cy: 115 }, // 汉字
}

/** 关系配对：这才是"节点关系"本身 */
const FLOW_LINKS: Array<[MapLayer, MapLayer]> = [
  ['initial', 'syllable'],   // 声母 → 音节
  ['final', 'syllable'],     // 韵母 → 音节
  ['syllable', 'character'], // 音节 → 汉字
  ['tone', 'character'],     // 声调 → 汉字
]

/** 布局参数：全部抽成命名常量，因为它们要在多处复用 */
const NODE_R = 44

// layerFlow：直接是数组，不是 computed
const layerFlow = LAYER_ORDER.map(layer => ({
  layer,
  label: LAYER_LABELS[layer],
  cx: LAYER_POS[layer].cx,
  cy: LAYER_POS[layer].cy,
  color: LAYER_COLORS[layer],
}))

// flowEdges：直接算出来，循环提到顶层
const flowEdges: Array<{ key: string; x1: number; y1: number; x2: number; y2: number }> = []
for (const [fromLayer, toLayer] of FLOW_LINKS) {
  const from = layerFlow.find(n => n.layer === fromLayer)
  const to = layerFlow.find(n => n.layer === toLayer)
  if (!from || !to) continue

  const dx = to.cx - from.cx
  const dy = to.cy - from.cy
  const d = Math.hypot(dx, dy)
  if (d === 0) continue

  const ux = dx / d
  const uy = dy / d

  flowEdges.push({
    key: `${fromLayer}->${toLayer}`,
    x1: from.cx + ux * NODE_R,
    y1: from.cy + uy * NODE_R,
    x2: to.cx - ux * NODE_R,
    y2: to.cy - uy * NODE_R,
  })
}

const similarNodes = computed(() => {
  if (!selectedNode.value) return []
  return selectedNode.value.meta.similar
    .map(id => allNodes.value.find(n => n.id === id))
    .filter(Boolean) as MapNode[]
})

function selectNode(node: MapNode) {
  selectedNode.value = node
  proExpanded.value = []
}

function clearFilters() {
  filterPlace.value = ''
  filterMethod.value = ''
  filterAspiration.value = ''
  filterNasal.value = ''
  filterTone.value = ''
  activeLayer.value = 'all'
}

async function playDemo(char: string) {
  const text = char.split('/')[0] || char
  await speech.speak(text, 'normal')
}
</script>

<template>
  <div class="pronunciation-map">
    <header class="map-header">
      <h3>发音地图</h3>
      <p>看清声母、韵母、声调、音节与汉字之间的关系；点击节点查看详情并进入学习。</p>
    </header>

    <!-- MAP-01 总览：层级筛选 + 汇聚关系图 -->
    <section class="overview card">
      <h4>发音层级关系</h4>
      <div class="flow-chain">
        <button
          v-for="layer in LAYER_ORDER"
          :key="layer"
          class="flow-node"
          :class="{ active: activeLayer === layer }"
          @click="activeLayer = activeLayer === layer ? 'all' : layer"
        >
          <span class="flow-label">{{ LAYER_LABELS[layer] }}</span>
          <span class="flow-count">{{ nodesByLayer.get(layer)?.length || 0 }} 项</span>
        </button>
      </div>
      <p class="flow-hint">声母与韵母组合成音节，叠加声调后对应汉字；「妈」单元覆盖完整闭环。</p>
      <svg
        class="demo-svg"
        viewBox="0 0 680 310"
        role="img"
        aria-label="发音层级关系图：声母与韵母汇聚成音节，音节与声调汇聚成汉字"
      >
        <line
          v-for="n in flowEdges"
          :key="`line-${n.key}`"
          :x1="n.x1"
          :y1="n.y1"
          :x2="n.x2"
          :y2="n.y2"
          stroke="#c0c4cc"
          stroke-width="2"
        />

        <template v-for="n in layerFlow" :key="n.layer">
          <circle
            :cx="n.cx"
            :cy="n.cy"
            :r="NODE_R"
            :fill="n.color.fill"
            :stroke="n.color.stroke"
            stroke-width="2"
          />
          <text
            :x="n.cx"
            :y="n.cy + 5"
            text-anchor="middle"
            font-size="14px"
            fill="#303133"
          >{{ n.label }}</text>
        </template>
      </svg>
    </section>

    <!-- MAP-02 分类筛选 -->
    <section class="filters card">
      <h4>分类筛选</h4>
      <div class="filter-row">
        <el-select v-model="filterPlace" placeholder="发音部位" clearable style="width: 140px">
          <el-option v-for="p in PLACE_FILTERS" :key="p" :label="p" :value="p" />
        </el-select>
        <el-select v-model="filterMethod" placeholder="发音方法" clearable style="width: 140px">
          <el-option v-for="m in METHOD_FILTERS" :key="m" :label="m" :value="m" />
        </el-select>
        <el-select v-model="filterAspiration" placeholder="送气/不送气" clearable style="width: 140px">
          <el-option label="送气" value="送气" />
          <el-option label="不送气" value="不送气" />
        </el-select>
        <el-select v-model="filterNasal" placeholder="口音/鼻音" clearable style="width: 130px">
          <el-option label="鼻音" value="鼻音" />
          <el-option label="口音" value="口音" />
        </el-select>
        <el-select v-model="filterTone" placeholder="声调" clearable style="width: 120px">
          <el-option label="四声" value="四声" />
          <el-option label="阴平" value="阴平" />
        </el-select>
        <el-button @click="clearFilters">重置</el-button>
      </div>
    </section>

    <!-- 节点网格 -->
    <section class="nodes-section">
      <div v-for="layer in LAYER_ORDER" :key="layer" v-show="activeLayer === 'all' || activeLayer === layer" class="layer-block">
        <h4 v-if="activeLayer === 'all'">{{ LAYER_LABELS[layer] }}</h4>
        <div class="node-grid">
          <el-card
            v-for="node in nodesByLayer.get(layer)"
            :key="node.id"
            shadow="hover"
            class="map-node"
            :class="{ selected: selectedNode?.id === node.id }"
            @click="selectNode(node)"
          >
            <div class="char">{{ node.character }}</div>
            <div class="py">{{ node.pinyin }}</div>
            <div class="ipa">{{ node.meta.ipa }}</div>
          </el-card>
        </div>
      </div>
      <el-empty v-if="!filteredNodes.length" description="没有符合筛选条件的节点，请调整筛选或重置。" />
    </section>

    <!-- MAP-03 节点详情 -->
    <el-drawer v-model="drawerOpen" :title="selectedNode?.character || '发音详情'" size="420px" direction="rtl">
      <template v-if="selectedNode">
        <div class="detail">
          <p class="detail-conclusion">{{ selectedNode.conclusion }}</p>
          <dl class="detail-meta">
            <dt>拼音</dt><dd>{{ selectedNode.pinyin }}</dd>
            <dt>IPA</dt><dd>{{ selectedNode.meta.ipa }}</dd>
            <dt>部位</dt><dd>{{ selectedNode.meta.place.join('、') }}</dd>
            <dt>方法</dt><dd>{{ selectedNode.meta.method.join('、') }}</dd>
          </dl>
          <div class="detail-actions">
            <el-button type="primary" @click="playDemo(selectedNode.character)">播放示范</el-button>
            <el-button @click="router.push(`/learn/${selectedNode.unitId}`)">进入单元</el-button>
          </div>
          <p class="tts-note">{{ speech.disclaimer }}</p>

          <!-- MAP-04 相近音比较 -->
          <div v-if="similarNodes.length" class="similar-block">
            <h4>相近音比较</h4>
            <div class="similar-list">
              <el-card v-for="s in similarNodes" :key="s.id" shadow="never" class="similar-card">
                <strong>{{ s.character }}</strong> {{ s.pinyin }}
                <p>{{ s.conclusion }}</p>
                <el-button size="small" @click="router.push(`/learn/${s.unitId}`)">并排学习</el-button>
              </el-card>
            </div>
          </div>

          <!-- MAP-05 专业展开 -->
          <el-collapse v-model="proExpanded" class="pro-collapse">
            <el-collapse-item title="专业术语（点击展开）" name="pro">
              <ul>
                <li v-for="t in selectedNode.meta.professional" :key="t.term">
                  <strong>{{ t.term }}</strong>：{{ t.explain }}
                </li>
              </ul>
              <p class="boundary">专业内容仅供学习参考，不构成医学诊断依据。</p>
            </el-collapse-item>
          </el-collapse>
        </div>
      </template>
    </el-drawer>

    <PageFeedback page="map" type="learning" />
  </div>
</template>

<style scoped>
.pronunciation-map { max-width: 1000px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.map-header h3 { margin: 0; font-size: 20px; }
.map-header p { margin: 8px 0 0; color: #909399; font-size: 14px; }
.card { background: #fff; border-radius: 12px; padding: 16px 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.overview h4, .filters h4, .layer-block h4 { margin: 0 0 12px; font-size: 15px; color: #303133; }
.flow-chain { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.flow-node { border: 1px solid #dcdfe6; background: #f5f7fa; border-radius: 8px; padding: 10px 14px; cursor: pointer; text-align: center; min-width: 72px; }
.flow-node.active { border-color: #409eff; background: #ecf5ff; }
.flow-label { display: block; font-weight: 600; font-size: 14px; }
.flow-count { font-size: 12px; color: #909399; }
.flow-hint { margin: 12px 0 0; font-size: 13px; color: #909399; }
.filter-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.node-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; margin-bottom: 16px; }
.map-node { cursor: pointer; text-align: center; }
.map-node.selected { border-color: #409eff; }
.char { font-size: 28px; font-weight: 700; }
.py { color: #409eff; font-size: 13px; margin: 4px 0; }
.ipa { font-size: 11px; color: #909399; font-family: serif; }
.detail-conclusion { font-size: 15px; line-height: 1.6; margin: 0 0 16px; }
.detail-meta { display: grid; grid-template-columns: 64px 1fr; gap: 6px 12px; font-size: 14px; margin: 0 0 16px; }
.detail-meta dt { color: #909399; }
.detail-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.tts-note { font-size: 12px; color: #909399; }
.similar-block { margin-top: 20px; }
.demo-svg { width: 100%; height: auto; display: block; margin-top: 16px; }
.similar-block h4 { margin: 0 0 10px; font-size: 14px; }
.similar-list { display: flex; flex-direction: column; gap: 8px; }
.similar-card p { font-size: 13px; color: #606266; margin: 6px 0; }
.pro-collapse { margin-top: 16px; }
.boundary { font-size: 12px; color: #909399; margin-top: 8px; }
@media (max-width: 768px) {
  .flow-chain { justify-content: center; }
  .filter-row .el-select { width: 100% !important; }
}
</style>
