/**
 * 实时声学特征提取（FR-907）：纯计算与轻量状态机，供 RealtimeAcousticCanvas
 * 在 rAF 循环中调用，不触碰 Vue 响应式与网络。
 *
 * 基频用 pitchy（McLeod Pitch Method，NSDF）提取，输出 pitch + clarity。
 * 双门限判定（docs/f0展示修改测试版1.md §6.1）：主门限 clarity ≥ 0.82 且
 * rms ≥ 0.012 判有声；前 3 帧稳定有声后，rms ≥ 0.008、clarity ≥ 0.55 且
 * 与邻近轨迹连续的弱周期帧（嘎裂/气泡音尾段）延续显示（weak 标记，
 * 画布用较弱样式）；半音变化率 > 2.0 ST/10ms 的帧进入 3 帧观察缓冲，
 * 短暂偏离回原轨迹按毛刺留空，连续进入新平台才接纳新轨迹。
 * 平滑在半音域做「3 点中值 + EMA」，仅在连续有效段内使用，进缺口即清空。
 * 纵轴对数半音标度；有个人音域时五度按音域锚定（1 度=ST(fLo)、5 度=ST(fHi)）。
 */
import { PitchDetector } from 'pitchy'

/** 4096 点 @44.1/48kHz ≈ 85–93ms：覆盖 50Hz（下限）3 个周期 */
export const ANALYSIS_FFT_SIZE = 4096
/** 分析步长（ms）：与后端 Praat 轨一致（docs §6.1） */
export const ANALYSIS_STEP_MS = 10

/** 人声基频窗口与清浊判定门限（清辅音/噪声的 clarity 通常落到 0.2–0.6） */
export const F0_MIN_HZ = 50
export const F0_MAX_HZ = 500
export const CLARITY_GATE = 0.82
export const SILENCE_RMS_GATE = 0.012
/** 弱周期延续门限（主门限判有声满 3 帧后生效） */
export const WEAK_RMS_GATE = 0.008
export const WEAK_CLARITY_GATE = 0.55
/** 弱周期帧与邻近轨迹的连续性上限（半音） */
export const WEAK_CONTINUITY_ST = 3
/** 跳变观察：半音变化率阈值（ST/10ms）与观察帧数 */
export const JUMP_OBSERVE_ST_PER_10MS = 2.0
export const JUMP_OBSERVE_FRAMES = 3
export const CLIPPING_PEAK = 0.95

/** 展示音量偏轻的提示门限（仅 UI 文案，不影响有声判定） */
export const QUIET_RMS_HINT = 0.03

/* ------------------------------ 半音标度 ------------------------------ */

/** 以 55Hz（A1）为 0 点的半音值；Hz→半音、半音→Hz 互转 */
export function hzToSemitone(hz: number): number {
  return 12 * Math.log2(hz / 55)
}

export function semitoneToHz(st: number): number {
  return 55 * Math.pow(2, st / 12)
}

export interface PitchRangeHz {
  fLo: number
  fHi: number
}

/** 五度值 → 半音：按个人音域锚定（1 度=ST(fLo)、5 度=ST(fHi)，docs §6.1） */
export function rangeDegreeToSemitone(range: PitchRangeHz, degree: number): number {
  const lo = hzToSemitone(range.fLo)
  const hi = hzToSemitone(range.fHi)
  return lo + ((degree - 1) / 4) * (hi - lo)
}

/** 拼音声调符号 → 调号（关卡 pinyin 无声调符号时返回 null，不猜） */
const TONE_MARKS: Array<[RegExp, 1 | 2 | 3 | 4]> = [
  [/[āēīōūǖ]/, 1],
  [/[áéíóúǘ]/, 2],
  [/[ǎěǐǒǔǚ]/, 3],
  [/[àèìòùǜ]/, 4],
]

export type ToneValue = 1 | 2 | 3 | 4

export function toneOfPinyin(pinyin?: string | null): ToneValue | null {
  if (!pinyin) return null
  for (const [pattern, tone] of TONE_MARKS) {
    if (pattern.test(pinyin)) return tone
  }
  return null
}

/**
 * 调型的五度目标轮廓（起点→终点走向，第三声为降升折线）。
 * 值为 [归一化时间 0–1, 五度值 1–5]。
 */
export function toneTargetContour(tone: ToneValue): Array<[number, number]> {
  switch (tone) {
    case 1:
      return [
        [0, 5],
        [1, 5],
      ]
    case 2:
      return [
        [0, 3],
        [1, 5],
      ]
    case 3:
      return [
        [0, 2],
        [0.45, 1],
        [1, 4],
      ]
    case 4:
      return [
        [0, 5],
        [1, 1],
      ]
  }
}

/** 五度值 → 半音（挂靠窗口中心，1 度 = 3 半音，五度全程约一个八度） */
export function degreeToSemitone(centerSt: number, degree: number): number {
  return centerSt + (degree - 3) * 3
}

