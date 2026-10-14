<script setup lang="ts">
// 关卡页（P05）：30 关总览与单关「学→录→评→存」闭环。统一结构
// （FR-601）：一句话结论、构形、示范、听辨与小测、3–5 步练习、误区；
// 检测开放才有录音入口（FR-609），与 P08 同任务同口径（FR-907）。
// 以下为占位状态与动作（不包含任何假实现），重构时按意图恢复。
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLevelsStore, type LevelView } from '@/stores/levels'
import { useRecordingStore } from '@/stores/recording'
import { usePageCopy } from '@/composables/usePageCopy'
import { TTS_DISCLAIMER } from '@/composables/useSpeechDemo'
import PageState from '@/components/PageState.vue'

const route = useRoute()
const router = useRouter()
const levelsStore = useLevelsStore()
const recordingStore = useRecordingStore()
const { copy } = usePageCopy('P05')

const routeId = computed(() => (route.params.id as string) || '')
const isListMode = computed(() => !routeId.value)

/** TODO(重构): level 视图 = 关卡身份 + CMS 内容（结论/步骤/误区）+ availability */
type LevelCard = LevelView & {
  target?: string
  pinyin?: string
  groupLabel?: string
  detectionOpen?: boolean
  unit?: {
    pinyin?: string; character?: string; conclusion?: string; description?: string; detail?: string
    steps?: any[]; mistakes?: any[]
  }
}
const level = ref<LevelCard | null>(null)
const groups = computed(() => levelsStore.levelGroups as Array<{ key: string; label: string; items: LevelCard[] }>)
const counts = computed(() => {
  const all = levelsStore.levels
  return {
    opened: all.filter(l => l.availability === 'open').length,
    learnOnly: all.filter(l => l.availability === 'learn_only').length,
    unopened: all.filter(l => l.availability === 'unopened').length,
  }
})

const neighbors = computed<{ prev: LevelCard | null; next: LevelCard | null }>(() => ({ prev: null, next: null }))
const isDemoPlaying = ref(false)
const demoIsSynthetic = ref(false)
const ttsDisclaimer = TTS_DISCLAIMER
const canvasRef = ref<HTMLCanvasElement | null>(null)
/** TODO(重构): 该关检测任务（朗读提示词/示范）就绪后才有录音链路 */
const activeUnitId = computed(() => (level.value?.detectionOpen ? routeId.value : ''))

function availabilityTag(l: LevelView) {
  return l.availability === 'open' ? 'success' : l.availability === 'learn_only' ? 'warning' : 'info'
}
function availabilityText(l: LevelView) {
  return l.availability === 'open' ? '可练可测' : l.availability === 'learn_only' ? '只学不测' : '未开放'
}
function playDemo(): void { /* TODO(重构): 播正式示范音（CMS），缺失时合成示意并标注 */ }
function playSlow(): void { /* TODO(重构): 慢速示范 */ }
function startRecording(): void { /* TODO(重构): useAssessmentFlow 录音开始 */ }
function stopRecording(): void { recordingStore.stopRecording() }
function analyzeAndGoFeedback(): void { /* TODO(重构): 提交检测并跳 P09 */ }
function openLevel(code: string): void { router.push(`/learn/${code}`) }
</script>

