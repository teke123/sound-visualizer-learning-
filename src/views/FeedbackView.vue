<script setup lang="ts">
// 结果页（P09，FR-1001~1010）：录音质量先行（不合格即「本次不能评」+
// 重录指引，不显示分数）；合格时展示——按个人音域换算的曲线对比（FR-1005/1006）、
// 分数（总分/声韵分/调型分，仅本关已开放维度，FR-1002/1003/1010）、现象（FR-1004）、
// 规则引擎四步反馈（FR-1007）、可靠性档（FR-1008）、立即行动与边界句（FR-1009）。
// 进阶可视化板块保留：音素级分析、3D 发音动画、声谱图 / 共振峰 / 能量图，
// 数据来自声学 / 诊断契约（audioAnalysis），随新契约定稿接线。
// 以下为占位状态与动作（不包含任何假实现），重构时按意图恢复。
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePageCopy } from '@/composables/usePageCopy'
import PageState from '@/components/PageState.vue'
import PageFeedback from '@/components/PageFeedback.vue'

const route = useRoute()
const router = useRouter()
const { copy } = usePageCopy('P09')

const unitId = computed(() => (route.params.id as string) || '')

/** TODO(重构): 检测结果对象（SRS 07 章稳定结构：质量/分数/现象/四步/可靠性/版本号） */
type AssessResult = {
  evaluable: boolean
  score: number
  initialScore?: number | null
  toneScore?: number | null
  scoreExplain?: string
  headline?: string
  reliability: 'reliable' | 'reference_only' | 'not_available'
  reliabilityNote?: string
  quality?: { summary?: string; items?: Array<{ key: string; label: string; status: string; message: string }> }
  curve?: unknown
  /** 进阶可视化：声学 / 诊断契约随新契约定稿后填充 */
  audioAnalysis?: {
    phonemes?: Array<{ phoneme: string; expected: string; detected: string; score: number; feedback?: string }>
    recognizedText?: string
    detectedTone?: number | string
  }
  phenomena?: Array<{ text: string }>
  fourSteps?: Array<{ phenomenon: string; link: string; hint: string; practice: string }>
  boundary?: { statement: string }
}
const result = ref<AssessResult | null>(null)

/** 刷新 / 直开本页时从该关最近一条档案记录恢复（无结果时不留空白页） */
const restoreState = ref<'idle' | 'loading' | 'error' | 'done'>('idle')
const restoreError = ref('')
const lastRecord = ref<{
  createdAt: string; character?: string; pinyin?: string; score: number; reliabilityNote?: string
} | null>(null)
const isPlaying = ref(false)

/** TODO(重构): 会话有效 + 服务端同意记录有效时才显示保存入口（NFR-15） */
const canArchive = computed(() => false)

/* 进阶可视化容器：曲线对比（FR-1005）、3D 构形动画、声谱图 / 共振峰 / 能量 */
const toneChartRef = ref<HTMLDivElement | null>(null)
const threeContainerRef = ref<HTMLDivElement | null>(null)
const spectrogramRef = ref<HTMLCanvasElement | null>(null)
const formantChartRef = ref<HTMLDivElement | null>(null)
const energyChartRef = ref<HTMLDivElement | null>(null)

function scoreColorOf(score: number) {
  return score >= 80 ? '#67c23a' : score >= 60 ? '#e6a23c' : '#f56c6c'
}
const lastScoreColor = computed(() => scoreColorOf(lastRecord.value?.score ?? 0))
const scoreColor = computed(() => scoreColorOf(result.value?.score ?? 0))

function restoreLastRecord(): void { /* TODO(重构): 从学习记录接口恢复该关最近结果 */ }
function playLastRecord(): void { /* TODO(重构): 按记录 id 拉录音流并播放 */ }
function playDemo(): void { /* TODO(重构): 播本关示范（FR-1009 立即行动） */ }
</script>

