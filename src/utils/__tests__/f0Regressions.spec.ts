import { describe, expect, it } from 'vitest'
import { splitByConfidence } from '../curveSegments'
import { PcmWindows } from '../pcmWindows'
import { ANALYSIS_FFT_SIZE, RealtimePitchTracker } from '../realtimeAcoustics'

describe('F0 regressions', () => {
  it('disconnects the old style when confidence changes', () => {
    const pts = [0.9, 0.9, 0.3, 0.3, 0.9, 0.9].map((conf, x) => ({
      x, y: [3, 3, 1, 1, 3, 3][x]!, conf, src: 'measured',
    }))
    const { solid, dotted } = splitByConfidence(pts)
    const left = solid.findIndex((p) => p?.[0] === 1)
    const right = solid.findIndex((p) => p?.[0] === 4)
    expect(solid.slice(left + 1, right)).toContain(null)
    expect(dotted.filter(Boolean)).toEqual([[1, 3], [2, 1], [3, 1], [4, 3]])
  })

  it('keeps a real gap in both styles', () => {
    const { solid, dotted } = splitByConfidence([
      { x: 0, y: 3, conf: .9, src: 'measured' },
      { x: 1, y: null, conf: 0, src: null },
      { x: 2, y: 3, conf: .3, src: 'measured' },
      { x: 3, y: 3, conf: .9, src: 'measured' },
    ])
    expect(solid).not.toContainEqual([0, 3])
    expect(dotted.filter(Boolean)).toEqual([[2, 3], [3, 3]])
  })

  it.each([44100, 48000])('uses distinct PCM windows at a 10ms cadence (%i Hz)', (rate) => {
    const start = 30 * rate
    const windows = new PcmWindows(rate, 4096, start)
    const outputs = []
    for (let offset = -64; offset < rate / 2; offset += 128) {
      const chunk = Float32Array.from({ length: 128 }, (_, i) => offset + i)
      outputs.push(...windows.push(chunk, start + offset))
    }
    expect(outputs.length).toBeGreaterThan(30)
    expect(outputs[0]!.t).toBeCloseTo(2048 / rate)
    for (let i = 1; i < outputs.length; i++) {
      expect(outputs[i]!.t - outputs[i - 1]!.t).toBeCloseTo(.01, 9)
      expect(outputs[i]!.samples[0]! - outputs[i - 1]!.samples[0]!).toBe(Math.round(rate * .01))
    }
  })

  it('waits for a fresh full window after dropped samples', () => {
    const windows = new PcmWindows(48000, 4096, 0)
    expect(windows.push(new Float32Array(4096), 0)).toHaveLength(1)
    expect(windows.push(new Float32Array(480), 8000)).toHaveLength(0)
  })

  it('continues a quiet periodic tail below the main RMS gate', () => {
    const tracker = new RealtimePitchTracker(48000)
    const sine = (amp: number) => Float32Array.from(
      { length: ANALYSIS_FFT_SIZE }, (_, i) => amp * Math.sin(2 * Math.PI * 220 * i / 48000),
    )
    for (let i = 0; i < 5; i++) tracker.push(sine(.4), i * .01)
    const frame = tracker.push(sine(.013), .05)
    expect(frame.rms).toBeGreaterThan(.008)
    expect(frame.rms).toBeLessThan(.012)
    expect(frame.f0Hz).toBeCloseTo(220, 0)
    expect(frame.weak).toBe(true)
  })
})

