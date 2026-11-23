<script setup lang="ts">
/**
 * CalibrationPanel：个人标定对话框（FR-1006 / D-20，可跳过）。
 * 录音区引导标定与 P11 主动重新标定共用；
 * 流程（个人标定流程改造方案）：创建/恢复会话 → 四个元音各 2 条（必要时第 3 条）
 * → 一段音域短文 → 最终计算 → 展示音域结果。
 * 每步录音可试听、重录、提交；刷新后从服务端恢复会话进度。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { QBtn, QCard, QCardSection, QDialog } from 'quasar'
import { ApiError } from '@/api'
import { useCalibration } from '@/features/calibration'
import { errorCopy } from '@/copy/usePageCopy'
import { usePlayerStore } from '@/stores/player'

const props = defineProps<{
  open: boolean
  /** 标定成功回调（检测流程自动重提交 / P11 刷新状态） */
}>()

const emit = defineEmits<{
  (e: 'done'): void
  (e: 'cancel'): void
  /** 直接关闭（× / 去登录）：不进入后续录音流程 */
  (e: 'dismiss'): void
}>()

const router = useRouter()
const calibration = useCalibration()
const player = usePlayerStore()
const wasOpen = ref(false)

/** 未登录导致的失败：改指引导登录，而非原地重试 */
const authFailed = computed(() => {
  const err = calibration.error.value
  return err instanceof ApiError && (err.code === 'AUTH_REQUIRED' || err.status === 401)
})

function gotoLogin() {
  // 带上当前路径，登录成功后回到原关卡（否则落到 /account，标定上下文丢失）
  const redirect = router.currentRoute.value.fullPath
  emit('dismiss')
  void router.push({ path: '/account/login', query: { redirect } })
}

onMounted(() => {
  if (props.open) void calibration.openSession()
})

watch(
  () => props.open,
  (open) => {
    if (open && !wasOpen.value) void calibration.openSession()
    if (!open) calibration.reset()
    wasOpen.value = open
  },
)

// 录音结束（手动停止或上限自动停止）只能从 recorder 状态感知：
// 监听 phase 本身永远不会触发（phase 正是要靠这里推进）
watch(
  () => calibration.recorder.status,
  (status) => {
    if (status === 'recorded') calibration.onStop()
  },
)

const task = computed(() => calibration.currentTask.value)
const session = computed(() => calibration.session.value)

/** 当前元音任务的任务配置（展示文字与拼音） */
const vowelTask = computed(() => {
  if (task.value?.kind !== 'vowel') return null
  return session.value?.vowels.find((v) => v.key === task.value?.vowel) ?? null
})

const isPitch = computed(() => task.value?.kind === 'pitch')

/** 计算失败（会话仍在、可重试） */
const calcFailed = computed(() =>
  calibration.phase.value === 'computing' && session.value?.calcState === 'failed')

/** 全部任务完成（计算成功）才关闭对话框；单条提交成功只更新进度 */
async function submit() {
  const ok = await calibration.submit()
  if (ok && calibration.phase.value === 'success') emit('done')
}

async function retryCompletion() {
  const ok = await calibration.requestCompletion()
  if (ok) emit('done')
}
</script>

