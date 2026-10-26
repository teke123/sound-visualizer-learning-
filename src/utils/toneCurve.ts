/**
 * 声调曲线处理：屏蔽静音 → 平滑 → 归一化（T 值 0–5）
 * ---------------------------------------------------------------------------
 * 为什么需要这三步（顺序不能颠倒）：
 *
 *   1) 屏蔽静音：基频（F0）只在有声段有意义。静音帧要变成 null，
 *      让图表断线，而不是把 0 或噪声画成一条掉到底的线。
 *
 *   2) 平滑：基频提取算法本身有抖动（真实录音的抖动通常比 3% 还大）。
 *      ⚠️ 而下一步的归一化会**放大**这种抖动——按 193–219 Hz 的调域算，
 *      3% 的频率抖动会变成 ±1.15 个 T 值（0–5 刻度上的 23%）。
 *      所以**必须先平滑再归一化**，顺序反了等于先把噪声放大再去补救。
 *      （注意：ECharts 的 series.smooth 只是"渲染平滑"，数值不变，不能替代这一步。）
 *
 *   3) 归一化：把绝对频率映射到「说话人自己调域内的 T 值 0–5」。
 *      成年男性基频约 90–150 Hz、女性 180–250 Hz、儿童 250–400 Hz，
 *      直接比绝对 Hz 等于让所有人跟同一条"标准音高"比，音色不同会被误判成发音错误。
 *      而声调的正确性本质是**走向**问题（高平 / 上升 / 降升 / 急降），不是绝对音高问题。
 *      T(x) = 5 × (ln x − ln lo) / (ln hi − ln lo)   —— 取对数是因为人耳对音高是对数感知。
 *
 * ⚠️ 已知局限（需与 A / D 确认后定稿）：
 *   1) 调域取自"本次录音"的有声段。若本次整体压低，调域跟着下移，归一化后看不出问题。
 *      更稳的做法是用说话人的「常态调域」（多次录音统计），或由后端给出目标调域。
 *   2) 标准曲线用同一套调域映射；超出 0–5 说明"标准要求的音高超出你本次音域"，
 *      可能是真信号，也可能是调域估计不准。产品上要怎么呈现需要想清楚。
 */

export interface PitchRange {
  lo: number
  hi: number
}

/** 屏蔽静音帧：voiced[i] === false → null；非正数也视为无效 */
export function maskByVoiced(f0: number[], voiced?: boolean[]): (number | null)[] {
  return f0.map((v, i) => {
    if (typeof v !== 'number' || !(v > 0)) return null
    if (voiced && voiced[i] === false) return null
    return v
  })
}

/**
 * 移动平均平滑。
 * ⚠️ 只在**连续有效段内**平滑，遇到 null（静音）就断开——不跨静音段平均，
 *    否则会把"字与字之间"的静音算进来，把曲线压平。
 *
 * @param window 每侧取多少个邻居；最终窗口长度 = 2 × window + 1
 */
export function smoothSeries(values: (number | null)[], window = 2): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null)
  let i = 0
  while (i < values.length) {
    if (values[i] === null) {
      i++
      continue
    }
    // 找出一段连续有效区间 [i, j)
    let j = i
    while (j < values.length && values[j] !== null) j++
    const seg = values.slice(i, j) as number[]
    for (let k = 0; k < seg.length; k++) {
      const lo = Math.max(0, k - window)
      const hi = Math.min(seg.length - 1, k + window)
      let sum = 0
      for (let m = lo; m <= hi; m++) sum += seg[m] as number
      out[i + k] = sum / (hi - lo + 1)
    }
    i = j
  }
  return out
}

/** 从（可能含 null 的）序列取调域：最低 / 最高有效基频 */
export function rangeOfSeries(values: (number | null)[]): PitchRange {
  let lo = Infinity
  let hi = -Infinity
  for (const v of values) {
    if (v === null || !(v > 0)) continue
    if (v < lo) lo = v
    if (v > hi) hi = v
  }
  return Number.isFinite(lo) ? { lo, hi } : { lo: 0, hi: 0 }
}

/** 从原始 F0 + 静音掩码取调域（便捷封装） */
export function pitchRange(f0: number[], voiced?: boolean[]): PitchRange {
  return rangeOfSeries(maskByVoiced(f0, voiced))
}

/** 对数尺度归一化 → T 值；无效帧返回 null，交给图表断线 */
export function toTValue(values: (number | null)[], range: PitchRange): (number | null)[] {
  const { lo, hi } = range
  if (!(lo > 0) || !(hi > lo)) return values.map(() => null)
  const lnLo = Math.log(lo)
  const span = Math.log(hi) - lnLo
  return values.map(v => (v === null || !(v > 0) ? null : ((Math.log(v) - lnLo) / span) * 5))
}

export interface NormalizeResult {
  /** 本次使用的调域 */
  range: PitchRange
  /** 平滑后（未归一化）的用户曲线 */
  smoothUser: (number | null)[]
  /** 平滑后的标准曲线 */
  smoothStandard: (number | null)[]
  /** 未平滑的 T 值（用于对比"为什么不先平滑不行"） */
  rawUserT: (number | null)[]
  rawStandardT: (number | null)[]
  /** 平滑 + 归一化后的 T 值（推荐画法） */
  userT: (number | null)[]
  standardT: (number | null)[]
}

/**
 * 一站式处理：屏蔽静音 → 平滑 → 定调域 → 两条曲线映射成 T 值。
 *
 * @param reference   自定义调域（例如后端给出的目标调域）；不传则用用户本次录音的调域
 * @param smoothWindow 平滑窗口半径（默认 2，即 5 点移动平均）
 */
export function normalizePair(
  userF0: number[],
  standardF0: number[],
  voiced?: boolean[],
  opts: { reference?: PitchRange; smoothWindow?: number } = {},
): NormalizeResult {
  const { reference, smoothWindow = 2 } = opts

  const maskedUser = maskByVoiced(userF0, voiced)
  const maskedStandard = maskByVoiced(standardF0)

  const smoothUser = smoothSeries(maskedUser, smoothWindow)
  const smoothStandard = smoothSeries(maskedStandard, smoothWindow)

  const range = reference ?? rangeOfSeries(smoothUser)

  return {
    range,
    smoothUser,
    smoothStandard,
    rawUserT: toTValue(maskedUser, range),
    rawStandardT: toTValue(maskedStandard, range),
    userT: toTValue(smoothUser, range),
    standardT: toTValue(smoothStandard, range),
  }
}