<template>
  <div class="feedback-view">
    <!-- 没有内存结果时的恢复流程：分析结果只保存在内存里，刷新页面 / 直接打开本页 /
         上一次分析失败都会走到这里。三种情况分别是「请求中」「该关无记录」「接口失败」，
         绝不留空白页（这是「点了分析没反馈」的真实原因）。文案统一走 P09 文案位。 -->
    <PageState
      v-if="!result && (restoreState === 'idle' || restoreState === 'loading')"
      state="loading"
      :copy="copy"
      class="card-block"
    />

    <PageState
      v-else-if="!result && restoreState === 'error'"
      state="error"
      :copy="copy"
      :detail="restoreError"
      class="card-block"
      @action="restoreLastRecord"
    />

    <!-- 有记录：渲染上次练习结果（分数 + 文字反馈，曲线无法恢复） -->
    <div v-else-if="!result && restoreState === 'done' && lastRecord" class="card-block last-result">
      <div class="last-result-head">
        <h3>上次练习结果</h3>
        <span class="last-result-time">{{ new Date(lastRecord.createdAt).toLocaleString() }}</span>
      </div>
      <p class="last-result-note">{{ copy.subtitle }}</p>

      <div class="last-result-main">
        <div class="last-result-word">
          <span class="last-char">{{ lastRecord.character || unitId }}</span>
          <span v-if="lastRecord.pinyin" class="last-pinyin">{{ lastRecord.pinyin }}</span>
        </div>
        <div class="last-result-score">
          <span class="last-score-number" :style="{ color: lastScoreColor }">{{ Math.round(lastRecord.score) }}</span>
          <span class="last-score-label">总分</span>
        </div>
      </div>

      <p v-if="lastRecord.reliabilityNote" class="last-result-feedback">{{ lastRecord.reliabilityNote }}</p>

      <div class="last-result-actions">
        <el-button type="primary" :loading="isPlaying" @click="playLastRecord">播放上次录音</el-button>
        <el-button @click="router.push(`/learn/${unitId}`)">回关卡重新录音</el-button>
        <el-button @click="router.push('/archive')">看我的档案</el-button>
      </div>
    </div>

    <!-- 没有任何该关记录（以及其它兜底情况）：给出回关卡重录的入口 -->
    <div v-else-if="!result" class="card-block no-result">
      <PageState state="empty" :copy="copy" @action="router.push(`/learn/${unitId}`)" />
      <div class="no-result-actions">
        <el-button @click="router.push('/test')">去检测中心</el-button>
        <el-button @click="router.push('/learn')">看全部关卡</el-button>
      </div>
    </div>

    <!-- 录音质量先行：不能评就停在这里，不显示分数（FR-1001/FR-1301） -->
    <div v-if="result" class="result-meta card-block">
      <el-alert
        v-if="!result.evaluable"
        type="warning"
        :title="result.quality?.summary || '本次不能评'"
        description="录音质量或朗读要求未达标。请按提示调整环境与朗读方式后重录；这不代表你发音不好。"
        show-icon
        :closable="false"
      />
      <div v-if="!result.evaluable" class="unevaluable-actions">
        <el-button type="danger" @click="router.push(`/learn/${unitId}`)">返回关卡重录</el-button>
        <el-button @click="router.push('/test')">在检测中心重录</el-button>
      </div>

      <template v-else>
        <p class="headline-label">本次录音结论</p>
        <h2 class="headline">{{ result.headline || result.phenomena?.[0]?.text || '分析完成' }}</h2>
        <el-tag :type="result.reliability === 'reliable' ? 'success' : result.reliability === 'reference_only' ? 'warning' : 'info'">
          {{ { reliable: '可靠', reference_only: '仅供参考', not_available: '暂不评价' }[result.reliability] }}
        </el-tag>
        <p class="reliability-note">{{ result.reliabilityNote }}</p>
      </template>

      <div v-if="result.quality?.items?.length" class="quality-list">
        <h4>录音质量（与分数分开显示）</h4>
        <div v-for="item in result.quality.items" :key="item.key" class="quality-item" :class="item.status">
          <strong>{{ item.label }}</strong> — {{ item.message }}
        </div>
      </div>

      <el-alert v-if="result.boundary?.statement" type="info" :title="result.boundary.statement" show-icon :closable="false" class="boundary" />
    </div>

    <!-- 曲线对比（FR-1005/1006）+ 3D 构形动画 -->
    <div v-if="result?.evaluable" class="analysis-row">
      <div class="chart-card">
        <h4>曲线对比 <small>我的曲线 vs 标准曲线，已按你的音域换算</small></h4>
        <div ref="toneChartRef" class="chart-container"></div>
        <!-- 重构时恢复：ECharts 折线（静音段断线），我的曲线 / 标准曲线叠加 -->
      </div>
      <div class="three-card">
        <h4>3D 发音动画 <small>（构形剖面示意 · 拖拽旋转 · 滚轮缩放）</small></h4>
        <div ref="threeContainerRef" class="three-container"></div>
      </div>
    </div>

    <!-- 音素级分析（声学 / 诊断契约：目标音素 vs 识别结果逐项比对） -->
    <div v-if="result?.evaluable && result?.audioAnalysis?.phonemes?.length" class="phoneme-section">
      <h3>音素级分析 <small>逐个音素看目标与实际的差别</small></h3>
      <div class="phoneme-list">
        <div
          v-for="(p, idx) in result!.audioAnalysis!.phonemes"
          :key="idx"
          class="phoneme-item"
          :class="p.score >= 80 ? 'good' : (p.score >= 60 ? 'warn' : 'bad')"
        >
          <div class="phoneme-name">{{ p.phoneme }}</div>
          <div class="phoneme-compare">
            <span class="expected">目标：{{ p.expected }}</span>
            <span class="arrow">→</span>
            <span class="detected">识别：{{ p.detected }}</span>
          </div>
          <div class="phoneme-score">
            <el-progress
              :percentage="Math.round(p.score)"
              :stroke-width="10"
              :color="p.score >= 80 ? '#67c23a' : (p.score >= 60 ? '#e6a23c' : '#f56c6c')"
            />
          </div>
          <p class="phoneme-feedback">{{ p.feedback }}</p>
        </div>
      </div>
      <div class="phoneme-summary" v-if="result?.audioAnalysis?.recognizedText">
        <span class="label">识别文本：</span>
        <span class="value">{{ result!.audioAnalysis!.recognizedText }}</span>
        <span class="label">识别声调：</span>
        <span class="value">第{{ result!.audioAnalysis!.detectedTone || '（依据F0判定）' }}声</span>
      </div>
    </div>

    <!-- 声谱图 + 共振峰 + 能量图（声学 / 诊断契约） -->
    <div v-if="result?.evaluable && result?.audioAnalysis" class="analysis-row three-col">
      <div class="chart-card">
        <h4>声谱图（语谱图）</h4>
        <canvas ref="spectrogramRef" class="spectrogram-canvas"></canvas>
        <p class="chart-desc">颜色越亮表示该频率在该时间点的能量越强</p>
      </div>
      <div class="chart-card">
        <h4>共振峰</h4>
        <div ref="formantChartRef" class="chart-container"></div>
      </div>
      <div class="chart-card">
        <h4>能量</h4>
        <div ref="energyChartRef" class="chart-container"></div>
      </div>
    </div>

    <!-- 分数（FR-1002/1003/1010：仅本关已开放维度；一句话可解释） -->
    <div v-if="result?.evaluable" class="score-section">
      <div class="score-ring">
        <el-progress type="circle" :percentage="Math.round(result?.score || 0)" :color="scoreColor" :width="140" :stroke-width="12">
          <template #default="{ percentage }">
            <div class="score-inner">
              <span class="score-number">{{ percentage }}</span>
              <span class="score-label">总分</span>
            </div>
          </template>
        </el-progress>
      </div>
      <div class="score-detail">
        <div v-if="result?.initialScore != null" class="score-item"><span>声韵分</span><el-progress :percentage="Math.round(result.initialScore)" color="#409eff" /></div>
        <div v-if="result?.toneScore != null" class="score-item"><span>调型分</span><el-progress :percentage="Math.round(result.toneScore)" color="#67c23a" /></div>
        <p class="score-explain">{{ result.scoreExplain }}</p>
      </div>
    </div>

    <!-- 现象（FR-1004：用本关允许的可观察差异描述，通俗话表述） -->
    <div v-if="result?.evaluable && result?.phenomena?.length" class="card-block">
      <h3>听出来的现象</h3>
      <ul class="phenomena-list">
        <li v-for="(p, idx) in result.phenomena" :key="idx">{{ p.text }}</li>
      </ul>
    </div>

    <!-- 规则引擎四步反馈（FR-1007：现象 → 可能相关环节 → 可感知提示 → 安全短练习） -->
    <div v-if="result?.evaluable && result?.fourSteps?.length" class="four-step card-block">
      <h3>练习建议（四步反馈）</h3>
      <div v-for="(item, idx) in result.fourSteps" :key="idx" class="step-item">
        <p><strong>① 现象</strong>{{ item.phenomenon }}</p>
        <p><strong>② 可能相关环节</strong>{{ item.link }}</p>
        <p><strong>③ 可感知提示</strong>{{ item.hint }}</p>
        <p><strong>④ 安全短练习</strong>{{ item.practice }}</p>
      </div>
    </div>

    <!-- 立即行动与边界句（FR-1009） -->
    <div v-if="result" class="action-bar">
      <el-button :icon="'VideoPlay'" size="large" @click="playDemo">播示范</el-button>
      <el-button :icon="'Refresh'" size="large" @click="router.push(`/learn/${unitId}`)">重录</el-button>
      <el-button v-if="canArchive" type="primary" size="large" @click="router.push('/archive')">看档案与保存</el-button>
    </div>

    <PageFeedback :page="`feedback/${unitId}`" :unit-id="unitId" type="result" />
  </div>
