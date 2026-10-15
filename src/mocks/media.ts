/** 模拟媒体：合成 WAV 音频与 SVG 图片（MSW dev:mock 模式专用） */

/** 生成指定时长与频率的正弦波 WAV（16-bit PCM 单声道） */
export function makeToneWav(options: { durationSec?: number; freq?: number; sampleRate?: number }): Uint8Array {
  const { durationSec = 0.8, freq = 440, sampleRate = 8000 } = options
  const numSamples = Math.floor(durationSec * sampleRate)
  const buffer = new ArrayBuffer(44 + numSamples * 2)
  const view = new DataView(buffer)
  const writeString = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i))
  }
  writeString(0, 'RIFF')
  view.setUint32(4, 36 + numSamples * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(36, 'data')
  view.setUint32(40, numSamples * 2, true)
  for (let i = 0; i < numSamples; i += 1) {
    // 简单淡入淡出防爆音
    const fade = Math.min(1, Math.min(i, numSamples - i) / (sampleRate * 0.05))
    const value = Math.sin((2 * Math.PI * freq * i) / sampleRate) * fade * 0.5
    view.setInt16(44 + i * 2, value * 32767, true)
  }
  return new Uint8Array(buffer)
}

/** 生成一个简单的口型示意 SVG（演示用占位图） */
export function makeMouthSvg(label: string, color: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200" width="320" height="200">
  <rect width="320" height="200" fill="#fafafa"/>
  <ellipse cx="160" cy="100" rx="120" ry="66" fill="${color}" opacity="0.25" stroke="${color}" stroke-width="3"/>
  <ellipse cx="160" cy="100" rx="70" ry="30" fill="#37474f" opacity="0.75"/>
  <text x="160" y="182" text-anchor="middle" font-size="16" fill="#546e7a">${label}</text>
</svg>`
}

/** 1x1 透明 PNG（共振峰图片占位） */
export const TINY_PNG = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='), (c) => c.charCodeAt(0))

/** 按 mediaId 稳定推导音频频率，便于「试听不同关卡不同音高」 */
export function freqForMediaId(mediaId: string): number {
  let hash = 0
  for (let i = 0; i < mediaId.length; i += 1) hash = (hash * 31 + mediaId.charCodeAt(i)) % 360
  return 220 + hash
}
