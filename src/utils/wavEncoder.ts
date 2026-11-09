/**
 * WAV 无损封装：把 AudioWorklet 采集的 32 位浮点 PCM 片段封装为
 * 16-bit PCM 单声道 WAV（44 字节 RIFF 头 + 交错数据）。
 *
 * 浏览器 MediaRecorder 默认输出 Opus/AAC 有损流，针对听感而非测量，
 * 会丢弃擦音、送气等高频频谱细节并破坏相位信息；录音链路改在内存中
 * 用本模块直接封装原始 PCM 后上传，后端转码保持声学保真度。
 */

/** 标准 44 字节 RIFF/WAVE 头（fmt chunk 定长 16） */
const WAV_HEADER_SIZE = 44

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i))
}

/** 量化为 16 位有符号整数（对称范围：-1 → -32768，[0, 1) → 0..32767） */
function toInt16(sample: number): number {
  const clamped = Math.max(-1, Math.min(1, sample))
  return clamped < 0 ? Math.round(clamped * 0x8000) : Math.round(clamped * 0x7fff)
}

export function encodeWav(chunks: readonly Float32Array[], sampleRate: number): Blob {
  const totalSamples = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const buffer = new ArrayBuffer(WAV_HEADER_SIZE + totalSamples * 2)
  const view = new DataView(buffer)

  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + totalSamples * 2, true)
  writeAscii(view, 8, 'WAVE')
  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk 长度
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // 单声道
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // 字节率 = 采样率 × 声道 × 2 字节
  view.setUint16(32, 2, true) // 块对齐
  view.setUint16(34, 16, true) // 位深
  writeAscii(view, 36, 'data')
  view.setUint32(40, totalSamples * 2, true)

  let offset = WAV_HEADER_SIZE
  for (const chunk of chunks) {
    for (let i = 0; i < chunk.length; i += 1, offset += 2) {
      view.setInt16(offset, toInt16(chunk[i]!), true)
    }
  }
  return new Blob([buffer], { type: 'audio/wav' })
}