</template>

<style scoped>
.feedback-view { display: flex; flex-direction: column; gap: 20px; }
.no-result-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
/* 上次练习结果（刷新 / 直开后从学习记录恢复） */
.last-result-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.last-result-head h3 { margin: 0; font-size: 16px; color: #303133; }
.last-result-time { font-size: 12px; color: #909399; }
.last-result-note { margin: 8px 0 16px; font-size: 13px; color: #909399; }
.last-result-main { display: flex; align-items: center; gap: 40px; }
.last-result-word { display: flex; align-items: baseline; gap: 10px; }
.last-char { font-size: 40px; font-weight: 700; color: #303133; }
.last-pinyin { font-size: 16px; color: #4a7a9a; }
.last-result-score { display: flex; flex-direction: column; align-items: center; }
.last-score-number { font-size: 36px; font-weight: 700; }
.last-score-label { font-size: 12px; color: #909399; }
.last-result-feedback { margin: 16px 0 0; padding: 12px 16px; background: #f5f7fa; border-radius: 8px; font-size: 13px; color: #606266; }
.last-result-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
.card-block { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06); }
.card-block h3 { margin: 0 0 12px; }
.headline-label { font-size: 13px; color: #909399; margin: 0; }
.headline { margin: 8px 0 12px; font-size: 20px; color: #303133; }
.reliability-note { font-size: 13px; color: #606266; margin-top: 8px; }
.quality-list { margin-top: 16px; }
.quality-list h4 { margin: 0 0 8px; font-size: 14px; }
.quality-item { font-size: 13px; padding: 6px 0; }
.quality-item.fail { color: #f5666c; }
.four-step .step-item { padding: 12px; margin-bottom: 8px; border-radius: 8px; background: #f5f7fa; font-size: 13px; }
.four-step .step-item p { margin: 4px 0; }
.boundary { margin-top: 12px; }
.unevaluable-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 12px; }
.curve-block .curve-note { font-size: 13px; color: #909399; margin: 0; }
.analysis-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.analysis-row.three-col { grid-template-columns: 1fr 1fr 1fr; }
.chart-card h4, .three-card h4 { margin: 0 0 8px; font-size: 14px; color: #303133; }
.chart-card h4 small, .three-card h4 small { font-size: 11px; color: #909399; font-weight: normal; }
.chart-card, .three-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.chart-container { width: 100%; height: 300px; }
.three-card { position: relative; }
.three-container { position: relative; width: 100%; height: 300px; border-radius: 8px; overflow: hidden; }
.spectrogram-canvas { width: 100%; height: 200px; border-radius: 8px; background: #0a0a1a; }
.chart-desc { font-size: 11px; color: #909399; text-align: center; margin-top: 6px; }
.phoneme-section { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.phoneme-section h3 { margin: 0 0 16px; font-size: 16px; color: #303133; }
.phoneme-section h3 small { font-size: 12px; color: #909399; font-weight: normal; }
.phoneme-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.phoneme-item { border-radius: 8px; padding: 14px; border: 1px solid #e4e7ed; }
.phoneme-item.good { border-color: #b3e19d; background: #f0f9eb; }
.phoneme-item.warn { border-color: #f3d19e; background: #fdf6ec; }
.phoneme-item.bad { border-color: #fbc4c4; background: #fef0f0; }
.phoneme-name { font-weight: 700; color: #303133; margin-bottom: 8px; font-size: 14px; }
.phoneme-compare { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #606266; margin-bottom: 8px; }
.phoneme-compare .arrow { color: #c0c4cc; }
.phoneme-score { margin-bottom: 6px; }
.phoneme-feedback { margin: 0; font-size: 12px; color: #909399; }
.phoneme-summary { margin-top: 16px; padding: 12px 16px; background: #ecf5ff; border-radius: 8px; font-size: 13px; color: #303133; }
.phoneme-summary .label { color: #909399; margin-right: 4px; }
.phoneme-summary .value { font-weight: 500; margin-right: 20px; }
@media (max-width: 900px) { .analysis-row, .analysis-row.three-col { grid-template-columns: 1fr; } }
.phenomena-list { margin: 0; padding-left: 18px; font-size: 14px; color: #606266; line-height: 1.9; }
.score-section { background: white; border-radius: 12px; padding: 24px; display: flex; align-items: center; gap: 40px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.score-ring { flex-shrink: 0; }
.score-inner { text-align: center; }
.score-number { font-size: 36px; font-weight: 700; color: #303133; display: block; }
.score-label { font-size: 12px; color: #909399; }
.score-detail { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.score-item { display: flex; align-items: center; gap: 12px; }
.score-item span { width: 60px; font-size: 14px; color: #606266; }
.score-explain { font-size: 13px; color: #909399; margin: 4px 0 0; }
.action-bar { display: flex; justify-content: center; gap: 16px; padding: 16px 0; flex-wrap: wrap; }
</style>