/* ------------------------------ 单帧特征 ------------------------------ */

export type FrameKind = 'silence' | 'voiced' | 'unvoicedNoise'

export interface AcousticFrame {
  /** 相对录音开始的秒数 */
  t: number
  rms: number
  peak: number
  /** 平滑后的基频；无声与清音段为 null（自然留空，不画伪造轨迹） */
  f0Hz: number | null
  clarity: number
  /** 弱周期延续帧（主门限未过、按连续性接纳）：画布用较弱样式 */
  weak: boolean
  /** 谱重心（Hz），仅清音摩擦/送气段计算，用于区分偏高频/偏低频摩擦 */
  centroidHz: number | null
  clipping: boolean
  kind: FrameKind
}

/**
 * 实时基频跟踪器：逐帧吃进 AnalyserNode 的时域（与可选频域）数据，
 * 输出分类好的 AcousticFrame；frames 保留整段录音（定格回看用）。
 * 跳变观察缓冲：与上一接纳帧的半音变化率超过阈值时暂挂，3 帧内回到
 * 原轨迹按毛刺留空，连续进入新平台才接纳新轨迹（docs §6.1）。
 */
export class RealtimePitchTracker {
  readonly frames: AcousticFrame[] = []

  private readonly detector: PitchDetector<Float32Array>
  private readonly sampleRate: number
  private readonly emaAlpha: number
  private medianWindow: number[] = []
  private emaSt: number | null = null
  private unvoicedStreak = 0
  /** 连续通过主门限的有声帧数（≥3 后启用弱周期延续） */
  private stableVoiced = 0
  /** 上一接纳帧的半音值（跳变观察的基线） */
  private acceptedSt: number | null = null
  private observing: { newSt: number; plateauRun: number } | null = null
  private lastTSec: number | null = null

  constructor(sampleRate: number, options?: { fftSize?: number; emaAlpha?: number }) {
    this.sampleRate = sampleRate
    this.emaAlpha = options?.emaAlpha ?? 0.35
    this.detector = PitchDetector.forFloat32Array(options?.fftSize ?? ANALYSIS_FFT_SIZE)
  }

  reset(): void {
    this.frames.length = 0
    this.medianWindow = []
    this.emaSt = null
    this.unvoicedStreak = 0
    this.stableVoiced = 0
    this.acceptedSt = null
    this.observing = null
    this.lastTSec = null
  }

  /** 每分析帧调用一次；freqData 供清音段谱重心（无频域数据传 null） */
  push(input: Float32Array, tSec: number, freqData?: Uint8Array | null): AcousticFrame {
    let sumSquares = 0
    let peak = 0
    for (let i = 0; i < input.length; i += 1) {
      const v = input[i] ?? 0
      sumSquares += v * v
      const abs = Math.abs(v)
      if (abs > peak) peak = abs
    }
    const rms = Math.sqrt(sumSquares / input.length)
    const clipping = peak >= CLIPPING_PEAK

    let f0Hz: number | null = null
    let clarity = 0
    let centroidHz: number | null = null
    let kind: FrameKind = 'silence'
    let weak = false

    const dt = this.lastTSec === null ? ANALYSIS_STEP_MS / 1000 : Math.max(tSec - this.lastTSec, 1e-4)
    this.lastTSec = tSec

    if (rms >= WEAK_RMS_GATE) {
      const [pitch, clar] = this.detector.findPitch(input, this.sampleRate)
      clarity = clar
      const inRange = pitch >= F0_MIN_HZ && pitch <= F0_MAX_HZ
      const confident = inRange && clar >= CLARITY_GATE && rms >= SILENCE_RMS_GATE
      const rawSt = inRange ? hzToSemitone(pitch) : null
      const nearAccepted =
        rawSt !== null && this.acceptedSt !== null
          ? Math.abs(rawSt - this.acceptedSt) <= WEAK_CONTINUITY_ST
          : true
      // 弱周期延续：主门限判有声满 3 帧后，低 clarity 但与轨迹连续（嘎裂尾段）
      const weakContinued =
        !confident && rawSt !== null && this.stableVoiced >= 3
        && rms >= WEAK_RMS_GATE && clar >= WEAK_CLARITY_GATE && nearAccepted

      if (confident || weakContinued) {
        kind = 'voiced'
        weak = weakContinued
        const st = rawSt!
        // 跳变观察：相对上一接纳帧的 10ms 归一化半音变化率超阈值
        const ratePer10ms = Math.abs(st - (this.acceptedSt ?? st)) / (dt / 0.01)
        const jumped =
          this.acceptedSt !== null && !weakContinued
          && ratePer10ms > JUMP_OBSERVE_ST_PER_10MS
        if (jumped || this.observing) {
          // 待判定帧留白；观察连续新平台或回原轨迹
          let resume = false
          if (jumped && !this.observing) {
            this.observing = { newSt: st, plateauRun: 1 }
          } else if (this.observing) {
            const nearNew = Math.abs(st - this.observing.newSt) <= WEAK_CONTINUITY_ST
            const nearOld =
              this.acceptedSt !== null && Math.abs(st - this.acceptedSt) <= WEAK_CONTINUITY_ST
            if (nearOld) {
              this.observing = null            // 回到原轨迹：毛刺留空
            } else if (nearNew) {
              this.observing.plateauRun += 1
              if (this.observing.plateauRun >= JUMP_OBSERVE_FRAMES) {
                this.observing = null
                resume = true                  // 连续新平台：接纳新轨迹
              }
            } else {
              this.observing.newSt = st
              this.observing.plateauRun = 1
            }
          }
          if (resume) {
            // 接纳帧起恢复显示；平滑状态清零，从新轨迹重新起段
            this.medianWindow = []
            this.emaSt = null
            this.acceptedSt = st
            this.stableVoiced = 1
            this.medianWindow.push(st)
            f0Hz = semitoneToHz(st)
            this.unvoicedStreak = 0
          } else {
            this.breakStreak()
            this.stableVoiced = 0
          }
        } else {
          // 正常接纳：半音域中值滤波（剃单帧微抖）→ EMA 平滑
          this.acceptedSt = st
          if (!weakContinued) this.stableVoiced += 1
          this.medianWindow.push(st)
          if (this.medianWindow.length > 3) this.medianWindow.shift()
          const medianSt = medianOf(this.medianWindow)
          this.emaSt = this.emaSt === null ? medianSt : this.emaSt + this.emaAlpha * (medianSt - this.emaSt)
          f0Hz = semitoneToHz(this.emaSt)
          this.unvoicedStreak = 0
        }
      } else {
        kind = 'unvoicedNoise'
        if (freqData) centroidHz = spectralCentroidHz(freqData, this.sampleRate)
        this.breakStreak()
        this.stableVoiced = 0
      }
    } else {
      this.breakStreak()
      this.stableVoiced = 0
    }

    const frame: AcousticFrame = { t: tSec, rms, peak, f0Hz, clarity, weak, centroidHz, clipping, kind }
    this.frames.push(frame)
    return frame
  }

