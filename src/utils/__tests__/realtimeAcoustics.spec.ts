/** 实时声学特征提取单测（FR-907）：合成信号驱动，确定性验证 */
import { describe, expect, it } from 'vitest'
import {
  AdaptivePitchWindow,
  ANALYSIS_FFT_SIZE,
  RealtimePitchTracker,
  degreeToSemitone,
  hzToSemitone,
  semitoneToHz,
  spectralCentroidHz,
  toneOfPinyin,
  toneTargetContour,
} from '../realtimeAcoustics'

const SAMPLE_RATE = 48_000

function sineWave(hz: number, seconds = ANALYSIS_FFT_SIZE / SAMPLE_RATE, amplitude = 0.4): Float32Array {
  const data = new Float32Array(Math.round(seconds * SAMPLE_RATE))
  for (let i = 0; i < data.length; i += 1) {
    data[i] = amplitude * Math.sin((2 * Math.PI * hz * i) / SAMPLE_RATE)
  }
  return data
}

/** 混入噪声模拟清辅音：无周期性、有能量 */
function noise(seconds = ANALYSIS_FFT_SIZE / SAMPLE_RATE, amplitude = 0.3): Float32Array {
  const data = new Float32Array(Math.round(seconds * SAMPLE_RATE))
  for (let i = 0; i < data.length; i += 1) {
    data[i] = amplitude * (Math.random() * 2 - 1)
  }
  return data
}

function pushFrames(tracker: RealtimePitchTracker, signal: Float32Array, count: number, startT = 0): void {
  for (let i = 0; i < count; i += 1) {
    tracker.push(signal, startT + (i * ANALYSIS_FFT_SIZE) / SAMPLE_RATE)
  }
}

/** 按 10ms 分析步长推帧（与生产画布一致，docs §6.1） */
function pushFrames10ms(tracker: RealtimePitchTracker, signal: Float32Array, count: number, startT = 0): void {
  for (let i = 0; i < count; i += 1) {
    tracker.push(signal, startT + i * 0.01)
  }
}

describe('半音换算', () => {
  it('Hz 与半音互为反函数', () => {
    for (const hz of [65, 85, 110, 220, 320, 500]) {
      expect(semitoneToHz(hzToSemitone(hz))).toBeCloseTo(hz, 6)
    }
  })

  it('五度值按窗口中心两侧各 3 半音展开', () => {
    const center = hzToSemitone(220)
    expect(degreeToSemitone(center, 3)).toBeCloseTo(center, 9)
    expect(degreeToSemitone(center, 5) - degreeToSemitone(center, 1)).toBeCloseTo(12, 6)
  })
})

