<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRecordingStore } from '@/stores/recording'
import * as echarts from 'echarts'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js'
import { getUnitMeta } from '@/data/pinyinUnits'
import PageFeedback from '@/components/PageFeedback.vue'
import PageState from '@/components/PageState.vue'
import { usePageCopy } from '@/composables/usePageCopy'
import { useUserStore } from '@/stores/user'
import { learningRecordApi } from '@/api'
import { maskByVoiced, smoothSeries } from '@/utils/toneCurve'
import { ElMessage } from 'element-plus'
import type { LearningRecord } from '@/types'

const route = useRoute()
const router = useRouter()
const recordingStore = useRecordingStore()
const userStore = useUserStore()
const { copy } = usePageCopy('P09')

const unitId = computed(() => route.params.id as string)
const assessment = computed(() => recordingStore.assessment)

/**
 * 后端有没有给标准声调曲线。
 * 没有就不画、图例也不留，并在图下显式说明原因 —— 不能编一条再标「标准发音」。
 * 现状：L01–L30 不在后端 UNIT_REFERENCE 白名单里，所以正式关卡拿不到 standardF0。
 */
const toneStandardMissing = computed(() => {
  const a = assessment.value?.audioAnalysis
  if (!a) return false
  const std = a.standardF0 || []
  return !(std.length > 0 && std.some(v => typeof v === 'number' && v > 0))
})

/**
 * 声谱图有没有可用数据。
 * 没有就不能画 —— 原先是把 80×100 个像素全涂成 rgb(0,0,255)，
 * 看上去像"图坏了"，既不是空态也不诚实。
 */
const hasSpectrogramData = computed(() => {
  const m = assessment.value?.audioAnalysis?.mfcc
  return !!m && m.length > 0 && (m[0]?.length ?? 0) > 0
})

/** 能量图有没有可用数据 */
const hasEnergyData = computed(() => {
  const e = assessment.value?.audioAnalysis?.energy
  return !!e && e.length > 0 && e.some(v => typeof v === 'number' && v > 0)
})

// =============================================
// 刷新 / 直开本页时的结果恢复
// 分析结果（含 F0/MFCC/共振峰/能量）只存在于前端内存，LearningRecord 里没有
// audioAnalysis，所以恢复出来的只能是「上次练习结果」的分数与文字反馈，图表无法恢复。
// 状态机：idle/loading（请求中）→ done（有记录）/ empty（该关无记录）/ error（接口失败）
// =============================================
type RestoreState = 'idle' | 'loading' | 'done' | 'empty' | 'error'

const restoreState = ref<RestoreState>('idle')
const restoreError = ref('')
const lastRecord = ref<LearningRecord | null>(null)
const isPlaying = ref(false)

// 播放中的 blob URL 与音频实例，卸载/重播前都要释放，避免内存泄漏
let audioEl: HTMLAudioElement | null = null
let audioUrl: string | null = null

function stopAudio() {
  if (audioEl) {
    audioEl.pause()
    audioEl = null
  }
  if (audioUrl) {
    URL.revokeObjectURL(audioUrl)
    audioUrl = null
  }
  isPlaying.value = false
}

// 恢复该关最近一次练习记录：取用户记录 → 筛当前 unitId → 按 createdAt 倒序取最新一条
async function restoreLastRecord() {
  restoreState.value = 'loading'
  restoreError.value = ''
  try {
    const res = await learningRecordApi.getByUser(userStore.userId, 50)
    const mine = (res.data || [])
      .filter(r => r.unitId === unitId.value)
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    const latest = mine[0] ?? null
    if (!latest) {
      lastRecord.value = null
      restoreState.value = 'empty'
      return
    }
    lastRecord.value = latest
    restoreState.value = 'done'
  } catch (err) {
    lastRecord.value = null
    restoreError.value = err instanceof Error ? err.message : String(err)
    restoreState.value = 'error'
  }
}

// 同一组件内切换关卡（/feedback/a → /feedback/b）时重新恢复，避免停留在上一关的记录
watch(unitId, () => {
  if (assessment.value) return
  stopAudio()
  lastRecord.value = null
  void restoreLastRecord()
})

// 按需拉取录音 blob URL 播放（后端 /learning-records/{id}/audio）
async function playLastRecord() {
  const record = lastRecord.value
  if (!record) return
  try {
    stopAudio()
    const url = await learningRecordApi.getRecordAudio(record.id)
    const el = new Audio(url)
    el.onended = () => { isPlaying.value = false }
    el.onerror = () => { isPlaying.value = false }
    audioUrl = url
    audioEl = el
    isPlaying.value = true
    await el.play()
  } catch (err) {
    console.error(err)
    stopAudio()
    ElMessage.error(copy.error)
  }
}

const toneChartRef = ref<HTMLDivElement | null>(null)
const threeContainerRef = ref<HTMLDivElement | null>(null)
const spectrogramRef = ref<HTMLCanvasElement | null>(null)
const formantChartRef = ref<HTMLDivElement | null>(null)
const energyChartRef = ref<HTMLDivElement | null>(null)

// ---------------------------------------------------------------------------
// 3D 演示环境预检（第 7 周任务）
// three 0.185 只接受 WebGL2；创建失败时它会抛未捕获异常，界面上只剩一个空框。
// 所以初始化前先探测能力，失败就给看得懂的兜底文案，而不是白屏。
// ---------------------------------------------------------------------------
type ThreeState = 'idle' | 'ready' | 'unsupported' | 'error'
const threeState = ref<ThreeState>('idle')
/** 3D 是否已确定不可用（用于模板在「画布」与「兜底说明」之间切换） */
const threeFailed = computed(
  () => threeState.value === 'unsupported' || threeState.value === 'error',
)