<template>
  <!-- ============ 单关骨架 ============ -->
  <div v-if="!isListMode" class="level-view">
    <!-- 加载中（关卡身份可先渲染；内容状态等 CMS 返回后再判，避免闪一下「未开放」） -->
    <div v-if="levelsStore.loading && !levelsStore.loaded" class="state-card">
      <PageState state="loading" :copy="copy" />
    </div>

    <!-- 加载失败：说清是后端没连上，不让人误判成「这一关不存在」 -->
    <div v-else-if="levelsStore.error" class="state-card">
      <PageState
        state="error"
        :copy="copy"
        :detail="levelsStore.error"
        action-text="重新加载"
        @action="levelsStore.fetchLevels(true)"
      />
    </div>

    <!-- 不存在或未发布的关卡 id（兜底） -->
    <div v-else-if="!level" class="state-card">
      <PageState
        state="empty"
        :copy="copy"
        action-text="回到关卡列表"
        @action="router.push('/learn')"
      />
    </div>

    <template v-else>
      <!-- 关卡头部：身份（关卡清单）+ 状态（CMS） -->
      <div class="level-header card">
        <div class="level-badge">{{ level.code }}</div>
        <div class="level-identity">
          <div class="level-target">
            {{ level.target }}
            <span class="level-pinyin">{{ level.unit?.pinyin || level.pinyin }}</span>
          </div>
          <div class="level-sub">
            <el-tag size="small" effect="plain">{{ level.groupLabel }}</el-tag>
            <span class="level-char">例字：{{ level.unit?.character || level.char }}</span>
            <el-tag size="small" :type="availabilityTag(level)" effect="light">
              {{ availabilityText(level) }}
            </el-tag>
          </div>
        </div>
        <div class="level-actions">
          <el-button type="primary" :icon="'VideoPlay'" :loading="isDemoPlaying" @click="playDemo">
            听示范
          </el-button>
          <el-button :icon="'VideoPause'" @click="playSlow">慢速</el-button>
        </div>
      </div>

      <!-- 示范音来源如实标注：有正式授权示范音就说明，没有就明说这是合成示意，不冒充 -->
      <p v-if="demoIsSynthetic" class="disclaimer demo-source">{{ ttsDisclaimer }}</p>
      <p v-else class="disclaimer demo-source is-real">示范音来自 CMS 已发布的正式授权录音。</p>

      <!-- 未开放 / 只学不测：明确状态，不给检测入口、不给分数 -->
      <el-alert
        v-if="level.availability === 'unopened'"
        class="card"
        type="info"
        show-icon
        :closable="false"
        :title="copy.unopened"
        description="本关还未发布，按「未开放」处理：可以先练前面已开放的关卡。"
      />
      <el-alert
        v-else-if="level.availability === 'learn_only'"
        class="card"
        type="warning"
        show-icon
        :closable="false"
        title="这一关只学习、不检测"
        description="当前评分还不能稳定复现，所以不开放检测，也就不会给出分数。跟着示范读熟就好。"
      />

      <div class="level-body">
        <!-- 示范 / 练习：内容来自 CMS -->
        <div class="card block">
          <h3>跟着读</h3>
          <div v-if="level.unit">
            <p class="block-text">{{ level.unit.conclusion || level.unit.description }}</p>
            <p v-if="level.unit.detail" class="block-detail">{{ level.unit.detail }}</p>

            <div v-if="level.unit.steps?.length" class="step-list">
              <div v-for="(s, i) in level.unit.steps" :key="i" class="step-item">
                <span class="step-index">{{ i + 1 }}</span>
                <div>
                  <strong>{{ s.title || s.text || '练习一步' }}</strong>
                  <p v-if="s.text && s.title">{{ s.text }}</p>
                  <p v-if="s.duration" class="step-duration">约 {{ s.duration }}</p>
                </div>
              </div>
            </div>
            <p v-else class="block-text muted">{{ copy.empty }}</p>
          </div>
          <p v-else class="block-text muted">{{ copy.empty }}</p>
        </div>

        <!-- 检测：只有「已发布 + 已开放检测」才出现录音链路 -->
        <div class="card block">
          <h3>录音检测</h3>
          <template v-if="level.detectionOpen && activeUnitId">
            <div class="recording-controls">
              <el-button
                v-if="!recordingStore.isRecording"
                type="danger"
                :icon="'Microphone'"
                size="large"
                circle
                class="record-btn"
                @click="startRecording"
              />
              <el-button
                v-else
                type="info"
                :icon="'VideoPause'"
                size="large"
                circle
                class="record-btn recording"
                @click="stopRecording"
              />
              <span class="record-time">{{ recordingStore.formattedDuration }}</span>
            </div>
            <canvas ref="canvasRef" width="600" height="120" class="waveform-canvas"></canvas>
            <div v-if="recordingStore.hasRecording" class="record-actions">
              <el-button :icon="'Refresh'" @click="recordingStore.clearRecording">重录</el-button>
              <el-button
                type="primary"
                :icon="'DataAnalysis'"
                :loading="recordingStore.isAnalyzing"
                @click="analyzeAndGoFeedback"
              >
                {{ recordingStore.isAnalyzing ? '分析中…' : '看看读得怎么样' }}
              </el-button>
            </div>
            <!-- 分析失败必须说清原因，不能静默（后端没起、麦克风异常、网络失败都在这里暴露） -->
            <el-alert
              v-if="recordingStore.error"
              class="record-error"
              type="error"
              show-icon
              :closable="false"
              :title="recordingStore.error"
              description="请确认后端已启动（npm run backend）、麦克风正常，然后点「重录」再试一次。"
            />
          </template>
          <p v-else class="block-text muted">
            {{ copy.unopened }}
          </p>
        </div>

        <!-- 常见误区：内容来自 CMS -->
        <div class="card block">
          <h3>容易读错的地方</h3>
          <div v-if="level.unit?.mistakes?.length" class="mistake-list">
            <div v-for="(m, i) in level.unit.mistakes" :key="i" class="mistake-item">
              <el-icon color="#e6a23c"><Warning /></el-icon>
              <div>
                <strong>{{ m.title || m.phenomenon || '注意' }}</strong>
                <p>{{ m.text || m.hint || '' }}</p>
              </div>
            </div>
          </div>
          <p v-else class="block-text muted">{{ copy.empty }}</p>
        </div>
      </div>

      <!-- 关卡导航 -->
      <div class="card level-nav">
        <el-button :disabled="!neighbors.prev" @click="neighbors.prev && openLevel(neighbors.prev.code)">
          ← 上一关 {{ neighbors.prev ? `${neighbors.prev.code} ${neighbors.prev.target}` : '' }}
        </el-button>
        <el-button @click="router.push('/learn')">全部 30 关</el-button>
        <el-button :disabled="!neighbors.next" @click="neighbors.next && openLevel(neighbors.next.code)">
          下一关 {{ neighbors.next ? `${neighbors.next.code} ${neighbors.next.target}` : '' }} →
        </el-button>
      </div>
    </template>
  </div>

  <!-- ============ 30 关总览骨架 ============ -->
  <div v-else class="levels-view">
    <div class="card levels-header">
      <div>
        <h2>{{ copy.subtitle }}</h2>
        <p class="levels-meta">
          共 {{ levelsStore.levels.length }} 关 ·
          可练可测 {{ counts.opened }} ·
          只学不测 {{ counts.learnOnly }} ·
          未开放 {{ counts.unopened }}
        </p>
      </div>
      <el-button :icon="'Refresh'" :loading="levelsStore.loading" @click="levelsStore.fetchLevels(true)">
        刷新关卡
      </el-button>
    </div>

    <PageState
      v-if="levelsStore.error"
      state="error"
      :copy="copy"
      :detail="levelsStore.error"
      action-text="重新加载"
      @action="levelsStore.fetchLevels(true)"
    />

    <PageState
      v-else-if="levelsStore.loading && !levelsStore.levels.length"
      state="loading"
      :copy="copy"
    />

    <template v-for="group in groups" :key="group.key">
      <div v-if="group.items.length" class="group-block">
        <div class="group-title">
          <span>{{ group.label }}</span>
          <small>{{ group.items.length }} 关</small>
        </div>
        <div class="level-grid">
          <div
            v-for="l in group.items"
            :key="l.code"
            class="level-card"
            :class="[`is-${l.availability}`]"
            @click="openLevel(l.code)"
          >
            <div class="level-card-top">
              <span class="level-card-code">{{ l.code }}</span>
              <el-tag size="small" :type="availabilityTag(l)" effect="light">{{ availabilityText(l) }}</el-tag>
            </div>
            <div class="level-card-target">{{ l.target }}</div>
            <div class="level-card-char">{{ l.unit?.character || l.char }}</div>
          </div>
        </div>
      </div>
    </template>

    <p class="levels-foot">
      关卡身份（ID / 顺序 / 目标音）以关卡清单为准（SRS 02 3.4）；内容、发布状态与检测开关
      以 CMS 为唯一内容源，未发布即「未开放」（FR-1405）。
    </p>
  </div>
