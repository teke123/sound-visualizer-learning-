/**
 * 实时声学特征提取（FR-907）：纯计算与轻量状态机，供 RealtimeAcousticCanvas
 * 在 rAF 循环中调用，不触碰 Vue 响应式与网络。
 *
 * 基频用 pitchy（McLeod Pitch Method，NSDF）提取，输出 pitch + clarity，
 * 用 clarity 门限区分有声段与清辅音/环境噪声；平滑在半音域做
 * 「3 点中值滤波（剃单帧八度跳变）+ 一阶指数平滑（EMA）」。
 * 纵轴一律使用对数半音标度（人耳音高感知是对数的，线性 Hz 会把
 * 低音声部压扁、高音声部放大），五度调型按「1 度 = 3 半音」挂靠窗口中心。
 */
import { PitchDetector } from 'pitchy'

export const ANALYSIS_FFT_SIZE = 2048

/** 人声基频窗口与清浊判定门限（清辅音/噪声的 clarity 通常落到 0.2–0.6） */
export const F0_MIN_HZ = 65
export const F0_MAX_HZ = 500
export const CLARITY_GATE = 0.85
export const SILENCE_RMS_GATE = 0.015
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
  /** 谱重心（Hz），仅清音摩擦/送气段计算，用于区分偏高频/偏低频摩擦 */
  centroidHz: number | null
  clipping: boolean
  kind: FrameKind
}

/**
 * 实时基频跟踪器：逐帧吃进 AnalyserNode 的时域（与可选频域）数据，
 * 输出分类好的 AcousticFrame；frames 保留整段录音（定格回看用）。
 */
export class RealtimePitchTracker {
  readonly frames: AcousticFrame[] = []

  private readonly detector: PitchDetector<Float32Array>
  private readonly sampleRate: number
  private readonly emaAlpha: number
  private medianWindow: number[] = []
  private emaSt: number | null = null
  private unvoicedStreak = 0

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

    if (rms >= SILENCE_RMS_GATE) {
      const [pitch, clar] = this.detector.findPitch(input, this.sampleRate)
      clarity = clar
      const voiced = pitch >= F0_MIN_HZ && pitch <= F0_MAX_HZ && clar >= CLARITY_GATE
      if (voiced) {
        kind = 'voiced'
        // 半音域中值滤波（剃掉单帧八度跳变）→ EMA 平滑
        const st = hzToSemitone(pitch)
        this.medianWindow.push(st)
        if (this.medianWindow.length > 3) this.medianWindow.shift()
        const medianSt = medianOf(this.medianWindow)
        this.emaSt = this.emaSt === null ? medianSt : this.emaSt + this.emaAlpha * (medianSt - this.emaSt)
        f0Hz = semitoneToHz(this.emaSt)
        this.unvoicedStreak = 0
      } else {
        kind = 'unvoicedNoise'
        if (freqData) centroidHz = spectralCentroidHz(freqData, this.sampleRate)
        this.breakStreak()
      }
    } else {
      this.breakStreak()
    }

    const frame: AcousticFrame = { t: tSec, rms, peak, f0Hz, clarity, centroidHz, clipping, kind }
    this.frames.push(frame)
    return frame
  }

  /** 无声/清音持续超过 3 帧：清空平滑状态，避免跨音节连线平滑 */
  private breakStreak(): void {
    this.unvoicedStreak += 1
    if (this.unvoicedStreak > 3) {
      this.medianWindow = []
      this.emaSt = null
    }
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