/** 能否创建 WebGL2 上下文（探测完立即丢弃，不占上下文名额） */
function supportsWebGL2(): boolean {
  try {
    if (typeof WebGL2RenderingContext === 'undefined') return false
    const c = document.createElement('canvas')
    const ctx = c.getContext('webgl2')
    if (!ctx) return false
    // 主动释放探测用的上下文
    ;(ctx as WebGL2RenderingContext).getExtension('WEBGL_lose_context')?.loseContext()
    return true
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// ECharts 实例登记：容器挂在 v-if 上，容器被摘掉后 getInstanceByDom 再也找不到
// 旧实例，会变成永久孤儿。用一张 Set 记住所有活着的实例，卸载时统一 dispose。
// ---------------------------------------------------------------------------
const liveCharts = new Set<echarts.ECharts>()

/** 取（或重建）某个容器上的 ECharts 实例，并登记到 liveCharts */
function trackChart(el: HTMLDivElement | null): echarts.ECharts | null {
  if (!el) return null
  const old = echarts.getInstanceByDom(el)
  if (old) {
    liveCharts.delete(old)
    old.dispose()
  }
  const chart = echarts.init(el)
  liveCharts.add(chart)
  return chart
}

// =============================================
// 发音特征解析：根据拼音推导口腔各部位姿态
// =============================================
interface ArticulationPose {
  // 下颌开合度 0~1
  jaw: number
  // 舌位：舌尖/舌中/舌根的目标位置与缩放（x 前后、y 高低、z 左右）
  tongueTip: { x: number; y: number; z: number; sy: number }
  tongueMid: { x: number; y: number; z: number; sy: number }
  tongueBack: { x: number; y: number; z: number; sy: number }
  // 嘴唇：展唇(横向拉伸) 0~1、圆唇(向前收拢) 0~1
  lipSpread: number
  lipRound: number
  // 软腭下降（鼻音时打开鼻腔通道）0~1
  velum: number
  // 气流强度
  airflow: number
}

// 声母分类：舌位基准
const TONGUE_LOW = { x: 0, y: -0.18, z: 0, sy: 0.8 }   // 舌平放

// 声母 → 发音姿态
function getInitialPose(initial: string): ArticulationPose {
  switch (initial) {
    // 双唇音 b p m：双唇闭合，舌平放
    case 'b': case 'p': case 'm':
      return {
        jaw: 0.15, tongueTip: { ...TONGUE_LOW, x: 0.05 }, tongueMid: { ...TONGUE_LOW }, tongueBack: { ...TONGUE_LOW },
        lipSpread: 0.1, lipRound: 0.3, velum: initial === 'm' ? 1 : 0, airflow: initial === 'p' ? 1 : 0.3,
      }
    // 唇齿音 f：下唇抵上齿，舌平放稍后
    case 'f':
      return {
        jaw: 0.2, tongueTip: { ...TONGUE_LOW, x: -0.08 }, tongueMid: { ...TONGUE_LOW }, tongueBack: { ...TONGUE_LOW },
        lipSpread: 0.3, lipRound: 0.1, velum: 0, airflow: 0.9,
      }
    // 舌尖中音 d t n l：舌尖抵上齿龈，舌中部下沉
    case 'd': case 't': case 'n': case 'l':
      return {
        jaw: 0.3, tongueTip: { x: 0.08, y: 0, z: 0, sy: 1.5 }, tongueMid: { ...TONGUE_LOW }, tongueBack: { ...TONGUE_LOW },
        lipSpread: 0.2, lipRound: 0.1, velum: initial === 'n' ? 1 : 0, airflow: initial === 't' ? 1 : 0.3,
      }
    // 舌根音 g k h：舌根抬起抵软腭
    case 'g': case 'k': case 'h':
      return {
        jaw: 0.35, tongueTip: { ...TONGUE_LOW }, tongueMid: { ...TONGUE_LOW }, tongueBack: { x: -0.1, y: 0.08, z: 0, sy: 1.6 },
        lipSpread: 0.2, lipRound: 0.1, velum: 0, airflow: initial === 'k' ? 1 : (initial === 'h' ? 0.9 : 0.3),
      }
    // 舌面音 j q x：舌面前部抵硬腭，舌面抬高
    case 'j': case 'q': case 'x':
      return {
        jaw: 0.2, tongueTip: { x: 0.1, y: 0.05, z: 0, sy: 1.7 }, tongueMid: { x: 0.05, y: 0.05, z: 0, sy: 1.5 }, tongueBack: { ...TONGUE_LOW },
        lipSpread: 0.6, lipRound: 0, velum: 0, airflow: initial === 'q' ? 1 : (initial === 'x' ? 0.9 : 0.3),
      }
    // 翘舌音 zh ch sh r：舌尖卷起抵硬腭前部
    case 'zh': case 'ch': case 'sh': case 'r':
      return {
        jaw: 0.25, tongueTip: { x: 0.02, y: 0.1, z: 0, sy: 1.8 }, tongueMid: { x: 0, y: 0.02, z: 0, sy: 1.3 }, tongueBack: { ...TONGUE_LOW },
        lipSpread: 0.3, lipRound: 0.15, velum: 0, airflow: initial === 'ch' ? 1 : (initial === 'sh' ? 0.9 : 0.3),
      }
    // 平舌音 z c s：舌尖抵下齿背，舌平
    case 'z': case 'c': case 's':
      return {
        jaw: 0.2, tongueTip: { x: 0.1, y: -0.15, z: 0, sy: 1.0 }, tongueMid: { ...TONGUE_LOW }, tongueBack: { ...TONGUE_LOW },
        lipSpread: 0.3, lipRound: 0.1, velum: 0, airflow: initial === 'c' ? 1 : (initial === 's' ? 0.9 : 0.3),
      }
    default:
      return {
        jaw: 0.3, tongueTip: { ...TONGUE_LOW }, tongueMid: { ...TONGUE_LOW }, tongueBack: { ...TONGUE_LOW },
        lipSpread: 0.3, lipRound: 0.1, velum: 0, airflow: 0.3,
      }
  }
}

// 韵母 → 口型姿态
function getFinalPose(finals: string): ArticulationPose {
  const has = (re: RegExp) => re.test(finals)
  const isNasal = has(/n$/) || has(/ng$/)
  let pose: ArticulationPose
  if (has(/a/)) {
    // a 开口大、舌低
    pose = {
      jaw: 0.9, tongueTip: { x: 0, y: -0.25, z: 0, sy: 0.8 }, tongueMid: { x: 0, y: -0.2, z: 0, sy: 0.8 }, tongueBack: { x: 0, y: -0.15, z: 0, sy: 0.8 },
      lipSpread: 0.4, lipRound: 0.1, velum: isNasal ? 0.8 : 0, airflow: 0.4,
    }
  } else if (has(/o/)) {
    // o 圆唇、舌后缩
    pose = {
      jaw: 0.7, tongueTip: { x: -0.05, y: -0.15, z: 0, sy: 0.9 }, tongueMid: { x: -0.08, y: -0.1, z: 0, sy: 1.0 }, tongueBack: { x: -0.15, y: -0.05, z: 0, sy: 1.2 },
      lipSpread: 0.1, lipRound: 0.9, velum: isNasal ? 0.8 : 0, airflow: 0.4,
    }
  } else if (has(/i/)) {
    // i 展唇、舌位高前
    pose = {
      jaw: 0.35, tongueTip: { x: 0.15, y: 0.02, z: 0, sy: 1.4 }, tongueMid: { x: 0.1, y: 0.02, z: 0, sy: 1.3 }, tongueBack: { ...TONGUE_LOW },
      lipSpread: 1, lipRound: 0, velum: isNasal ? 0.8 : 0, airflow: 0.35,
    }
  } else if (has(/u/)) {
    // u 圆唇、舌位高后
    pose = {
      jaw: 0.35, tongueTip: { x: -0.05, y: -0.1, z: 0, sy: 1.0 }, tongueMid: { x: -0.1, y: -0.05, z: 0, sy: 1.1 }, tongueBack: { x: -0.15, y: 0, z: 0, sy: 1.3 },
      lipSpread: 0.05, lipRound: 1, velum: isNasal ? 0.8 : 0, airflow: 0.3,
    }
  } else if (has(/ü|v/)) {
    // ü 撮口、舌位高前
    pose = {
      jaw: 0.3, tongueTip: { x: 0.15, y: 0.05, z: 0, sy: 1.5 }, tongueMid: { x: 0.1, y: 0.05, z: 0, sy: 1.4 }, tongueBack: { ...TONGUE_LOW },
      lipSpread: 0.15, lipRound: 0.85, velum: isNasal ? 0.8 : 0, airflow: 0.3,
    }
  } else {
    // e 半开口、舌中
    pose = {
      jaw: 0.6, tongueTip: { x: 0, y: -0.12, z: 0, sy: 1.0 }, tongueMid: { x: 0, y: -0.1, z: 0, sy: 1.0 }, tongueBack: { x: 0, y: -0.05, z: 0, sy: 1.0 },
      lipSpread: 0.3, lipRound: 0.2, velum: isNasal ? 0.8 : 0, airflow: 0.35,
    }
  }
  return pose
}

// 从拼音解析声母/韵母
function splitPinyin(pinyin: string): { initial: string; finals: string } {
  const initials = ['zh', 'ch', 'sh', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h', 'j', 'q', 'x', 'r', 'z', 'c', 's', 'y', 'w']
  for (const ini of initials) {
    if (pinyin.startsWith(ini)) {
      return { initial: ini, finals: pinyin.slice(ini.length) }
    }
  }
  return { initial: '', finals: pinyin }
}

// 综合声母与韵母，得到最终发音姿态
function getArticulationPose(unitId: string): ArticulationPose {
  // 声调练习单元如 ma_t2 → 去后缀取 ma
  const baseId = unitId.replace(/_[a-z0-9]+$/i, '')
  const { initial, finals } = splitPinyin(baseId)
  const initialPose = initial ? getInitialPose(initial) : null
  const finalPose = getFinalPose(finals)

  // 无声母（零声母音节如 a/o/er）直接用韵母姿态
  if (!initialPose) return finalPose

  // 组合：下颌取韵母（元音主导口型），舌位声母为准（辅音成阻），唇形按元音
  return {
    jaw: Math.max(initialPose.jaw, finalPose.jaw * 0.7),
    tongueTip: initialPose.tongueTip,
    tongueMid: initialPose.tongueMid,
    tongueBack: initialPose.tongueBack,
    lipSpread: finalPose.lipSpread,
    lipRound: finalPose.lipRound,
    velum: Math.max(initialPose.velum, finalPose.velum),
    airflow: initialPose.airflow,
  }
}

// 当前单元的发音姿态（供动画使用）
const currentPose = computed(() => getArticulationPose(unitId.value))

// =============================================
// 精细 3D 口腔模型：上颚/软腭/上下颌/舌头/牙齿/嘴唇/声带/气流
// =============================================
/** 3D 场景初始化（带 WebGL2 能力检测与异常兜底） */
function initThreeScene(): (() => void) | null {
  if (!threeContainerRef.value) return null
  if (!supportsWebGL2()) {
    threeState.value = 'unsupported'
    console.warn('[3D] 当前环境无法创建 WebGL2 上下文，已降级为文字说明')
    return null
  }
  try {
    const dispose = initThreeSceneInner()
    threeState.value = dispose ? 'ready' : 'error'
    return dispose ?? null
  } catch (e) {
    threeState.value = 'error'
    console.error('[3D] 场景初始化失败', e)
    return null
  }
}

function initThreeSceneInner(): (() => void) | undefined {
  if (!threeContainerRef.value) return
  const container = threeContainerRef.value
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf7f4ef)
  // 浅色暖调背景，贴近教材纸张质感
  scene.fog = new THREE.Fog(0xf7f4ef, 8, 16)

  const camera = new THREE.PerspectiveCamera(42, container.clientWidth / container.clientHeight, 0.1, 100)
  // 默认侧面（矢状面）视角：第一眼就是教科书口腔剖面图
  camera.position.set(3.1, 0.05, 0.02)
  camera.lookAt(0, -0.1, 0)
  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(container.clientWidth, container.clientHeight)
  renderer.shadowMap.enabled = true
  container.appendChild(renderer.domElement)

  // CSS2D 渲染器（汉字/发音信息标注，不随透视变形）
  const labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(container.clientWidth, container.clientHeight)
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.top = '0'
  labelRenderer.domElement.style.left = '0'
  labelRenderer.domElement.style.pointerEvents = 'none'
  container.appendChild(labelRenderer.domElement)

  // 当前汉字 + 发音部位标注
  const meta = getUnitMeta(unitId.value)
  const labelDiv = document.createElement('div')
  labelDiv.style.cssText = 'text-align:center;color:#6b3a52;font-family:sans-serif;user-select:none;'
  const charSpan = document.createElement('div')
  charSpan.textContent = meta?.char || unitId.value
  charSpan.style.cssText = 'font-size:34px;font-weight:700;text-shadow:0 1px 4px rgba(255,255,255,0.8);'
  const pinyinSpan = document.createElement('div')
  pinyinSpan.textContent = meta?.tone || ''
  pinyinSpan.style.cssText = 'font-size:14px;color:#4a7a9a;margin-top:2px;'
  labelDiv.appendChild(charSpan)
  labelDiv.appendChild(pinyinSpan)
  const label = new CSS2DObject(labelDiv)
  label.position.set(0, 1.55, 0)
  scene.add(label)

  // 部位中文标注（悬停查看详细说明，帮助学习者看懂口腔结构）
  // 相机在 x 轴正方向看向原点，屏幕投影中 y 控制上下、z 控制左右、x 控制远近缩放
  // 坐标已按截图中模型的视觉方向重新对齐，使标签贴合对应结构外缘
  const partLabelItems = [
    { name: '鼻腔', desc: '鼻音（m、n、ng）的气流从这里流出', x: 0.15, y: 0.75, z: 0.0 },
    { name: '上颚', desc: '硬腭。舌面音（j、q、x）舌尖抵住硬腭前部', x: 0.15, y: 0.32, z: 0.15 },
    { name: '软腭', desc: '发鼻音时下垂，让气流转向鼻腔', x: 0.15, y: 0.42, z: -0.28 },
    { name: '悬雍垂', desc: '小舌，和软腭一起控制鼻音', x: 0.15, y: 0.18, z: -0.38 },
    { name: '上牙', desc: '唇齿音（f）下唇抵住上齿', x: 0.15, y: 0.08, z: 0.42 },
    { name: '下牙', desc: '平舌音（z、c、s）舌尖抵住下齿背', x: 0.15, y: -0.28, z: 0.35 },
    { name: '上唇', desc: '双唇音（b、p、m）上下唇闭合', x: 0.15, y: 0.2, z: 0.78 },
    { name: '下唇', desc: '唇齿音（f）下唇靠近上齿', x: 0.15, y: -0.35, z: 0.78 },
    { name: '舌头', desc: '舌尖、舌中、舌根控制大多数声母的发音部位', x: 0.15, y: -0.12, z: 0.08 },
    { name: '喉', desc: '气流从肺部经喉部进入口腔', x: 0.15, y: -0.28, z: -0.82 },
  ] as const
  for (const p of partLabelItems) {
    const pDiv = document.createElement('div')
    pDiv.textContent = p.name
    pDiv.title = p.desc
    // 始终浮于前景：半透明底 + 细描边，文字本身半透明，不遮挡 3D 模型
    pDiv.style.cssText = 'pointer-events:auto;cursor:help;z-index:10;background:rgba(255,255,255,0.45);border:1px solid rgba(255,255,255,0.7);border-radius:6px;padding:2px 8px;font-size:12px;font-weight:600;color:rgba(58,46,42,0.82);font-family:sans-serif;user-select:none;white-space:nowrap;box-shadow:0 1px 4px rgba(0,0,0,0.15);'
    const obj = new CSS2DObject(pDiv)
    obj.position.set(p.x, p.y, p.z)
    // 置于较高渲染顺序，确保标签叠在模型前景
    obj.renderOrder = 999
    scene.add(obj)
  }

  // ---- 灯光：柔和暖光，突出口腔内部结构 ----
  scene.add(new THREE.AmbientLight(0xffffff, 0.65))
  const hemi = new THREE.HemisphereLight(0xfff5ee, 0xc8b8a8, 0.6)
  scene.add(hemi)
  const dirMain = new THREE.DirectionalLight(0xfff0e0, 1.0)
  dirMain.position.set(2, 3, 4)
  scene.add(dirMain)
  const dirFill = new THREE.DirectionalLight(0xe8f0ff, 0.5)
  dirFill.position.set(-3, 1, 2)
  scene.add(dirFill)

  // ---- 辅助坐标网格（轻微）----
  // const grid = new THREE.GridHelper(4, 20, 0x334466, 0x223344)
  // grid.position.y = -1.2
  // scene.add(grid)

  // ---- 部件容器 ----
  // 上颌组（固定）
  const upperJaw = new THREE.Group()
  scene.add(upperJaw)
  // 下颌组（随开合旋转）
  const lowerJaw = new THREE.Group()
  lowerJaw.position.set(0, -0.55, 0.1)
  scene.add(lowerJaw)

  // ==================== 头部半透明轮廓（侧面剖面感） ====================
  const headMat = new THREE.MeshPhongMaterial({
    color: 0xc8b4a0, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false,
  })
  const head = new THREE.Mesh(new THREE.SphereGeometry(1.35, 48, 32), headMat)
  head.scale.set(1, 0.9, 1.1)
  head.position.y = -0.05
  scene.add(head)
  // 剖面参考线（中线轮廓）
  const cutLineMat = new THREE.LineBasicMaterial({ color: 0xb8a898, transparent: true, opacity: 0.35 })
  const cutPts: THREE.Vector3[] = []
  for (let i = 0; i <= 40; i++) {
    const a = (i / 40) * Math.PI
    cutPts.push(new THREE.Vector3(Math.cos(a) * 1.3, Math.sin(a) * 1.15, 0))
  }
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(cutPts), cutLineMat))

  // ==================== 上颚（硬腭）：拱形穹顶 ====================
  const palateMat = new THREE.MeshPhongMaterial({
    color: 0xe0859a, transparent: true, opacity: 0.6, side: THREE.DoubleSide, depthWrite: false, shininess: 20,
  })
  const palate = new THREE.Mesh(new THREE.SphereGeometry(0.95, 48, 24, 0, Math.PI * 2, 0, Math.PI * 0.55), palateMat)
  palate.position.set(0, 0.42, -0.05)
  palate.scale.set(1, 0.62, 1)
  upperJaw.add(palate)
  // 硬腭纹路
  const ridgeMat = new THREE.LineBasicMaterial({ color: 0xc86078, transparent: true, opacity: 0.45 })
  const ridgePts: THREE.Vector3[] = []
  for (let i = 0; i <= 30; i++) {
    const a = (i / 30) * Math.PI * 0.9 - Math.PI * 0.45
    ridgePts.push(new THREE.Vector3(Math.sin(a) * 0.9, 0.42, Math.cos(a) * 0.9 * 0.35))
  }
  const ridgeLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(ridgePts), ridgeMat)
  upperJaw.add(ridgeLine)

  // ==================== 软腭（可下垂，鼻音打开通道） ====================
  const velumMat = new THREE.MeshPhongMaterial({
    color: 0xd86078, transparent: true, opacity: 0.75, side: THREE.DoubleSide,
  })
  const velum = new THREE.Mesh(new THREE.SphereGeometry(0.4, 32, 16, 0, Math.PI * 2, Math.PI * 0.45, Math.PI * 0.55), velumMat)
  velum.position.set(0, 0.35, -0.75)
  velum.scale.set(0.7, 1, 0.55)
  upperJaw.add(velum)
  // 悬雍垂（小舌）
  const uvulaMat = new THREE.MeshPhongMaterial({ color: 0xc85068 })
  const uvula = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.2, 12), uvulaMat)
  uvula.position.set(0, 0.28, -0.78)
  upperJaw.add(uvula)

  // ==================== 鼻腔（鼻音通道，鼻音时气流由此流出） ====================
  const nosePath = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 0.78, 0.5),
    new THREE.Vector3(0, 0.9, 0),
    new THREE.Vector3(0, 0.85, -0.55),
  ])
  const noseGeom = new THREE.TubeGeometry(nosePath, 24, 0.1, 12, false)
  const noseMat = new THREE.MeshPhongMaterial({
    color: 0x7f9cc0, transparent: true, opacity: 0.5, side: THREE.DoubleSide, depthWrite: false,
  })
  const nose = new THREE.Mesh(noseGeom, noseMat)
  upperJaw.add(nose)

  // ==================== 上牙齿：门牙 + 两侧臼齿 ====================
  const teethMat = new THREE.MeshPhongMaterial({ color: 0xece0cc, shininess: 60 })
  const upperTeeth = new THREE.Group()
  upperJaw.add(upperTeeth)
  for (let i = -2; i <= 2; i++) {
    const incisor = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.16, 0.06), teethMat)
    incisor.position.set(i * 0.09, 0.16, 0.45 + Math.abs(i) * 0.015)
    incisor.rotation.z = i * 0.08
    upperTeeth.add(incisor)
  }
  // 上臼齿
  for (let i = 1; i <= 3; i++) {
    for (const side of [-1, 1]) {
      const molar = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.12, 0.08), teethMat)
      molar.position.set(side * (0.3 + i * 0.12), 0.14, 0.3 - i * 0.04)
      molar.rotation.z = side * 0.3
      molar.rotation.y = side * 0.2
      upperTeeth.add(molar)
    }
  }

  // ==================== 下颌骨 + 下牙齿 ====================
  const mandibleMat = new THREE.MeshPhongMaterial({
    color: 0x8f4052, transparent: true, opacity: 0.45, side: THREE.DoubleSide,
  })
  const mandible = new THREE.Mesh(new THREE.SphereGeometry(0.85, 40, 20, 0, Math.PI * 2, Math.PI * 0.45, Math.PI * 0.55), mandibleMat)
  mandible.position.y = 0.12
  mandible.scale.set(1, 0.6, 1)
  lowerJaw.add(mandible)

  const lowerTeeth = new THREE.Group()
  lowerJaw.add(lowerTeeth)
  for (let i = -2; i <= 2; i++) {
    const incisor = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.15, 0.06), teethMat)
    incisor.position.set(i * 0.09, 0.1, 0.42 + Math.abs(i) * 0.015)
    incisor.rotation.z = i * 0.08
    lowerTeeth.add(incisor)
  }
  for (let i = 1; i <= 3; i++) {
    for (const side of [-1, 1]) {
      const molar = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.11, 0.08), teethMat)
      molar.position.set(side * (0.3 + i * 0.12), 0.08, 0.26 - i * 0.04)
      molar.rotation.z = side * 0.3
      molar.rotation.y = side * 0.2
      lowerTeeth.add(molar)
    }
  }

  // ==================== 舌头：三段球体拼成扁长舌形（舌尖/舌中/舌根独立驱动） ====================
  const tongueMat = new THREE.MeshPhongMaterial({
    color: 0xd45068, transparent: true, opacity: 0.95, shininess: 30,
  })
  // 舌尖（圆润、可翘起，对应 d/t/n/l、zh/ch/sh、j/q/x 等舌位）
  const tongueTipMesh = new THREE.Mesh(new THREE.SphereGeometry(0.2, 24, 16), tongueMat)
  tongueTipMesh.scale.set(1, 0.55, 0.9)
  tongueTipMesh.position.set(0.42, -0.38, 0.55)
  lowerJaw.add(tongueTipMesh)
  // 舌中
  const tongueMidMesh = new THREE.Mesh(new THREE.SphereGeometry(0.27, 24, 16), tongueMat)
  tongueMidMesh.scale.set(1, 0.55, 0.9)
  tongueMidMesh.position.set(0, -0.4, -0.02)
  lowerJaw.add(tongueMidMesh)
  // 舌根（贴近咽喉，对应 g/k/h 舌根音）
  const tongueBackMesh = new THREE.Mesh(new THREE.SphereGeometry(0.24, 24, 16), tongueMat)
  tongueBackMesh.scale.set(1, 0.55, 0.9)
  tongueBackMesh.position.set(-0.42, -0.36, -0.55)
  lowerJaw.add(tongueBackMesh)

  // ==================== 嘴唇（上下唇，随开合与圆展变化） ====================
  const lipMat = new THREE.MeshPhongMaterial({ color: 0xc84860, shininess: 40 })
  const upperLip = new THREE.Mesh(new THREE.TorusGeometry(0.55, 0.09, 16, 40, Math.PI * 0.7), lipMat)
  upperLip.position.set(0, 0.12, 0.72)
  upperLip.rotation.set(Math.PI / 2, 0, Math.PI / 2)
  upperLip.scale.z = 0.85
  upperJaw.add(upperLip)
  const lowerLip = new THREE.Mesh(new THREE.TorusGeometry(0.55, 0.09, 16, 40, Math.PI * 0.7), lipMat)
  lowerLip.position.set(0, -0.12, 0.72)
  lowerLip.rotation.set(Math.PI / 2, 0, Math.PI / 2)
  lowerLip.scale.z = 0.85
  lowerJaw.add(lowerLip)

  // ==================== 气流粒子（从喉部向口外喷出，鼻音时部分走鼻腔） ====================
  const particleCount = 300
  const positions = new Float32Array(particleCount * 3)
  const velocities = new Float32Array(particleCount * 3)
  for (let i = 0; i < particleCount; i++) {
    resetParticle(i)
  }
  function resetParticle(i: number) {
    positions[i * 3] = (Math.random() - 0.5) * 0.4
    positions[i * 3 + 1] = -0.55 + (Math.random() - 0.5) * 0.2
    positions[i * 3 + 2] = -0.8 - Math.random() * 0.4
    velocities[i * 3] = (Math.random() - 0.5) * 0.3
    velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.2
    velocities[i * 3 + 2] = 0.4 + Math.random() * 0.5
  }
  const particlesGeom = new THREE.BufferGeometry()
  particlesGeom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  const particlesMat = new THREE.PointsMaterial({
    color: 0x3f7fc0, size: 0.05, transparent: true, opacity: 0.85, depthWrite: false,
  })
  const particles = new THREE.Points(particlesGeom, particlesMat)
  scene.add(particles)

  // ==================== 控制器 ====================
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 1.5
  controls.maxDistance = 8
  controls.target.set(0, -0.15, 0)

  // ==================== 动画循环 ====================
  let time = 0
  let rafId = 0
  // 当前姿态（线性插值逼近目标）
  const current = {
    jaw: 0.3, lipSpread: 0.3, lipRound: 0.1, velum: 0,
    tipX: 0, tipY: 0, midY: 0, backY: 0, backX: 0,
    airflow: 0.4,
  }

  function animate() {
    rafId = requestAnimationFrame(animate)
    time += 0.016
    const pose = currentPose.value

    // ---- 平滑逼近目标姿态 ----
    const k = 0.06
    current.jaw += (pose.jaw - current.jaw) * k
    current.lipSpread += (pose.lipSpread - current.lipSpread) * k
    current.lipRound += (pose.lipRound - current.lipRound) * k
    current.velum += (pose.velum - current.velum) * k
    current.tipX += (pose.tongueTip.x - current.tipX) * k
    current.tipY += (pose.tongueTip.y - current.tipY) * k
    current.midY += (pose.tongueMid.y - current.midY) * k
    current.backY += (pose.tongueBack.y - current.backY) * k
    current.backX += (pose.tongueBack.x - current.backX) * k
    current.airflow += (pose.airflow - current.airflow) * k

    // ---- 下颌开合（绕后方关节旋转） ----
    lowerJaw.rotation.x = -current.jaw * 0.5

    // ---- 舌头：三段球体独立驱动，模拟舌形弯曲 ----
    tongueTipMesh.position.set(current.tipX + 0.42, current.tipY - 0.38, 0.55)
    tongueMidMesh.position.set(0, current.midY - 0.4, -0.02)
    tongueBackMesh.position.set(current.backX - 0.42, current.backY - 0.36, -0.55)
    // 舌尖抬起时舌体微微上翘、收窄（翘舌/舌面音）
    const lift = (current.tipY + 0.18) / 0.3
    tongueTipMesh.scale.set(1, 0.55 - lift * 0.1, 0.9)
    tongueMidMesh.scale.set(1, 0.55 - lift * 0.08, 0.9)

    // ---- 嘴唇：开合 + 圆展 ----
    const lipOpen = current.jaw * 0.22
    upperLip.position.y = 0.12 + lipOpen * 0.15
    lowerLip.position.y = -0.12 - lipOpen * 0.35
    // 圆唇：横向收拢、向前凸；展唇：横向拉伸
    const roundScale = 1 - current.lipRound * 0.5
    upperLip.scale.set(roundScale * (1 + current.lipSpread * 0.3), roundScale * 0.9, 0.85 + current.lipRound * 0.5)
    lowerLip.scale.set(roundScale * (1 + current.lipSpread * 0.3), roundScale * 0.9, 0.85 + current.lipRound * 0.5)
    // 圆唇时嘴唇前移
    upperLip.position.z = 0.72 + current.lipRound * 0.25
    lowerLip.position.z = 0.72 + current.lipRound * 0.25

    // ---- 软腭：鼻音时下垂，打开鼻腔通道 ----
    velum.rotation.x = current.velum * 0.9
    velum.position.y = 0.35 - current.velum * 0.25
    uvula.rotation.x = current.velum * 0.9
    uvula.position.y = 0.28 - current.velum * 0.3

    // ---- 气流粒子：从喉部喷向口外；鼻音时部分从鼻腔通道飘出 ----
    const speedFactor = 0.6 + current.airflow * 1.6
    const posAttr = particlesGeom.attributes.position as THREE.BufferAttribute | undefined
    if (!posAttr) return
    const pos = posAttr.array as Float32Array
    const nasalOn = current.velum > 0.5
    for (let i = 0; i < particleCount; i++) {
      const useNasal = nasalOn && i % 3 === 0
      const idx = i * 3
      pos[idx] = (pos[idx] ?? 0) + (velocities[idx] ?? 0) * speedFactor
      pos[idx + 1] = (pos[idx + 1] ?? 0) + ((velocities[idx + 1] ?? 0) + (useNasal ? 0.55 : 0)) * speedFactor
      pos[idx + 2] = (pos[idx + 2] ?? 0) + (velocities[idx + 2] ?? 0) * speedFactor
      if (useNasal) {
        // 走鼻腔的粒子升到鼻腔高度后重新生成
        if ((pos[idx + 1] ?? 0) > 0.85) resetParticle(i)
      } else if ((pos[idx + 2] ?? 0) > 1.35) {
        resetParticle(i)
      }
    }
    posAttr.needsUpdate = true
    particlesMat.opacity = 0.35 + current.airflow * 0.45

    controls.update()
    renderer.render(scene, camera)
    labelRenderer.render(scene, camera)
  }
  animate()

  // 窗口缩放 / 侧栏折叠都会改变容器宽度：用 ResizeObserver 跟随。
  // 原先尺寸与相机 aspect 只在初始化时算一次，折叠侧栏或改窗口后 3D 会与卡片错位。
  const applySize = () => {
    const w = container.clientWidth
    const h = container.clientHeight
    if (!w || !h) return
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
    labelRenderer.setSize(w, h)
  }
  const ro = new ResizeObserver(applySize)
  ro.observe(container)

  // 返回清理函数（组件卸载时释放资源）
  return () => {
    ro.disconnect()
    cancelAnimationFrame(rafId)
    renderer.dispose()
    controls.dispose()
    if (renderer.domElement.parentNode === container) {
      container.removeChild(renderer.domElement)
    }
    if (labelRenderer.domElement.parentNode === container) {
      container.removeChild(labelRenderer.domElement)
    }
  }
}