  /** 出现缺口即清空平滑状态，下一有效段独立起线。 */
  private breakStreak(): void {
    this.unvoicedStreak += 1
    this.medianWindow = []
    this.emaSt = null
  }
}

/* --------------------------- 自适应纵轴窗口 --------------------------- */

const DEFAULT_WINDOW_HZ: [number, number] = [85, 320]

/**
 * 实时纵轴：未积累足够有声样本前用成人默认区间；有声满约 0.5 秒后
 * 平滑收缩到本人平均音高 ±8 半音，男女声、高低嗓音都不至于贴边或压扁。
 */
export class AdaptivePitchWindow {
  minSt = hzToSemitone(DEFAULT_WINDOW_HZ[0])
  maxSt = hzToSemitone(DEFAULT_WINDOW_HZ[1])

  private meanSt: number | null = null
  private voicedSec = 0

  update(st: number, dtSec: number): void {
    this.meanSt = this.meanSt === null ? st : this.meanSt + 0.1 * (st - this.meanSt)
    this.voicedSec += dtSec
    if (this.voicedSec < 0.5) return
    const targetMin = this.meanSt - 8
    const targetMax = this.meanSt + 8
    this.minSt += (targetMin - this.minSt) * 0.1
    this.maxSt += (targetMax - this.maxSt) * 0.1
  }

  get centerSt(): number {
    return (this.minSt + this.maxSt) / 2
  }
}

/* ------------------------------ 谱重心 ------------------------------ */

/** 字节数据底噪截止：低于该值的 bin 视为本底噪声，不参与重心（否则
 * 全谱 -100dB 地板换算成线性后会把重心拖向谱中央） */
const CENTROID_FLOOR_BYTE = 20

/**
 * 频域字节数据的能量加权谱重心（Hz）。字节值是 -100..-30 dB 映射，
 * 先还原线性幅度再加权，避免对数刻度把重心系统性拉向低频。
 */
export function spectralCentroidHz(freqData: Uint8Array, sampleRate: number): number {
  const binHz = sampleRate / 2 / freqData.length
  let weighted = 0
  let total = 0
  for (let i = 1; i < freqData.length; i += 1) {
    const byte = freqData[i]!
    if (byte < CENTROID_FLOOR_BYTE) continue
    const db = (byte / 255) * 70 - 100
    const magnitude = Math.pow(10, db / 20)
    weighted += i * binHz * magnitude
    total += magnitude
  }
  return total > 0 ? weighted / total : 0
}

/* ------------------------------ 小工具 ------------------------------ */

export function medianOf(values: number[]): number {
  if (values.length === 0) return Number.NaN
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 1 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2
}
