/**
 * 声调曲线处理（重构占位，仅保留设计意图）
 * ---------------------------------------------------------------------------
 * 意图（处理顺序不可颠倒）：
 *
 *   1) 屏蔽静音：F0 只在有声段有意义，静音帧置 null 让图表断线，
 *      不把 0 或噪声画成掉底的线；
 *
 *   2) 平滑：F0 提取本身有抖动，而下一步的归一化会放大抖动
 *      （窄调域下 3% 频率抖动 ≈ ±1 个 T 值），必须先平滑再归一化；
 *      平滑只在连续有效段内进行，不跨静音段平均；
 *      注意：图表库的渲染平滑不改变数值，不能替代这一步。
 *
 *   3) 归一化：T(x) = 5 × (ln x − ln lo) / (ln hi − ln lo)，
 *      把绝对频率映射到说话人调域内的 T 值 0–5（对数尺度，符合听感），
 *      避免用绝对 Hz 评判不同音色的人。
 *
 * 已知设计问题（重构时必须解决，不要照旧实现）：
 *   - 调域不应取自"本次录音"（整体压低时调域跟着下移，问题被归一化抹掉），
 *     应使用说话人常态调域（多次录音统计）或后端下发目标调域；
 *   - 标准曲线与用户曲线使用同一调域时，超界（T<0 或 T>5）的呈现语义要明确定义。
 */

export interface PitchRange {
  lo: number
  hi: number
}

/** 意图：静音帧 -> null（非正数与 voiced=false 都视为无效） */
export function maskByVoiced(f0: number[], voiced?: boolean[]): (number | null)[] {
  throw new Error('重构占位：静音屏蔽（算法待按上述意图重新实现）')
}

/** 意图：连续有效段内的移动平均平滑，遇 null 断开 */
export function smoothSeries(values: (number | null)[], window = 2): (number | null)[] {
  throw new Error('重构占位：曲线平滑（算法待按上述意图重新实现）')
}

/** 意图：从有效帧取调域（最低/最高基频） */
export function rangeOfSeries(values: (number | null)[]): PitchRange {
  throw new Error('重构占位：调域估计（待重构，建议改用常态调域）')
}

/** 意图：对数尺度归一化到 T 值 0–5；无效帧返回 null 交给图表断线 */
export function toTValue(values: (number | null)[], range: PitchRange): (number | null)[] {
  throw new Error('重构占位：T 值归一化（算法待按上述意图重新实现）')
}
