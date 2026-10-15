/**
 * 声道剖面几何与关键帧插值（ADR-20 / #20：按发音器官关键帧参数化，前端绘制）。
 * 纯函数：SagittalView.vue 只负责 SVG 输出与播放控制。
 * 坐标系：viewBox 0 0 400 320，头朝左，y 向下。
 */
import type { SagittalKeyframe } from '@/api'

export const TRANSITION_MS = 160

export function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value))
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

/** 插值后的有效参数：数值线性插值，枚举取主导帧（t≥0.5 为目标帧） */
export interface EffectiveKeyframe {
  jaw: number
  lipAperture: number
  lipRounding: number
  lipContact: SagittalKeyframe['lips']['contact']
  tipPlace: SagittalKeyframe['tongueTip']['place']
  tipStricture: SagittalKeyframe['tongueTip']['stricture']
  bodyHeight: number
  bodyBackness: number
  bodyStricture: SagittalKeyframe['tongueBody']['stricture']
  velumLowered: boolean
  airflow: SagittalKeyframe['airflow']
  voicing: boolean
}

export function interpolateKeyframes(a: SagittalKeyframe, b: SagittalKeyframe, t: number): EffectiveKeyframe {
  const w = clamp01(t)
  const dominant = w < 0.5 ? a : b
  return {
    jaw: lerp(a.jaw, b.jaw, w),
    lipAperture: lerp(a.lips.aperture, b.lips.aperture, w),
    lipRounding: lerp(a.lips.rounding, b.lips.rounding, w),
    lipContact: dominant.lips.contact,
    tipPlace: dominant.tongueTip.place,
    tipStricture: dominant.tongueTip.stricture,
    bodyHeight: lerp(a.tongueBody.height, b.tongueBody.height, w),
    bodyBackness: lerp(a.tongueBody.backness, b.tongueBody.backness, w),
    bodyStricture: dominant.tongueBody.stricture,
    velumLowered: dominant.velum === 'lowered',
    airflow: dominant.airflow,
    voicing: dominant.voicing,
  }
}

/* ----------------------------- 参考点位表 ----------------------------- */

/** 舌尖位置（x, y）与上接触目标；stricture 决定与目标的间隙 */
const TIP_PLACE_ANCHORS: Record<SagalPlace, { tip: [number, number]; target: [number, number] }> = {
  rest: { tip: [122, 180], target: [118, 138] },
  dental: { tip: [102, 158], target: [100, 152] },
  alveolar: { tip: [108, 140], target: [106, 136] },
  postalveolar: { tip: [124, 136], target: [122, 132] },
  retroflex: { tip: [134, 148], target: [126, 132] },
}
type SagalPlace = SagittalKeyframe['tongueTip']['place']

const STRICTURE_GAP: Record<SagittalKeyframe['tongueTip']['stricture'], number> = {
  closure: 0,
  fricative: 4,
  approximant: 9,
  open: 16,
}

/** 双唇接触方式对应的上唇目标 */
const LIP_CONTACT_GAP: Record<SagittalKeyframe['lips']['contact'], number> = {
  none: 0,
  bilabial: 0,
  labiodental: -6,
}

export interface SagittalGeometry {
  /** 下颌组旋转角度（绕颞颌关节 232,182） */
  jawRotateDeg: number
  upperLip: string
  lowerLip: string
  /** 唇开口（含接触修正），用于文字说明 */
  lipGapPx: number
  lipClosed: boolean
  tonguePath: string
  /** 舌与上结构的最近接触点（示意标注用） */
  constriction: { x: number; y: number; label: string } | null
  velumPath: string
  nasalPortOpen: boolean
  airflowPath: string
  airflowLabel: string
  voicing: boolean
}

function airflowOf(kind: SagittalKeyframe['airflow']): { path: string; label: string } {
  switch (kind) {
    case 'oral':
      return { path: 'M204,262 C196,230 170,190 120,168 C100,160 84,152 66,148', label: '气流：口腔' }
    case 'nasal':
      return { path: 'M204,262 C200,230 208,205 214,190 C218,170 160,140 78,116', label: '气流：鼻腔' }
    case 'burst':
      return { path: 'M204,262 C196,230 170,190 120,168 C100,160 84,152 66,148', label: '气流：爆破' }
    case 'aspirated_burst':
      return { path: 'M204,262 C196,230 170,190 120,168 C100,160 84,152 66,148', label: '气流：送气' }
    case 'friction':
      return { path: 'M204,262 C196,230 170,190 130,160', label: '气流：摩擦' }
    case 'affricate':
      return { path: 'M204,262 C196,230 170,190 120,168 C100,160 84,152 66,148', label: '气流：塞擦' }
    default:
      return { path: '', label: '' }
  }
}