// 声调曲线对比图
// ---------------------------------------------------------------------------
// 三条硬约束（都有来由，改之前先看）：
//
//   1) 标准曲线**只能来自后端**。拿不到就不画、图例也一起去掉，并显式说明原因。
//      前端按 detectedTone 现编一条再标「标准发音」= 假分，违反 SRS「禁止假分」。
//
//   2) 横轴优先用后端**逐帧时间戳**。A（2026-10-11）说时间戳「我还没做」，
//      将来会按帧返回；并且明确「分析的时候的帧率可能会变」。
//      所以**不能写死帧长**——512/16000 = 32ms 只是标称值，实际帧距可能不匀。
//      没有时间戳时退化为帧序号并如实标注，不把帧序号冒充「时间」。
//
//   3) 屏蔽静音 + 数据平滑走 src/utils/toneCurve.ts（第 6 周工具）。
//      注意：ECharts 的 series.smooth 只是**渲染**平滑、数值不变，不能替代数据平滑。

/** 声调图横轴：时间戳 → 平均帧距 → 帧序号，依次退化，并如实给出轴名与单位 */
function buildToneAxis(
  frameCount: number,
  timestamps: number[] | undefined,
  duration: number,
): { labels: number[]; axisName: string; unit: 's' | '帧' } {
  // ① 后端给了逐帧时间戳 —— 最优，直接用它
  if (Array.isArray(timestamps) && frameCount > 0 && timestamps.length === frameCount) {
    return { labels: timestamps, axisName: '时间 (s)', unit: 's' }
  }
  // ② 没有时间戳但有总时长 —— 按平均帧距近似，轴名如实写「按平均帧距」
  if (duration > 0 && frameCount > 1) {
    const step = duration / frameCount
    return {
      labels: Array.from({ length: frameCount }, (_, i) => Number((i * step).toFixed(2))),
      axisName: '时间 (s · 按平均帧距)',
      unit: 's',
    }
  }
  // ③ 都没有 —— 帧序号，不是时间，不冒充
  return {
    labels: Array.from({ length: frameCount }, (_, i) => i),
    axisName: '帧序号',
    unit: '帧',
  }
}

