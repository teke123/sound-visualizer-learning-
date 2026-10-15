/** 声道剖面：关键帧插值 / 时间轴采样 / 几何构建单测（ADR-20 / §11） */
import { describe, expect, it } from 'vitest'
import type { SagittalKeyframe } from '@/api'
import { buildSagittalGeometry, buildTimeline, interpolateKeyframes, sampleTimeline } from '../sagittal'

function frame(overrides: Partial<SagittalKeyframe> = {}): SagittalKeyframe {
  return {
    label: '测试帧',
    holdMs: 400,
    jaw: 0.2,
    lips: { aperture: 0.4, rounding: 0, contact: 'none' },
    tongueTip: { place: 'alveolar', stricture: 'open' },
    tongueBody: { height: 0.3, backness: 0.5, stricture: 'open' },
    velum: 'raised',
    airflow: 'oral',
    voicing: true,
    ...overrides,
  }
}

describe('interpolateKeyframes', () => {
  it('数值字段线性插值', () => {
    const a = frame({ jaw: 0 })
    const b = frame({ jaw: 1 })
    expect(interpolateKeyframes(a, b, 0.5).jaw).toBeCloseTo(0.5)
    expect(interpolateKeyframes(a, b, 0).jaw).toBe(0)
  })

  it('枚举字段取主导帧（t<0.5 起始帧，t≥0.5 目标帧）', () => {
    const a = frame({ velum: 'raised', airflow: 'oral' })
    const b = frame({ velum: 'lowered', airflow: 'nasal' })
    expect(interpolateKeyframes(a, b, 0.4).velumLowered).toBe(false)
    expect(interpolateKeyframes(a, b, 0.6).velumLowered).toBe(true)
    expect(interpolateKeyframes(a, b, 0.6).airflow).toBe('nasal')
  })

  it('插值超出 [0,1] 的 t 被钳制', () => {
    const a = frame({ jaw: 0 })
    const b = frame({ jaw: 1 })
    expect(interpolateKeyframes(a, b, 2).jaw).toBe(1)
    expect(interpolateKeyframes(a, b, -1).jaw).toBe(0)
  })
})

describe('buildTimeline / sampleTimeline', () => {
  it('hold 期返回当前帧 t=0；过渡期返回 (a, a+1, 0<t<1)', () => {
    const { entries } = buildTimeline([frame({ holdMs: 400 }), frame({ holdMs: 600 })])
    expect(sampleTimeline(entries, 100)).toEqual({ a: 0, b: 0, t: 0 })
    const inTransition = sampleTimeline(entries, 400 + 80)
    expect(inTransition).toEqual({ a: 0, b: 1, t: 0.5 })
    expect(sampleTimeline(entries, 700)).toEqual({ a: 1, b: 1, t: 0 })
  })

  it('超出总时长的采样返回 null', () => {
    const { entries, totalMs } = buildTimeline([frame({ holdMs: 300 })])
    expect(sampleTimeline(entries, totalMs + 1)).toBeNull()
  })
})

describe('buildSagittalGeometry', () => {
  it('下颌开合映射为旋转角度，双唇闭合帧 lipClosed', () => {
    const closed = buildSagittalGeometry(
      interpolateKeyframes(frame({ jaw: 0, lips: { aperture: 0, rounding: 0, contact: 'bilabial' } }), frame({ jaw: 0, lips: { aperture: 0, rounding: 0, contact: 'bilabial' } }), 0),
    )
    expect(closed.lipClosed).toBe(true)
    expect(closed.jawRotateDeg).toBe(0)

    const open = buildSagittalGeometry(
      interpolateKeyframes(frame({ jaw: 1 }), frame({ jaw: 1 }), 0),
    )
    expect(open.jawRotateDeg).toBeGreaterThan(10)
    expect(open.lipClosed).toBe(false)
  })

  it('软腭下降打开鼻咽通道并给鼻腔气流路径', () => {
    const nasal = buildSagittalGeometry(
      interpolateKeyframes(frame({ velum: 'lowered', airflow: 'nasal' }), frame({ velum: 'lowered', airflow: 'nasal' }), 0),
    )
    expect(nasal.nasalPortOpen).toBe(true)
    expect(nasal.airflowLabel).toContain('鼻腔')
  })

  it('成阻帧给出收紧点标注', () => {
    const closure = buildSagittalGeometry(
      interpolateKeyframes(frame({ tongueTip: { place: 'alveolar', stricture: 'closure' } }), frame({ tongueTip: { place: 'alveolar', stricture: 'closure' } }), 0),
    )
    expect(closure.constriction?.label).toBe('成阻')
  })
})