export function buildSagittalGeometry(p: EffectiveKeyframe): SagittalGeometry {
  const jaw = clamp01(p.jaw)
  const jawRotateDeg = jaw * 13

  // 唇：aperture 0（闭）→1（大开）；rounding 前伸；contact 修正
  const mouthY = 146
  const protrude = p.lipRounding * 9
  const baseGap = p.lipAperture * 34
  const contactGap = p.lipContact === 'bilabial' ? 0 : baseGap
  const lipGapPx = Math.max(0, contactGap + LIP_CONTACT_GAP[p.lipContact]!)
  const upperLipY = mouthY - lipGapPx / 2 - 4
  const lowerLipY = mouthY + lipGapPx / 2 + 4
  const upperLip = `M${78 - protrude},${upperLipY} q10,-8 22,-2 q-8,6 -22,6 z`
  const lowerLip = `M${78 - protrude},${lowerLipY} q10,8 22,2 q-8,-6 -22,-6 z`

  // 舌：舌面高低/前后 + 舌尖位置/阻碍
  const bodyApexX = lerp(136, 198, clamp01(p.bodyBackness))
  const bodyApexY = lerp(206, 138, clamp01(p.bodyHeight))
  const anchor = TIP_PLACE_ANCHORS[p.tipPlace]!
  const gap = STRICTURE_GAP[p.tipStricture]!
  const tipX = anchor.tip[0]
  const tipY = anchor.tip[1] + gap
  const floorY = 228 + jaw * 4
  const tonguePath = [
    `M236,218`,
    `C228,${lerp(200, bodyApexY + 14, 0.6)} ${Math.min(226, bodyApexX + 34)},${bodyApexY + 6} ${bodyApexX},${bodyApexY}`,
    `C${lerp(bodyApexX, tipX, 0.5)},${bodyApexY + 10} ${lerp(tipX, bodyApexX, 0.35)},${tipY - 4} ${tipX},${tipY}`,
    `C${tipX - 8},${tipY + 10} ${lerp(tipX, 170, 0.6)},${floorY - 6} 172,${floorY}`,
    `L236,218 z`,
  ].join(' ')

  // 舌面阻碍（g/k/h/j/q/x）：舌面接近腭部
  const bodyStrictureGap = STRICTURE_GAP[p.bodyStricture]!
  const bodyConstriction =
    p.bodyStricture !== 'open'
      ? { x: bodyApexX, y: bodyApexY - bodyStrictureGap, label: '舌面收紧' }
      : null
  const tipConstriction =
    p.tipStricture === 'closure' || p.tipStricture === 'fricative'
      ? { x: anchor.target[0], y: anchor.target[1], label: p.tipStricture === 'closure' ? '成阻' : '摩擦' }
      : null

  // 软腭：raised 关闭鼻咽通道；lowered 打开（m/n）
  const velumPath = p.velumLowered
    ? 'M206,150 C216,164 224,180 226,196'
    : 'M206,150 C218,158 230,162 238,166'

  const air = airflowOf(p.airflow)

  return {
    jawRotateDeg,
    upperLip,
    lowerLip,
    lipGapPx,
    lipClosed: p.lipContact === 'bilabial' || (p.lipContact === 'none' && lipGapPx < 3),
    tonguePath,
    constriction: tipConstriction ?? bodyConstriction,
    velumPath,
    nasalPortOpen: p.velumLowered,
    airflowPath: air.path,
    airflowLabel: air.label,
    voicing: p.voicing,
  }
}

/** 播放时间轴：第 i 帧 hold holdMs，随后 TRANSITION_MS 过渡到下一帧 */
export interface TimelineEntry {
  frameIndex: number
  /** hold 起止 */
  holdStart: number
  holdEnd: number
  transitionEnd: number
}

export function buildTimeline(keyframes: SagittalKeyframe[]): { entries: TimelineEntry[]; totalMs: number } {
  const entries: TimelineEntry[] = []
  let cursor = 0
  keyframes.forEach((frame, index) => {
    const holdStart = cursor
    const holdEnd = holdStart + Math.max(60, frame.holdMs)
    const transitionEnd = holdEnd + (index < keyframes.length - 1 ? TRANSITION_MS : 0)
    entries.push({ frameIndex: index, holdStart, holdEnd, transitionEnd })
    cursor = transitionEnd
  })
  return { entries, totalMs: cursor }
}

/** 时间点 →（帧 a，帧 b，插值 t）；hold 期 t=0 */
export function sampleTimeline(
  entries: TimelineEntry[],
  timeMs: number,
): { a: number; b: number; t: number } | null {
  for (const entry of entries) {
    if (timeMs <= entry.holdEnd) return { a: entry.frameIndex, b: entry.frameIndex, t: 0 }
    if (entry.transitionEnd > entry.holdEnd && timeMs <= entry.transitionEnd) {
      const span = entry.transitionEnd - entry.holdEnd
      return { a: entry.frameIndex, b: entry.frameIndex + 1, t: (timeMs - entry.holdEnd) / span }
    }
  }
  return null
}