<template>
  <QDialog
    :model-value="open"
    :persistent="true"
    @update:model-value="(value: boolean) => !value && emit('cancel')"
  >
    <QCard
      flat
      bordered
      class="calibration-panel"
      style="width: min(560px, 94vw)"
      role="dialog"
      aria-label="个人标定"
    >
      <QCardSection class="cal-content">
        <header class="cal-head">
          <div class="cal-head-text">
            <h2>个人标定</h2>
            <p>四个元音各录两条，再读一段短文：用于按本人音域与元音空间归一化</p>
          </div>
          <QBtn flat round dense class="cal-close" icon="close" aria-label="关闭" @click="emit('dismiss')" />
        </header>

        <!-- 进度：四个元音 + 短文 -->
        <div v-if="session" class="cal-progress" aria-label="标定进度">
          <span
            v-for="v in session.vowels"
            :key="v.key"
            class="cal-chip"
            :class="{ done: v.done, current: task?.kind === 'vowel' && task?.vowel === v.key }"
          >{{ v.displayText }} {{ v.done ? '✓' : `${v.acceptedTakes}/${v.targetTakes}` }}</span>
          <span
            class="cal-chip"
            :class="{ done: session.passageAccepted, current: task?.kind === 'pitch' }"
          >短文{{ session.passageAccepted ? ' ✓' : '' }}</span>
        </div>

        <!-- 提交成功的可见反馈 -->
        <p v-if="calibration.notice.value" class="cal-notice">{{ calibration.notice.value }}</p>

        <!-- 读取会话 -->
        <p v-if="calibration.phase.value === 'loading'" class="cal-loading">正在准备标定…</p>

        <!-- 蓝牙耳机警告：HFP 窄带会丢失高频，标定与正式录音同样受影响 -->
        <p v-if="calibration.recorder.inputBluetooth" class="cal-bluetooth-warn">
          当前检测到蓝牙耳机麦克风（{{ calibration.recorder.inputLabel }}）：录音会切换到窄带通话模式、丢失高频信息，请改用手机自带麦克风或外接麦克风。
        </p>

        <!-- retry_take：当前这条录音未通过质检，重录本条 -->
        <div v-if="calibration.failAdvice.value" class="cal-fail">
          <p class="cal-fail-title">这条录音没有通过检查</p>
          <p>{{ calibration.failAdvice.value }}</p>
          <QBtn outline no-caps color="blue-grey-4" text-color="blue-grey-9" class="cal-btn" label="再试一次" @click="calibration.startRecording()" />
        </div>

        <!-- vowel_dispersed：该元音几条录音差异较大，需再录一条 -->
        <div v-else-if="calibration.dispersedNotice.value" class="cal-fail">
          <p class="cal-fail-title">这个元音的几次录音差异较大</p>
          <p>请放松、用自然的音量平稳发音，再录一次。</p>
          <QBtn outline no-caps color="blue-grey-4" text-color="blue-grey-9" class="cal-btn" label="再录一次" @click="calibration.startRecording()" />
        </div>

        <!-- 当前任务 -->
        <template v-if="calibration.phase.value !== 'success' && task">
          <div class="cal-text">
            <template v-if="isPitch">
              <h3>请朗读下面这段短文</h3>
              <p class="cal-passage">{{ session?.passageText }}</p>
              <p class="cal-note">按页面文字用平常的音高连续朗读，不用刻意高或低。</p>
            </template>
            <template v-else>
              <p class="cal-vowel">
                {{ vowelTask?.displayText }}
                <span class="cal-vowel-pinyin">{{ vowelTask?.pinyin }} {{ vowelTask?.ipa }}</span>
              </p>
              <p class="cal-note">
                自然、平稳地延长发音，约 1 秒<template v-if="task?.additionalTake">；前两条录音差异较大，请再录一条</template>。
              </p>
            </template>
          </div>

          <div v-if="calibration.phase.value === 'intro'" class="cal-actions">
            <QBtn
              unelevated
              no-caps
              color="primary"
              class="cal-btn primary"
              :label="isPitch ? '● 开始朗读录音' : '● 开始录音'"
              @click="calibration.startRecording()"
            />
          </div>

          <div v-else-if="calibration.phase.value === 'recording'" class="cal-recording">
            <p class="cal-recording-hint">
              录音中…{{ isPitch ? '读完后' : '发完音后' }}点「停止」（最长 {{ isPitch ? 40 : 10 }} 秒）
            </p>
            <span class="cal-timer">{{ (calibration.recorder.elapsedMs / 1000).toFixed(1) }}s</span>
            <QBtn unelevated no-caps color="primary" class="cal-btn stop" label="■ 停止" @click="calibration.recorder.stop()" />
          </div>

          <div
            v-else-if="calibration.phase.value === 'recorded' || calibration.phase.value === 'uploading' || calibration.phase.value === 'submitting'"
            class="cal-recorded"
          >
            <QBtn
              v-if="calibration.recorder.blobUrl"
              outline
              no-caps
              color="primary"
              text-color="primary"
              class="cal-btn"
              :label="player.isCurrent('cal-preview') ? '⏸ 暂停试听' : '▶ 试听'"
              @click="player.play({ key: 'cal-preview', url: calibration.recorder.blobUrl! })"
            />
            <QBtn
              outline
              no-caps
              color="primary"
              text-color="primary"
              class="cal-btn"
              label="重录"
              :disable="calibration.busy.value"
              @click="calibration.discard()"
            />
            <QBtn
              unelevated
              no-caps
              color="primary"
              class="cal-btn primary"
              :label="calibration.busy.value ? '处理中…' : '提交本条录音'"
              :disable="calibration.busy.value"
              @click="submit"
            />
          </div>
        </template>

        <!-- 最终计算中 -->
        <div v-if="calibration.phase.value === 'computing'" class="cal-computing">
          <p>正在计算个人标定结果…</p>
          <p v-if="calcFailed" class="cal-fail-inline">计算没有成功：{{ session?.lastError ?? '请重试' }}</p>
          <QBtn
            v-if="calcFailed"
            outline
            no-caps
            color="blue-grey-4"
            text-color="blue-grey-9"
            class="cal-btn"
            label="重试计算"
            @click="retryCompletion"
          />
        </div>

        <!-- 成功 -->
        <div v-if="calibration.phase.value === 'success'" class="cal-success">
          <p>
            标定完成{{ calibration.result.value ? `，你的音域约 ${Math.round(calibration.result.value.pitchRange.fLo)}–${Math.round(calibration.result.value.pitchRange.fHi)} Hz` : '' }}。
          </p>
          <p v-if="session" class="cal-success-detail">
            {{ session.vowels.filter((v) => v.done).length }}/4 个元音已完成标定；元音空间图使用 i/u/a，音域用于声调五度值换算。
          </p>
          <QBtn unelevated no-caps color="primary" class="cal-btn primary" label="继续" @click="emit('done')" />
        </div>

        <!-- 失败：未登录 → 去登录；其他 → 重试 -->
        <div v-if="calibration.phase.value === 'failed' && calibration.error.value" class="cal-fail">
          <p class="cal-fail-title">{{ errorCopy(calibration.error.value).title }}</p>
          <p>{{ errorCopy(calibration.error.value).hint }}</p>
          <QBtn v-if="authFailed" outline no-caps color="primary" text-color="primary" class="cal-btn" label="去登录" @click="gotoLogin" />
          <QBtn v-else outline no-caps color="primary" text-color="primary" class="cal-btn" label="重试" @click="calibration.openSession()" />
        </div>

        <footer class="cal-foot">
          <!-- 未登录时不再提供「跳过标定，直接录音」：跳过去录完也提交不了（上传要求登录） -->
          <QBtn
            v-if="!authFailed"
            flat
            no-caps
            color="grey-5"
            :label="calibration.phase.value === 'success' ? '关闭' : '跳过标定，直接录音'"
            @click="emit('cancel')"
          />
        </footer>
      </QCardSection>
    </QCard>
  </QDialog>