</template>

<style scoped>
.card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06); }
.card + .card, .card + .el-alert, .el-alert + .level-body { margin-top: 16px; }

/* ---- 状态卡 ---- */
.state-card { background: #fff; border-radius: 12px; padding: 32px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.06); display: flex; flex-direction: column; align-items: center; gap: 10px; }
.state-title { font-size: 16px; font-weight: 600; color: #303133; margin: 0; }
.state-text { font-size: 13px; color: #909399; margin: 0; line-height: 1.7; }

/* ---- 单关 ---- */
.level-header { display: flex; align-items: center; gap: 20px; }
.level-badge { flex: 0 0 auto; background: #409eff; color: #fff; font-weight: 700; font-size: 20px; border-radius: 12px; padding: 14px 18px; letter-spacing: 1px; }
.level-identity { flex: 1; }
.level-target { font-size: 40px; font-weight: 700; color: #303133; line-height: 1.1; }
.level-pinyin { font-size: 20px; color: #409eff; margin-left: 12px; }
.level-sub { display: flex; align-items: center; gap: 10px; margin-top: 6px; flex-wrap: wrap; }
.level-char { font-size: 13px; color: #606266; }
.level-actions { display: flex; flex-direction: column; gap: 8px; }
.level-body { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
.block h3 { margin: 0 0 12px; font-size: 16px; color: #303133; }
.block-text { font-size: 14px; color: #303133; line-height: 1.7; margin: 0 0 8px; }
.block-text.muted { color: #a8abb2; }
.block-detail { font-size: 13px; color: #606266; line-height: 1.7; margin: 0 0 12px; }
.disclaimer { margin: 12px 0 0; font-size: 12px; color: #a8abb2; }
.demo-source { margin: 8px 2px 0; }
.demo-source.is-real { color: #67c23a; }
.level-nav { display: flex; justify-content: space-between; margin-top: 16px; }

/* ---- 步骤 / 误区 ---- */
.step-list, .mistake-list { display: flex; flex-direction: column; gap: 10px; }
.step-item, .mistake-item { display: flex; gap: 10px; align-items: flex-start; background: #f5f7fa; border-radius: 8px; padding: 10px 12px; }
.step-index { flex: 0 0 22px; height: 22px; border-radius: 50%; background: #409eff; color: #fff; font-size: 12px; display: flex; align-items: center; justify-content: center; }
.step-item strong, .mistake-item strong { color: #303133; font-size: 14px; }
.step-item p, .mistake-item p { margin: 2px 0 0; font-size: 13px; color: #606266; }
.step-duration { color: #a8abb2 !important; }

/* ---- 录音 ---- */
.recording-controls { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.record-btn { width: 60px; height: 60px; font-size: 22px; }
.record-btn.recording { animation: pulse 1s infinite; }
@keyframes pulse { 0% { transform: scale(1) } 50% { transform: scale(1.08) } 100% { transform: scale(1) } }
.record-time { font-size: 22px; font-weight: 600; color: #303133; font-variant-numeric: tabular-nums; }
.waveform-canvas { width: 100%; height: 110px; border-radius: 8px; background: #1a1a2e; }
.record-actions { margin-top: 12px; display: flex; gap: 12px; }
.record-error { margin-top: 12px; text-align: left; }

/* ---- 列表 ---- */
.levels-header { display: flex; justify-content: space-between; align-items: center; }
.levels-header h2 { margin: 0; font-size: 18px; color: #303133; }
.levels-meta { margin: 6px 0 0; font-size: 13px; color: #909399; }
.group-block { margin-top: 20px; }
.group-title { display: flex; align-items: baseline; gap: 8px; font-size: 15px; font-weight: 600; color: #303133; margin-bottom: 10px; }
.group-title small { font-weight: 400; color: #a8abb2; }
.level-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.level-card { background: #fff; border-radius: 12px; padding: 14px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); cursor: pointer; transition: transform .15s, box-shadow .15s; border: 1px solid transparent; }
.level-card:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.1); }
.level-card.is-unopened { opacity: .62; }
.level-card.is-open { border-color: #b3e19d; }
.level-card.is-learn_only { border-color: #f3d19e; }
.level-card-top { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
.level-card-code { font-size: 12px; color: #909399; letter-spacing: .5px; }
.level-card-target { font-size: 30px; font-weight: 700; color: #303133; margin-top: 8px; }
.level-card-char { font-size: 13px; color: #909399; margin-top: 2px; }
.levels-foot { margin-top: 20px; font-size: 12px; color: #a8abb2; line-height: 1.7; }

@media (max-width: 900px) {
  .level-body { grid-template-columns: 1fr; }
  .level-header { flex-direction: column; align-items: flex-start; }
}
</style>