function initToneChart() {
  const chart = trackChart(toneChartRef.value)
  if (!chart) return

  const audio = assessment.value?.audioAnalysis
  const rawF0: number[] = audio?.f0 || []
  const voiced: boolean[] | undefined = audio?.voiced_flag
  const voicedProbs: number[] = audio?.voiced_probs || []

  // 屏蔽静音 → null（ECharts 遇 null 断线），再在连续有声段内做数据平滑。
  // 走第 6 周工具；顺序不可颠倒（先平滑，再谈归一化）。
  const userF0 = smoothSeries(maskByVoiced(rawF0, voiced))

  // 标准曲线：只认真实数据。拿不到就什么都不画 —— 不再按 detectedTone 现编一条
  const standardRaw: number[] = audio?.standardF0 || []
  const hasStandard =
    standardRaw.length > 0 && standardRaw.some(v => typeof v === 'number' && v > 0)

  const { labels, axisName, unit } = buildToneAxis(
    rawF0.length,
    audio?.timestamps,
    audio?.duration || 0,
  )

  // 系列：用户曲线必有；标准曲线只在后端真的给了才画（禁止假分）
  const series: any[] = [
    {
      name: '您的发音',
      type: 'line',
      data: userF0,
      connectNulls: false, // 静音处断线
      smooth: true,
      lineStyle: { color: '#409eff', width: 3 },
      itemStyle: { color: '#409eff' },
      symbol: 'circle',
      symbolSize: 6,
    },
  ]
  if (hasStandard) {
    // 长度不同时按公共长度截断，不做最近邻重排那种「伪对齐」
    series.push({
      name: '标准发音',
      type: 'line',
      data: smoothSeries(maskByVoiced(standardRaw)).slice(0, labels.length),
      connectNulls: false,
      smooth: true,
      lineStyle: { color: '#67c23a', width: 3, type: 'dashed' },
      itemStyle: { color: '#67c23a' },
      symbol: 'none',
    })
  }

  chart.setOption({
    title: { text: '声调曲线对比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'axis',
      // 显示：横轴值（时间/帧）+ 频率 + 有声标记 + voiced_prob（若有）
      formatter: (params: any) => {
        // params 为数组：0=您的发音,1=标准发音（视图序列顺序）
        const p = Array.isArray(params) ? params[0] : params
        const idx = p?.dataIndex ?? 0
        const val = p?.data ?? null
        const isVoiced = voiced?.[idx]
        const prob = voicedProbs[idx]
        const voicedTxt = typeof isVoiced === 'boolean' ? (isVoiced ? '有声' : '无声') : ''
        const probTxt = (typeof prob === 'number') ? `<br/>voiced_prob: ${prob.toFixed(2)}` : ''
        const head = unit === 's' ? `时间: ${labels[idx]} s` : `第 ${idx} 帧`
        const freqTxt = typeof val === 'number' ? `${val.toFixed(1)} Hz` : '—'
        return `${head}<br/>频率: ${freqTxt}<br/>${voicedTxt}${probTxt}`
      }
    },
    // 没有标准曲线时图例也不留它：不能让图例承诺一条不存在的线
    legend: { data: hasStandard ? ['您的发音', '标准发音'] : ['您的发音'], bottom: 0 },
    xAxis: { type: 'category', data: labels, name: axisName },
    yAxis: { type: 'value', name: '频率 (Hz)' },
    series,
    grid: { left: 60, right: 30, top: 40, bottom: 40 },
  })
}