</template>

<style scoped lang="sass">
.calibration-panel
  max-height: 88vh
  overflow: auto

.cal-content
  display: flex
  flex-direction: column
  gap: 14px

.cal-head
  display: flex
  align-items: flex-start
  justify-content: space-between
  gap: 10px

  h2
    margin: 0 0 4px
    font-size: 18px
  p
    margin: 0
    font-size: 13px
    color: var(--vs-mute)

.cal-close
  flex-shrink: 0

.cal-progress
  display: flex
  gap: 8px
  flex-wrap: wrap

.cal-chip
  border: 1px solid #cfd8dc
  border-radius: 14px
  padding: 3px 12px
  font-size: 13px
  color: #607d8b

  &.done
    background: #e8f5e9
    border-color: #a5d6a7
    color: #1b5e20

  &.current
    background: #e0f2f1
    border-color: #4db6ac
    color: #00695c
    font-weight: 700

.cal-loading
  color: var(--vs-mute)
  text-align: center

.cal-text
  background: var(--vs-soft)
  border-radius: 10px
  padding: 14px
  h3
    margin: 0 0 8px
    font-size: 15px
    color: var(--vs-coffee)

.cal-passage
  font-size: 18px
  line-height: 2
  margin: 0 0 8px
  color: var(--vs-ink)

.cal-note
  margin: 0
  font-size: 13px
  color: var(--vs-coffee-d)

/* 元音任务主展示：目标元音大字居中 */
.cal-vowel
  margin: 4px 0 8px
  text-align: center
  font-size: 30px
  font-weight: 700
  color: #004d40

.cal-vowel-pinyin
  font-size: 15px
  font-weight: 400
  color: #00796b

/* 单条提交成功反馈 */
.cal-notice
  margin: 0
  background: #e8f5e9
  border: 1px solid #a5d6a7
  border-radius: 10px
  padding: 8px 14px
  font-size: 13px
  color: #1b5e20

.cal-bluetooth-warn
  margin: 0
  font-size: 13px
  color: #bf360c
  font-weight: 600

.cal-actions, .cal-recorded, .cal-recording
  display: flex
  gap: 10px
  align-items: center
  justify-content: center
  flex-wrap: wrap

/* 原 .cal-btn 胶囊基础尺寸（48px 触达 / 110px 最小宽 / 15px 字号）；
   .primary 实底青（var(--vs-brand)）字重 700 同原版 .cal-btn.primary */
.cal-btn
  min-height: 48px
  min-width: 110px
  font-size: 15px
  &.primary
    font-weight: 700

.cal-recording
  flex-direction: column

.cal-recording-hint
  margin: 0
  color: var(--vs-brand)
  font-size: 14px

.cal-timer
  font-variant-numeric: tabular-nums
  font-size: 24px
  font-weight: 700
  color: var(--vs-brand)

.cal-fail
  background: var(--vs-amber-soft)
  border: 1px solid var(--vs-sand)
  border-radius: 10px
  padding: 12px 16px
  display: flex
  flex-direction: column
  gap: 8px
  align-items: flex-start
  p
    margin: 0
    font-size: 14px
    color: var(--vs-ink2)

.cal-fail-title
  font-weight: 700
  color: var(--vs-brand-d)

.cal-computing
  background: #e3f2fd
  border: 1px solid #90caf9
  border-radius: 10px
  padding: 14px
  display: flex
  flex-direction: column
  gap: 8px
  align-items: flex-start
  p
    margin: 0
    color: #0d47a1
    font-size: 14px

.cal-fail-inline
  color: #bf360c

.cal-success
  background: var(--vs-green-soft)
  border: 1px solid var(--vs-green-line)
  border-radius: 10px
  padding: 16px
  display: flex
  flex-direction: column
  gap: 10px
  align-items: flex-start
  p
    margin: 0
    color: var(--vs-green-d)

.cal-success-detail
  font-size: 13px
  color: #2e7d32

.cal-foot
  text-align: center
</style>
