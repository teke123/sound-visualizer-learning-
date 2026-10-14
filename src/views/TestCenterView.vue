<script setup lang="ts">
// 检测中心（P08，FR-901~908）：任务列表仅含「已发布且检测已开放」的关；
// 录音前可听示范并看到朗读内容；环境与用途说明；录音过程控制；处理失败可理解。
// 与 P05 关卡内录音是同一任务、同一套评分口径（FR-907）。
// 以下为占位状态与动作（不包含任何假实现），重构时按意图恢复。
import { computed, ref } from 'vue'
import { useUnitsStore } from '@/stores/units'
import { useRecordingStore } from '@/stores/recording'
import { usePageCopy } from '@/composables/usePageCopy'
import { TTS_DISCLAIMER } from '@/composables/useSpeechDemo'
import PageState from '@/components/PageState.vue'
import PageFeedback from '@/components/PageFeedback.vue'

const unitsStore = useUnitsStore()
const recordingStore = useRecordingStore()
const { copy } = usePageCopy('P08')

/** TODO(重构): 任务列表 = 已发布且检测开放的关（FR-901） */
type Task = { id: string; character: string; pinyin: string; conclusion?: string }
const verifiedTasks = ref<Task[]>([])
const unitId = ref('')
const unit = computed(() => verifiedTasks.value.find(t => t.id === unitId.value) || null)

/** CMS 正式示范音缺失时的合成示意（必须如实标注，不冒充授权示范） */
const speech = { speak: (_text: string, _speed: 'normal' | 'slow') => { /* TODO(重构): useSpeechDemo */ }, disclaimer: TTS_DISCLAIMER }

const loadState = computed<'loading' | 'error' | 'empty' | null>(() =>
  unitsStore.error ? 'error' : verifiedTasks.value.length ? null : 'empty',
)
function handleLoadAction(): void { unitsStore.fetchPublished() }
function selectTask(): void { /* TODO(重构): 载入该关检测任务（提示词/示范/质检要求） */ }

const envOk = ref(false)
const consented = ref(false)   // TODO(重构): 读服务端同意状态
const authOk = ref(false)
const micError = ref('')
function checkMic(): void { /* TODO(重构): getUserMedia 权限请求与失败指引（FR-904） */ }

const countdown = ref(0)
const analysisState = ref<'loading' | 'error' | null>(null)
const analysisDetail = ref('')
function startTest(): void { /* TODO(重构): useAssessmentFlow 录音开始（含倒计时） */ }
function submit(): void { /* TODO(重构): 提交检测（幂等键），进度态与超时按 NFR-03 */ }
function retryAnalysis(): void { /* TODO(重构): 失败重试，保留已录内容 */ }
</script>

<template>
  <div class="test-center">
    <h2>检测中心</h2>
    <p class="intro">{{ copy.subtitle }}</p>

    <!-- 任务加载 / 错误 / 未开放统一走 P08 文案位：后端没连上要说清，不能让人误读成「就是没有任务」 -->
    <PageState
      :state="loadState"
      :copy="copy"
      :detail="loadState === 'error' ? (unitsStore.error || undefined) : undefined"
      @action="handleLoadAction"
    />

    <template v-if="!loadState">
      <!-- TEST-01 任务选择 -->
      <el-card class="step-card">
        <h4>1. 选择任务</h4>
        <el-radio-group v-model="unitId" @change="selectTask">
          <el-radio v-for="t in verifiedTasks" :key="t.id" :value="t.id" border class="task-radio">
            {{ t.character }}（{{ t.pinyin }}）
          </el-radio>
        </el-radio-group>
      </el-card>

      <el-card v-if="unit" class="task-card">
        <h3>任务：{{ unit.character }}（{{ unit.pinyin }}）</h3>
        <p>{{ unit.conclusion }}</p>
        <p class="meta">请朗读：{{ unit.character.split('/')[0] }} · 预计约 30 秒</p>
      </el-card>

      <!-- TEST-02 示范 -->
      <el-card class="step-card">
        <h4>2. 听示范</h4>
        <el-button @click="speech.speak(unit?.character?.split('/')[0] || '妈', 'normal')">正常速度</el-button>
        <el-button @click="speech.speak(unit?.character?.split('/')[0] || '妈', 'slow')">慢速</el-button>
        <p class="tts-note">{{ speech.disclaimer }}</p>
      </el-card>

      <!-- TEST-03 环境检查 -->
      <el-card class="step-card">
        <h4>3. 环境检查</h4>
        <el-checkbox v-model="envOk">我已确认环境安静、麦克风距离约 10–20 cm、设备正常</el-checkbox>
      </el-card>

      <!-- TEST-04/05 用途与授权 -->
      <el-card class="step-card">
        <h4>4. 用途说明与麦克风授权</h4>
        <p>录音用于本次检测分析。{{ consented ? '已同意保存到个人档案。' : '未同意前不会长期保存，也不用于研究或模型训练。' }}</p>
        <el-button @click="checkMic">请求麦克风权限</el-button>
        <el-tag v-if="authOk" type="success" style="margin-left:8px">已授权</el-tag>
        <p v-else class="hint">若拒绝授权，请在浏览器设置中开启麦克风后刷新页面。</p>
        <p v-if="micError" class="hint mic-error">授权失败原因：{{ micError }}</p>
      </el-card>

      <!-- TEST-06 录音 -->
      <el-card class="step-card">
        <h4>5. 录音</h4>
        <div v-if="countdown > 0" class="countdown">{{ countdown }}</div>
        <el-button v-if="!recordingStore.isRecording" type="danger" @click="startTest">{{ copy.cta }}</el-button>
        <el-button v-else type="info" @click="recordingStore.stopRecording()">停止</el-button>
        <audio v-if="recordingStore.audioUrl" :src="recordingStore.audioUrl" controls class="playback" />
        <div class="actions">
          <el-button @click="recordingStore.clearRecording()">重录</el-button>
          <el-button type="primary" :disabled="!recordingStore.hasRecording" :loading="recordingStore.isAnalyzing" @click="submit">提交分析</el-button>
        </div>
      </el-card>

      <!-- TEST-07 处理状态：分析与分析失败都走文案位，原始错误进 detail -->
      <PageState
        :state="analysisState"
        :copy="copy"
        :detail="analysisState === 'error' ? analysisDetail : undefined"
        :show-action="analysisState === 'error'"
        @action="retryAnalysis"
      />
    </template>

    <PageFeedback page="test-center" :unit-id="unitId" type="result" />
  </div>
</template>

<style scoped>
.test-center { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.intro { color: #606266; font-size: 14px; margin: 0; }
.task-card h3 { margin: 0 0 8px; }
.meta, .tts-note, .hint { font-size: 13px; color: #909399; }
.mic-error { color: #c45656; }
.step-card h4 { margin: 0 0 12px; }
.task-radio { margin: 4px 8px 4px 0; }
.countdown { font-size: 48px; font-weight: 700; text-align: center; color: #409eff; }
.playback { display: block; margin-top: 12px; width: 100%; }
.actions { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
</style>