// 声谱图（基于后端 MFCC 的倒谱强度图）
// ⚠️ 这里画的**不是**「某频率在某时刻的能量」：
//    后端给的是 librosa 的 MFCC（倒谱系数），不是 STFT 幅度谱。
//    所以纵轴是「倒谱系数序号」，文案也改准了；真要画声谱图需要后端补 STFT。
//    另外用整幅数据的峰值做归一化 —— 系数直接 clamp 到 1 会让整片过饱和发白。
function initSpectrogram() {
  if (!spectrogramRef.value) return
  const canvas = spectrogramRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // 高分屏：位图按 DPR 放大，CSS 尺寸不变，否则 250 个物理像素被拉伸到 400+ 会糊
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const cssW = Math.round(canvas.clientWidth || 500)
  const cssH = 200
  canvas.width = Math.round(cssW * dpr)
  canvas.height = Math.round(cssH * dpr)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const w = cssW
  const h = cssH

  const timeSteps = 100
  const freqBins = 80
  const mfcc = assessment.value?.audioAnalysis?.mfcc || []
  const hasMfcc = mfcc.length > 0 && (mfcc[0]?.length ?? 0) > 0

  // 无数据：清空后直接返回，空态由模板负责，不涂任何颜色
  ctx.clearRect(0, 0, w, h)
  if (!hasMfcc) return

  // 峰值归一化 + γ 压缩
  // ⚠️ 只做峰值归一化不够：MFCC 的 c0（第 0 阶）量级比其他阶大十几到几十倍，
  //    峰值卡在 c0 上，高阶系数会被整个压成深蓝、看不出结构。
  //    γ = 0.45 < 1 用来提升小值的可见度，同时保留"谁大谁小"的顺序，不改变可比性。
  let peak = 0
  for (const row of mfcc) {
    for (const v of row) {
      const a = Math.abs(v)
      if (a > peak) peak = a
    }
  }
  const scale = peak > 0 ? peak : 1
  const GAMMA = 0.45

  for (let t = 0; t < timeSteps; t++) {
    for (let f = 0; f < freqBins; f++) {
      const mfccIdx = Math.floor((f / freqBins) * mfcc.length)
      const timeIdx = Math.floor((t / timeSteps) * (mfcc[0]?.length || 1))
      const raw = Math.abs(mfcc[mfccIdx]?.[timeIdx] || 0)
      const ratio = Math.max(0, Math.min(1, raw / scale))
      const energy = Math.pow(ratio, GAMMA)

      // 颜色映射：深蓝→青→绿→黄→红
      const r = Math.floor(energy < 0.5 ? energy * 2 * 255 : 255)
      const g = Math.floor(energy < 0.5 ? energy * 2 * 255 : (1 - energy) * 2 * 255)
      const b = Math.floor(energy < 0.5 ? 255 : (1 - energy) * 2 * 255)

      ctx.fillStyle = `rgb(${r},${g},${b})`
      ctx.fillRect((t / timeSteps) * w, (1 - f / freqBins) * h, w / timeSteps + 1, h / freqBins + 1)
    }
  }

  // 轴说明：纵轴是倒谱系数序号，不是频率
  ctx.fillStyle = '#909399'
  ctx.font = '11px sans-serif'
  ctx.fillText('时间 →', w - 50, h - 5)
  ctx.save()
  ctx.translate(12, h / 2)
  ctx.rotate(-Math.PI / 2)
  ctx.fillText('倒谱系数 →', -32, 0)
  ctx.restore()
}

