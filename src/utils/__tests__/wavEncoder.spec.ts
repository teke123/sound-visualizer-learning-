/** WAV 无损封装单测：RIFF 头结构、多段拼接、16 位量化边界 */
import { describe, expect, it } from 'vitest'
import { encodeWav } from '../wavEncoder'

async function readHeader(blob: Blob): Promise<{ view: DataView; bytes: Uint8Array }> {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  return { view: new DataView(bytes.buffer), bytes }
}

function ascii(bytes: Uint8Array, offset: number, length: number): string {
  return String.fromCharCode(...bytes.subarray(offset, offset + length))
}

describe('encodeWav', () => {
  it('写入合法的 RIFF/PCM 单声道头', async () => {
    const blob = encodeWav([new Float32Array([0.5, -0.5])], 48_000)
    expect(blob.type).toBe('audio/wav')
    const { view, bytes } = await readHeader(blob)
    expect(ascii(bytes, 0, 4)).toBe('RIFF')
    expect(view.getUint32(4, true)).toBe(36 + 4) // 36 + data 大小（2 样本 × 2 字节）
    expect(ascii(bytes, 8, 4)).toBe('WAVE')
    expect(ascii(bytes, 12, 4)).toBe('fmt ')
    expect(view.getUint32(16, true)).toBe(16)
    expect(view.getUint16(20, true)).toBe(1) // PCM
    expect(view.getUint16(22, true)).toBe(1) // 单声道
    expect(view.getUint32(24, true)).toBe(48_000)
    expect(view.getUint32(28, true)).toBe(96_000) // 字节率
    expect(view.getUint16(32, true)).toBe(2) // 块对齐
    expect(view.getUint16(34, true)).toBe(16) // 位深
    expect(ascii(bytes, 36, 4)).toBe('data')
    expect(view.getUint32(40, true)).toBe(4)
  })

  it('多段 PCM 按顺序交错拼接', async () => {
    const blob = encodeWav([new Float32Array([0.5]), new Float32Array([-0.5, 0])], 44_100)
    const { view, bytes } = await readHeader(blob)
    expect(view.getUint32(40, true)).toBe(6)
    expect(bytes.length).toBe(44 + 6)
    expect(view.getInt16(44, true)).toBe(16384) // round(0.5 × 32767)
    expect(view.getInt16(46, true)).toBe(-16384)
    expect(view.getInt16(48, true)).toBe(0)
  })

  it('量化边界：±1 满幅、越界截断到满幅', async () => {
    const blob = encodeWav([new Float32Array([1, -1, 1.5, -1.5])], 44_100)
    const { view } = await readHeader(blob)
    expect(view.getInt16(44, true)).toBe(32767)
    expect(view.getInt16(46, true)).toBe(-32768)
    expect(view.getInt16(48, true)).toBe(32767)
    expect(view.getInt16(50, true)).toBe(-32768)
  })

  it('空输入只产出 44 字节头', async () => {
    const blob = encodeWav([], 44_100)
    const { view } = await readHeader(blob)
    expect(blob.size).toBe(44)
    expect(view.getUint32(40, true)).toBe(0)
  })
})