describe('RealtimePitchTracker', () => {
  it('稳态正弦波：数帧后收敛到目标基频', () => {
    const tracker = new RealtimePitchTracker(SAMPLE_RATE)
    pushFrames(tracker, sineWave(220), 6)
    const voiced = tracker.frames.filter((f) => f.kind === 'voiced')
    expect(voiced.length).toBeGreaterThanOrEqual(5)
    const last = tracker.frames.at(-1)!
    expect(last.f0Hz).not.toBeNull()
    expect(last.f0Hz!).toBeCloseTo(220, 1)
  })

  it('静音帧：有声判 null、kind 为 silence', () => {
    const tracker = new RealtimePitchTracker(SAMPLE_RATE)
    pushFrames(tracker, new Float32Array(ANALYSIS_FFT_SIZE), 4)
    expect(tracker.frames.every((f) => f.f0Hz === null && f.kind === 'silence')).toBe(true)
  })

  it('白噪声（有能量无周期）：判为清音噪声而非伪基频', () => {
    const tracker = new RealtimePitchTracker(SAMPLE_RATE)
    pushFrames(tracker, noise(), 6)
    expect(tracker.frames.every((f) => f.kind === 'unvoicedNoise' && f.f0Hz === null)).toBe(true)
  })

  it('单帧八度毛刺被滤除（10ms 邻近帧率下走观察缓冲留空）', () => {
    const step = ANALYSIS_FFT_SIZE / SAMPLE_RATE
    const tracker = new RealtimePitchTracker(SAMPLE_RATE)
    pushFrames(tracker, sineWave(220), 5) // 稳态 220Hz
    tracker.push(sineWave(440), 5 * step) // 注入一帧八度毛刺（时间单调递增）
    pushFrames(tracker, sineWave(220), 2, 6 * step)
    const around = tracker.frames.slice(-3)
    for (const frame of around) {
      // 毛刺帧按 docs §6.1 留空或被中值滤波压回，后续帧回到 220Hz 邻域
      if (frame.f0Hz === null) continue
      expect(frame.f0Hz).toBeGreaterThan(180)
      expect(frame.f0Hz).toBeLessThan(260)
    }
    const last = tracker.frames.at(-1)!
    expect(last.f0Hz).not.toBeNull()
    expect(last.f0Hz!).toBeGreaterThan(180)
    expect(last.f0Hz!).toBeLessThan(260)
  })

  it('10ms 步长下八度跳变进入观察缓冲：毛刺留空，回原轨迹后恢复', () => {
    const tracker = new RealtimePitchTracker(SAMPLE_RATE)
    pushFrames10ms(tracker, sineWave(220), 6)   // 稳态
    const glitch = tracker.push(sineWave(440), 0.06)  // 10ms 内跳八度：rate=12 ST/10ms
    expect(glitch.f0Hz).toBeNull()                    // 待判定留白
    const back = tracker.push(sineWave(220), 0.07)    // 回到原轨迹
    expect(back.f0Hz).toBeNull()                      // 毛刺期间保持留空
    const resumed = tracker.push(sineWave(220), 0.08) // 之后恢复正常显示
    expect(resumed.f0Hz).not.toBeNull()
    expect(resumed.f0Hz!).toBeGreaterThan(180)
    expect(resumed.f0Hz!).toBeLessThan(260)
  })

  it('10ms 步长下持续新平台（3 帧）被接纳为新轨迹', () => {
    const tracker = new RealtimePitchTracker(SAMPLE_RATE)
    pushFrames10ms(tracker, sineWave(220), 6)
    expect(tracker.push(sineWave(440), 0.06).f0Hz).toBeNull()  // 观察第 1 帧
    expect(tracker.push(sineWave(440), 0.07).f0Hz).toBeNull()  // 观察第 2 帧
    const accepted = tracker.push(sineWave(440), 0.08)         // 第 3 帧：接纳
    expect(accepted.f0Hz).not.toBeNull()
    expect(accepted.f0Hz!).toBeGreaterThan(380)
    expect(accepted.f0Hz!).toBeLessThan(500)
  })

  it('无声断开超过 3 帧后清空平滑状态（新音节不跨段连线）', () => {
    const tracker = new RealtimePitchTracker(SAMPLE_RATE)
    pushFrames(tracker, sineWave(200), 4)
    expect((tracker as unknown as { emaSt: number | null }).emaSt).not.toBeNull()
    pushFrames(tracker, new Float32Array(ANALYSIS_FFT_SIZE), 4)
    expect((tracker as unknown as { emaSt: number | null }).emaSt).toBeNull()
  })

  it('reset 清空全部历史', () => {
    const tracker = new RealtimePitchTracker(SAMPLE_RATE)
    pushFrames(tracker, sineWave(220), 3)
    tracker.reset()
    expect(tracker.frames.length).toBe(0)
  })
})

describe('AdaptivePitchWindow', () => {
  it('初始为成人默认区间，有声满 0.5 秒后向本人音高收缩', () => {
    const win = new AdaptivePitchWindow()
    const low = hzToSemitone(110)
    const dt = ANALYSIS_FFT_SIZE / SAMPLE_RATE
    for (let i = 0; i < Math.ceil(0.5 / dt) + 30; i += 1) {
      win.update(low, dt)
    }
    expect(win.centerSt).toBeCloseTo(low, 0)
    // ±8 半音视野
    expect(win.maxSt - win.minSt).toBeLessThan(16.5)
    expect(win.maxSt - win.minSt).toBeGreaterThan(15)
  })
})

describe('谱重心', () => {
  function freqDataOf(hz: number, bins: number): Uint8Array {
    const data = new Uint8Array(bins)
    const binHz = SAMPLE_RATE / 2 / bins
    const peak = Math.max(1, Math.round(hz / binHz))
    data[peak] = 255
    return data
  }

  it('单频能量：重心跟随频率位置', () => {
    const bins = ANALYSIS_FFT_SIZE / 2
    const low = spectralCentroidHz(freqDataOf(1000, bins), SAMPLE_RATE)
    const high = spectralCentroidHz(freqDataOf(6000, bins), SAMPLE_RATE)
    expect(low).toBeGreaterThan(900)
    expect(low).toBeLessThan(1100)
    expect(high).toBeGreaterThan(5800)
  })
})

describe('调型推导', () => {
  it('声调符号 → 调号', () => {
    expect(toneOfPinyin('mā')).toBe(1)
    expect(toneOfPinyin('má')).toBe(2)
    expect(toneOfPinyin('ǎ')).toBe(3)
    expect(toneOfPinyin('mà')).toBe(4)
  })

  it('无声调符号（如声母关 pinyin）返回 null，不猜调', () => {
    expect(toneOfPinyin('b')).toBeNull()
    expect(toneOfPinyin('a')).toBeNull()
    expect(toneOfPinyin(undefined)).toBeNull()
  })

  it('四声轮廓走向正确（平/升/降升/降）', () => {
    expect(toneTargetContour(1).at(-1)![1]).toBe(5)
    expect(toneTargetContour(2)[0][1]).toBeLessThan(toneTargetContour(2).at(-1)![1])
    expect(toneTargetContour(3).length).toBe(3)
    expect(toneTargetContour(4)[0][1]).toBeGreaterThan(toneTargetContour(4).at(-1)![1])
  })
})