// 共振峰轨迹图 (F1-F2空间)
function initFormantChart() {
  const chart = trackChart(formantChartRef.value)
  if (!chart) return

  const f1Data = assessment.value?.audioAnalysis?.f1 || []
  const f2Data = assessment.value?.audioAnalysis?.f2 || []

  // 采样减少点数
  const step = Math.max(1, Math.floor(f1Data.length / 30))
  const scatterData: number[][] = []
  for (let i = 0; i < f1Data.length; i += step) {
    scatterData.push([f2Data[i] ?? 0, f1Data[i] ?? 0])
  }

  // 标准元音位置 (F2, F1)
  const standardVowels: [string, number[]][] = [
    ['i', [2400, 280]], ['e', [2100, 400]], ['a', [1100, 750]],
    ['o', [800, 500]], ['u', [600, 300]],
  ]

  chart.setOption({
    title: { text: '共振峰轨迹图 (F1-F2)', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      formatter: (p: any) => {
        if (p.seriesIndex === 0) return `F1: ${p.data[1].toFixed(0)} Hz<br/>F2: ${p.data[0].toFixed(0)} Hz`
        return p.name
      },
    },
    xAxis: { type: 'value', name: 'F2 (Hz)', inverse: true, min: 500, max: 2500 },
    yAxis: { type: 'value', name: 'F1 (Hz)', inverse: true, min: 200, max: 900 },
    series: [
      {
        name: '您的发音',
        type: 'line',
        data: scatterData,
        smooth: true,
        lineStyle: { color: '#409eff', width: 3 },
        itemStyle: { color: '#409eff' },
        symbolSize: 6,
      },
      {
        name: '标准元音',
        type: 'scatter',
        data: standardVowels.map(v => ({ value: v[1], name: v[0] })),
        symbolSize: 14,
        itemStyle: { color: '#67c23a' },
        label: { show: true, formatter: '{b}', position: 'right', fontSize: 12 },
      },
    ],
    legend: { data: ['您的发音', '标准元音'], bottom: 0 },
    grid: { left: 60, right: 40, top: 40, bottom: 40 },
  })
}

// 能量包络图
function initEnergyChart() {
  const chart = trackChart(energyChartRef.value)
  if (!chart) return

  const energy = assessment.value?.audioAnalysis?.energy || []
  const duration = assessment.value?.audioAnalysis?.duration || 0
  const n = energy.length

  // 横轴与声调图用同一套退化规则：有真实总时长才换算成秒，否则如实显示帧序号。
  // 原先是 `duration || 1.5` —— 没有时长就编一个 1.5 秒，等于编时间轴。
  const timed = duration > 0 && n > 1
  const labels = Array.from(
    { length: n },
    (_, i) => (timed ? Number(((i / n) * duration).toFixed(2)) : i),
  )

  chart.setOption({
    title: { text: '能量包络图', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'axis',
      formatter: (p: any) => {
        const item = Array.isArray(p) ? p[0] : p
        const i = item?.dataIndex ?? 0
        const head = timed ? `时间: ${labels[i]} s` : `第 ${i} 帧`
        const val = typeof item?.data === 'number' ? item.data.toFixed(3) : '—'
        return `${head}<br/>能量(RMS): ${val}`
      },
    },
    xAxis: { type: 'category', data: labels, name: timed ? '时间 (s)' : '帧序号' },
    // 不再硬编码 0–1：后端是 librosa RMS，真实量级约 0.01–0.2，
    // 写死 max:1 会让曲线贴在底部，看不出包络形状。
    yAxis: { type: 'value', name: '能量 (RMS)', min: 0 },
    series: [{
      type: 'line',
      data: energy,
      smooth: true,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64,158,255,0.6)' },
          { offset: 1, color: 'rgba(64,158,255,0.05)' },
        ]),
      },
      lineStyle: { color: '#409eff', width: 2 },
      itemStyle: { color: '#409eff' },
      symbol: 'none',
    }],
    grid: { left: 60, right: 30, top: 40, bottom: 40 },
  })
}

