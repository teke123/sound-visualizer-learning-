<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useLevelsStore, type LevelView } from '@/stores/levels'

const levelsStore = useLevelsStore()

/* ---------- 布局参数 ---------- */
const PER_ROW = 8      // 每行最多放几个节点
const NODE_R = 26      // 节点半径
const GAP_X = 76       // 横向间距（圆心到圆心）
const GAP_Y = 76       // 纵向行距
const PAD_X = 40       // 左右留白
const PAD_Y = 40       // 上下留白
const BAND_GAP = 56    // 层与层之间的额外间距

/* ---------- 布局：把 30 关算成带坐标的节点 ---------- */
const layout = computed(() => {
  const nodes: Array<LevelView & { cx: number; cy: number; row: number; col: number }> = []
  const bands: Array<{ key: string; label: string; count: number; y: number }> = []

  let cursorY = PAD_Y + NODE_R

  // D 的 store 已经按「单韵母 → 声母 → 拼读」分好组、且按 order 排好序
  for (const group of levelsStore.levelGroups) {
    const items = group.items

    // 层标题放在这一层第一个节点的上方
    bands.push({
      key: group.key,
      label: group.label,
      count: items.length,
      y: cursorY - NODE_R - 22,
    })

    items.forEach((lv, i) => {
      const row = Math.floor(i / PER_ROW)   // 第几行
      const col = i % PER_ROW               // 第几列
      nodes.push({
        ...lv,
        row,
        col,
        cx: PAD_X + NODE_R + col * GAP_X,
        cy: cursorY + row * GAP_Y,
      })
    })

    // 这一层占了几行 → 游标往下推
    const rows = Math.max(1, Math.ceil(items.length / PER_ROW))
    cursorY += rows * GAP_Y + BAND_GAP
  }

  return { nodes, bands }
})

onMounted(() => levelsStore.fetchLevels())
</script>

<template>
  <svg
    class="roadmap"
    viewBox="0 0 664 560"
    role="img"
    aria-label="发音闯关定位图：单韵母、声母、拼读三层，共 30 关"
  >
    <!-- ① 层标题 -->
    <g v-for="b in layout.bands" :key="b.key">
      <text :x="PAD_X" :y="b.y" class="band-label">{{ b.label }}</text>
      <text :x="PAD_X + 64" :y="b.y" class="band-count">{{ b.count }} 关</text>
    </g>

    <!-- ② 节点：一个关卡 = 圆 + 例字 + 关卡编号 -->
    <g v-for="n in layout.nodes" :key="n.code">
      <circle
        :cx="n.cx"
        :cy="n.cy"
        :r="NODE_R"
        :class="['node', `node--${n.availability}`]"
      />
      <text :x="n.cx" :y="n.cy - 2" text-anchor="middle" class="node-char">{{ n.char }}</text>
      <text :x="n.cx" :y="n.cy + 14" text-anchor="middle" class="node-code">{{ n.code }}</text>
    </g>
  </svg>
</template>

<style scoped>
.roadmap { width: 100%; height: auto; display: block; font-size: 14px; }

.roadmap .band-label { font-weight: 600; fill: #303133; }
.roadmap .band-count { font-weight: 400; fill: #909399; }

.roadmap .node { stroke-width: 2; }

/* ★ 三态：类名必须与 availability 的实际取值完全一致 */
.roadmap .node--open       { fill: #f0f9eb; stroke: #67c23a; }
.roadmap .node--learn_only { fill: #fdf6ec; stroke: #e6a23c; stroke-dasharray: 4 3; }
.roadmap .node--unopened   { fill: #f4f4f5; stroke: #dcdfe6; stroke-dasharray: 4 3; }

.roadmap .node-char { font-size: 18px; fill: #303133; }
.roadmap .node-code { font-size: 12px; fill: #909399; }
</style>