function scoreColorOf(score: number) {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

const scoreColor = computed(() => scoreColorOf(assessment.value?.score || 0))
// 恢复出来的「上次练习结果」也沿用同一套分数配色
const lastScoreColor = computed(() => scoreColorOf(lastRecord.value?.score || 0))

// 数据图表统一渲染（声调/声谱/共振峰/能量），重绘前已做 dispose 防护
function renderDataCharts() {
  initToneChart()
  initSpectrogram()
  initFormantChart()
  initEnergyChart()
}

// 3D 场景清理函数（卸载时调用）
let disposeThree: (() => void) | null = null

onMounted(async () => {
  // 内存里没有本次分析结果（刷新 / 直开本页 / 上次分析失败）→ 从后端学习记录里恢复
  if (!assessment.value) {
    void restoreLastRecord()
  }

  // 等待DOM渲染完成后再初始化图表
  await nextTick()
  setTimeout(() => {
    renderDataCharts()
    disposeThree = initThreeScene() ?? null
  }, 100)
})

onUnmounted(() => {
  disposeThree?.()
  disposeThree = null
  // 图表实例统一 dispose：否则离开页面后实例仍持有 canvas 与 zrender 内部监听；
  // 而图表容器挂在 v-if 上，容器被摘掉后旧实例会变成再也找不到的孤儿（演示中反复重录会累积）。
  for (const chart of liveCharts) chart.dispose()
  liveCharts.clear()
  stopAudio()
})

// 当后端分析结果到达（可能晚于组件挂载）时重绘数据图表，避免空白
watch(
  () => assessment.value?.audioAnalysis,
  (val) => {
    if (val && (val.f0?.length || val.energy?.length || val.mfcc?.length)) {
      nextTick(() => renderDataCharts())
    }
  }
)
</script>

<template>
  <div class="feedback-view">
    <!-- 没有内存结果时的恢复流程：分析结果只保存在内存里，刷新页面 / 直接打开本页 /
         上一次分析失败都会走到这里。三种情况分别是「请求中」「该关无记录」「接口失败」，
         绝不留空白页（这是「点了分析没反馈」的真实原因）。文案统一走 P09 文案位。 -->
    <PageState
      v-if="!assessment && (restoreState === 'idle' || restoreState === 'loading')"
      state="loading"
      :copy="copy"
      class="card-block"
    />

    <PageState
      v-else-if="!assessment && restoreState === 'error'"
      state="error"
      :copy="copy"
      :detail="restoreError"
      class="card-block"
      @action="restoreLastRecord"
    />

    <!-- 有记录：渲染上次练习结果（分数 + 文字反馈，图表无法恢复） -->
    <div v-else-if="!assessment && restoreState === 'done' && lastRecord" class="card-block last-result">
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

      <div class="last-result-metrics">
        <div class="score-item"><span>准确度</span><el-progress :percentage="Math.round(lastRecord.accuracy)" color="#409eff" /></div>
        <div class="score-item"><span>流利度</span><el-progress :percentage="Math.round(lastRecord.fluency)" color="#67c23a" /></div>
        <div class="score-item"><span>发音</span><el-progress :percentage="Math.round(lastRecord.pronunciation)" color="#e6a23c" /></div>
      </div>

      <p v-if="lastRecord.feedback" class="last-result-feedback">{{ lastRecord.feedback }}</p>

      <div class="last-result-actions">
        <el-button type="primary" :loading="isPlaying" @click="playLastRecord">播放上次录音</el-button>
        <el-button @click="router.push(`/learn/${unitId}`)">回关卡重新录音</el-button>
        <el-button @click="router.push('/archive')">看我的档案</el-button>
      </div>
    </div>

    <!-- 没有任何该关记录（以及其它兜底情况）：给出回关卡重录的入口 -->
    <div v-else-if="!assessment" class="card-block no-result">
      <PageState state="empty" :copy="copy" @action="router.push(`/learn/${unitId}`)" />
      <div class="no-result-actions">
        <el-button @click="router.push('/test')">去检测中心</el-button>
        <el-button @click="router.push('/learn')">看全部 30 关</el-button>
      </div>
    </div>

    <!-- 录音质量 / 结论 / 可靠性 / 边界 -->
    <div v-if="assessment" class="result-meta card-block">
      <el-alert
        v-if="assessment && !assessment.evaluable"
        type="warning"
        :title="assessment.quality?.summary || '录音质量不达标'"
        description="当前录音无法可靠评价。请按下方提示调整环境后重录。"
        show-icon
        :closable="false"
      />
      <div v-if="assessment && !assessment.evaluable" class="unevaluable-actions">
        <el-button type="danger" @click="router.push(`/learn/${unitId}`)">返回单元重录</el-button>
        <el-button @click="router.push(`/test?unit=${unitId}`)">在检测中心重录</el-button>
      </div>
      <template v-else-if="assessment">
        <p class="headline-label">当前任务结论</p>
        <h2 class="headline">{{ assessment.headline || assessment.feedback[0]?.phenomenon || '分析完成' }}</h2>
        <el-tag :type="assessment.reliability === 'reliable' ? 'success' : assessment.reliability === 'reference_only' ? 'warning' : 'info'">
          {{ { reliable: '结果可靠', reference_only: '仅供参考', not_available: '暂不评价' }[assessment.reliability] }}
        </el-tag>
        <p class="reliability-note">{{ assessment.reliabilityNote }}</p>
      </template>

      <div v-if="assessment?.quality?.items?.length" class="quality-list">
        <h4>录音质量</h4>
        <div v-for="item in assessment.quality.items" :key="item.key" class="quality-item" :class="item.status">
          <strong>{{ item.label }}</strong> — {{ item.message }}
        </div>
      </div>

      <el-alert v-if="assessment?.boundary?.statement" type="info" :title="assessment.boundary.statement" show-icon :closable="false" class="boundary" />
    </div>

    <!-- 四步反馈（仅可评价时） -->
    <div v-if="assessment?.evaluable && assessment?.feedback?.length" class="four-step card-block">
      <h3>练习建议（四步反馈）</h3>
      <div v-for="(item, idx) in assessment.feedback" :key="idx" class="step-item" :class="item.type">
        <p><strong>① 现象</strong>{{ item.phenomenon || item.message }}</p>
        <p><strong>② 可能环节</strong>{{ item.link || item.detail }}</p>
        <p><strong>③ 可感知提示</strong>{{ item.hint }}</p>
        <p><strong>④ 安全短练习</strong>{{ item.practice || item.improvement }}</p>
      </div>
    </div>

    <!-- 综合评分（辅参考，非主结论） -->
    <div v-if="assessment?.evaluable" class="score-section">
      <div class="score-ring">
        <el-progress type="circle" :percentage="Math.round(assessment?.score || 0)" :color="scoreColor" :width="140" :stroke-width="12">
          <template #default="{ percentage }">
            <div class="score-inner">
              <span class="score-number">{{ percentage }}</span>
              <span class="score-label">综合评分</span>
            </div>
          </template>
        </el-progress>
      </div>
      <div class="score-detail">
        <div class="score-item"><span>准确度</span><el-progress :percentage="Math.round(assessment?.accuracy || 0)" :color="'#409eff'" /></div>
        <div class="score-item"><span>流利度</span><el-progress :percentage="Math.round(assessment?.fluency || 0)" :color="'#67c23a'" /></div>
        <div class="score-item"><span>发音</span><el-progress :percentage="Math.round(assessment?.pronunciation || 0)" :color="'#e6a23c'" /></div>
      </div>
    </div>

    <!-- 音素级分析（深度学习识别结果） -->
    <div class="phoneme-section" v-if="assessment?.evaluable && assessment?.audioAnalysis?.phonemes?.length">
      <h3>音素级分析 <small>基于 Wav2Vec2 深度学习模型识别</small></h3>
      <div class="phoneme-list">
        <div v-for="(p, idx) in assessment!.audioAnalysis!.phonemes" :key="idx" class="phoneme-item" :class="p.score >= 80 ? 'good' : (p.score >= 60 ? 'warn' : 'bad')">
          <div class="phoneme-name">{{ p.phoneme }}</div>
          <div class="phoneme-compare">
            <span class="expected">目标：{{ p.expected }}</span>
            <span class="arrow">→</span>
            <span class="detected">识别：{{ p.detected }}</span>
          </div>
          <div class="phoneme-score">
            <el-progress :percentage="Math.round(p.score)" :stroke-width="10" :color="p.score >= 80 ? '#67c23a' : (p.score >= 60 ? '#e6a23c' : '#f56c6c')" />
          </div>
          <p class="phoneme-feedback">{{ p.feedback }}</p>
        </div>
      </div>
      <div class="phoneme-summary" v-if="assessment?.audioAnalysis?.recognizedText">
        <span class="label">识别文本：</span>
        <span class="value">{{ assessment!.audioAnalysis!.recognizedText }}</span>
        <span class="label">识别声调：</span>
        <span class="value">第{{ assessment!.audioAnalysis!.detectedTone || '（依据F0判定）' }}声</span>
      </div>
    </div>

    <!-- 声调曲线 + 3D动画（仅可评价时展示） -->
    <div v-if="assessment?.evaluable && assessment?.audioAnalysis" class="analysis-row">
      <div class="chart-card">
        <div ref="toneChartRef" class="chart-container"></div>
        <p v-if="toneStandardMissing" class="chart-desc">
          本次没有标准声调曲线（后端未提供），图中只显示你自己的音高走势。
        </p>
      </div>
      <div class="three-card">
        <h4>3D发音动画 <small>（剖面示意 · 拖拽旋转 · 滚轮缩放 · 悬停部位查看说明）</small></h4>
        <!-- 预检兜底：不支持 WebGL2 时给看得懂的解释，而不是留一个空框 -->
        <div v-if="threeFailed" class="three-fallback">
          <p class="three-fallback-title">这台设备暂时显示不了 3D 演示</p>
          <p class="three-fallback-desc">
            浏览器或显卡不支持 WebGL2（也可能是关闭了硬件加速，或正通过远程桌面演示）。
            这不影响上面的分数与图表，换个浏览器 / 打开硬件加速 / 换台机器即可看到。
          </p>
        </div>
        <div v-else ref="threeContainerRef" class="three-container"></div>
      </div>
    </div>

    <!-- 声谱图 + 共振峰 + 能量图（仅可评价时展示） -->
    <div v-if="assessment?.evaluable && assessment?.audioAnalysis" class="analysis-row three-col">
      <div class="chart-card">
        <h4>声谱图</h4>
        <canvas v-if="hasSpectrogramData" ref="spectrogramRef" class="spectrogram-canvas"></canvas>
        <p v-else class="chart-desc">本次没有频谱数据（后端未返回 MFCC），无法绘制声谱图。</p>
        <!-- 文案改准：后端给的是 MFCC（倒谱系数），不是某频率上的能量 -->
        <p v-if="hasSpectrogramData" class="chart-desc">
          颜色越亮表示该倒谱分量的强度越大（MFCC，不是物理频率上的能量）
        </p>
      </div>
      <div class="chart-card">
        <div ref="formantChartRef" class="chart-container"></div>
      </div>
      <div class="chart-card">
        <h4 v-if="!hasEnergyData">能量包络图</h4>
        <div v-if="hasEnergyData" ref="energyChartRef" class="chart-container"></div>
        <p v-else class="chart-desc">本次没有能量数据，无法绘制能量包络。</p>
      </div>
    </div>

    <!-- 反馈建议（兼容旧展示，四步反馈已在上方） -->
    <div v-if="false" class="feedback-section">
      <h3>改进建议</h3>
      <div class="feedback-list">
        <div v-for="(item, idx) in (assessment?.feedback || [])" :key="idx" class="feedback-item" :class="item.type">
          <el-icon v-if="item.type === 'error'" color="#f56c6c"><CircleCloseFilled /></el-icon>
          <el-icon v-else-if="item.type === 'warning'" color="#e6a23c"><WarningFilled /></el-icon>
          <el-icon v-else color="#409eff"><InfoFilled /></el-icon>
          <div>
            <strong>{{ item.message }}</strong>
            <p>{{ item.detail }}</p>
            <p class="improvement">💡 {{ item.improvement }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div v-if="assessment" class="action-bar">
      <el-button :icon="'Refresh'" size="large" @click="router.push(`/learn/${unitId}`)">再次录音</el-button>
      <el-button v-if="assessment?.evaluable" type="success" :icon="'VideoPlay'" size="large" @click="router.push(`/learn/${unitId}`)">开始练习</el-button>
      <el-button type="primary" plain size="large" @click="router.push('/archive')">保存到档案</el-button>
      <el-button :icon="'Back'" size="large" @click="router.push('/library')">返回发音库</el-button>
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
.last-result-metrics { display: flex; flex-direction: column; gap: 12px; margin-top: 20px; }
.last-result-feedback { margin: 16px 0 0; padding: 12px 16px; background: #f5f7fa; border-radius: 8px; font-size: 13px; color: #606266; }
.last-result-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
.card-block { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06); }
.headline-label { font-size: 13px; color: #909399; margin: 0; }
.headline { margin: 8px 0 12px; font-size: 20px; color: #303133; }
.reliability-note { font-size: 13px; color: #606266; margin-top: 8px; }
.quality-list { margin-top: 16px; }
.quality-item { font-size: 13px; padding: 6px 0; }
.quality-item.fail { color: #f56c6c; }
.four-step h3 { margin: 0 0 12px; }
.step-item { padding: 12px; margin-bottom: 8px; border-radius: 8px; background: #f5f7fa; font-size: 13px; }
.step-item.error { background: #fef0f0; }
.step-item.warning { background: #fdf6ec; }
.step-item p { margin: 4px 0; }
.boundary { margin-top: 12px; }
.unevaluable-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 12px; }
.score-section { background: white; border-radius: 12px; padding: 24px; display: flex; align-items: center; gap: 40px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.score-ring { flex-shrink: 0; }
.score-inner { text-align: center; }
.score-number { font-size: 36px; font-weight: 700; color: #303133; display: block; }
.score-label { font-size: 12px; color: #909399; }
.score-detail { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.score-item { display: flex; align-items: center; gap: 12px; }
.score-item span { width: 60px; font-size: 14px; color: #606266; }
.analysis-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.analysis-row.three-col { grid-template-columns: 1fr 1fr 1fr; }
.spectrogram-canvas { width: 100%; height: 200px; border-radius: 8px; background: #0a0a1a; }
.chart-desc { font-size: 11px; color: #909399; text-align: center; margin-top: 6px; }
.chart-card h4 { margin: 0 0 8px; font-size: 14px; color: #303133; }
.chart-card, .three-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.chart-container { width: 100%; height: 300px; }
.three-card { position: relative; }
.three-card h4 { margin: 0 0 8px; font-size: 14px; color: #303133; }
.three-card h4 small { font-size: 11px; color: #909399; font-weight: normal; }
.three-container { position: relative; width: 100%; height: 300px; border-radius: 8px; overflow: hidden; }
/* 3D 不可用时的兜底说明：占位高度与画布一致，避免布局跳动 */
.three-fallback {
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  height: 300px; padding: 0 24px; border-radius: 8px;
  background: #f5f7fa; border: 1px dashed #dcdfe6; text-align: center;
}
.three-fallback-title { margin: 0 0 8px; font-size: 14px; font-weight: 600; color: #606266; }
.three-fallback-desc { margin: 0; font-size: 12px; line-height: 1.8; color: #909399; }
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
.feedback-section { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.feedback-section h3 { margin: 0 0 16px; font-size: 16px; color: #303133; }
.feedback-list { display: flex; flex-direction: column; gap: 12px; }
.feedback-item { display: flex; gap: 12px; align-items: flex-start; padding: 16px; border-radius: 8px; background: #f5f7fa; }
.feedback-item.error { background: #fef0f0; }
.feedback-item.warning { background: #fdf6ec; }
.feedback-item.suggestion { background: #ecf5ff; }
.feedback-item strong { color: #303133; display: block; margin-bottom: 4px; }
.feedback-item p { margin: 2px 0; color: #606266; font-size: 13px; }
.improvement { color: #409eff !important; font-weight: 500; }
.action-bar { display: flex; justify-content: center; gap: 16px; padding: 16px 0; }
</style>