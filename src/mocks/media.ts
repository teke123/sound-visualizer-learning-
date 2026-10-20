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

/* ------------------------- 三维构形占位模型（GLB） ------------------------- */

/** UV 球体网格：位置/法线烘焙平移与非均匀缩放（演示用占位，法线取近似值） */
function sphereGeometry(options: {
  radius: number
  scale: [number, number, number]
  center: [number, number, number]
  widthSegments?: number
  heightSegments?: number
}) {
  const { radius, scale: [sx, sy, sz], center: [cx, cy, cz], widthSegments = 16, heightSegments = 12 } = options
  const positions = new Float32Array((widthSegments + 1) * (heightSegments + 1) * 3)
  const normals = new Float32Array(positions.length)
  let offset = 0
  for (let iy = 0; iy <= heightSegments; iy += 1) {
    const v = iy / heightSegments
    for (let ix = 0; ix <= widthSegments; ix += 1) {
      const u = ix / widthSegments
      const x = -Math.cos(u * Math.PI * 2) * Math.sin(v * Math.PI)
      const y = Math.cos(v * Math.PI)
      const z = Math.sin(u * Math.PI * 2) * Math.sin(v * Math.PI)
      positions[offset] = x * radius * sx + cx
      positions[offset + 1] = y * radius * sy + cy
      positions[offset + 2] = z * radius * sz + cz
      const length = Math.hypot(x, y, z) || 1
      normals[offset] = x / length
      normals[offset + 1] = y / length
      normals[offset + 2] = z / length
      offset += 3
    }
  }
  const indices = new Uint16Array(widthSegments * heightSegments * 6)
  let index = 0
  for (let iy = 0; iy < heightSegments; iy += 1) {
    for (let ix = 0; ix < widthSegments; ix += 1) {
      const a = iy * (widthSegments + 1) + ix
      const b = a + 1
      const c = a + widthSegments + 1
      const d = c + 1
      indices[index++] = a
      indices[index++] = c
      indices[index++] = b
      indices[index++] = b
      indices[index++] = c
      indices[index++] = d
    }
  }
  return { positions, normals, indices }
}

/**
 * 生成一个最小合法的 GLB（glTF 2.0 二进制）：上颚 + 舌体两个椭球示意。
 * 演示用占位模型，供 three.js GLTFLoader 走通「/api/media → 渲染」链路。
 */
export function makeMouthGlb(): Uint8Array {
  const parts = [
    { color: [0.973, 0.733, 0.816], geometry: sphereGeometry({ radius: 1, scale: [1, 0.55, 0.8], center: [0, 0.32, 0] }) },
    { color: [0.898, 0.451, 0.451], geometry: sphereGeometry({ radius: 0.62, scale: [1, 0.5, 1.15], center: [0, -0.28, 0.1] }) },
  ]

  const chunks: Uint8Array[] = []
  const bufferViews: Array<{ buffer: number; byteOffset: number; byteLength: number }> = []
  const accessors: Array<{
    bufferView: number
    componentType: number
    count: number
    type: string
    min?: number[]
    max?: number[]
  }> = []
  const primitives: Array<{ attributes: { POSITION: number; NORMAL: number }; indices: number; material: number }> = []
  const materials: Array<{ pbrMetallicRoughness: { baseColorFactor: number[]; metallicFactor: number; roughnessFactor: number }; doubleSided: boolean }> = []
  let byteOffset = 0

  const pushView = (data: Uint8Array) => {
    bufferViews.push({ buffer: 0, byteOffset, byteLength: data.byteLength })
    chunks.push(data)
    byteOffset += data.byteLength
    return bufferViews.length - 1
  }

  parts.forEach((part, materialIndex) => {
    const { positions, normals, indices } = part.geometry
    const min = [Infinity, Infinity, Infinity]
    const max = [-Infinity, -Infinity, -Infinity]
    for (let i = 0; i < positions.length; i += 3) {
      for (let axis = 0; axis < 3; axis += 1) {
        const value = positions[i + axis]!
        if (value < min[axis]!) min[axis] = value
        if (value > max[axis]!) max[axis] = value
      }
    }
    const positionAccessor = accessors.push({
      bufferView: pushView(new Uint8Array(positions.buffer, positions.byteOffset, positions.byteLength)),
      componentType: 5126,
      count: positions.length / 3,
      type: 'VEC3',
      min,
      max,
    }) - 1
    const normalAccessor = accessors.push({
      bufferView: pushView(new Uint8Array(normals.buffer, normals.byteOffset, normals.byteLength)),
      componentType: 5126,
      count: normals.length / 3,
      type: 'VEC3',
    }) - 1
    const indexAccessor = accessors.push({
      bufferView: pushView(new Uint8Array(indices.buffer, indices.byteOffset, indices.byteLength)),
      componentType: 5123,
      count: indices.length,
      type: 'SCALAR',
    }) - 1
    primitives.push({ attributes: { POSITION: positionAccessor, NORMAL: normalAccessor }, indices: indexAccessor, material: materialIndex })
    materials.push({
      pbrMetallicRoughness: { baseColorFactor: [...part.color, 1], metallicFactor: 0, roughnessFactor: 0.55 },
      doubleSided: true,
    })
  })

  const gltf = {
    asset: { version: '2.0', generator: 'mock' },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0, name: 'articulation-placeholder' }],
    meshes: [{ primitives }],
    materials,
    buffers: [{ byteLength: byteOffset }],
    bufferViews,
    accessors,
  }

  // GLB 组包：12 字节头 + JSON 块（空格补齐 4 字节）+ BIN 块（零补齐；本生成器各段均为 4 的倍数）
  let jsonBytes = new TextEncoder().encode(JSON.stringify(gltf))
  const jsonPad = (4 - (jsonBytes.byteLength % 4)) % 4
  if (jsonPad > 0) {
    const padded = new Uint8Array(jsonBytes.byteLength + jsonPad)
    padded.set(jsonBytes)
    padded.fill(0x20, jsonBytes.byteLength)
    jsonBytes = padded
  }
  const bin = new Uint8Array(byteOffset)
  let binOffset = 0
  for (const chunk of chunks) {
    bin.set(chunk, binOffset)
    binOffset += chunk.byteLength
  }
  const total = 12 + 8 + jsonBytes.byteLength + 8 + bin.byteLength
  const glb = new Uint8Array(total)
  const view = new DataView(glb.buffer)
  view.setUint32(0, 0x46546c67, true) // 'glTF'
  view.setUint32(4, 2, true)
  view.setUint32(8, total, true)
  view.setUint32(12, jsonBytes.byteLength, true)
  view.setUint32(16, 0x4e4f534a, true) // 'JSON'
  glb.set(jsonBytes, 20)
  view.setUint32(20 + jsonBytes.byteLength, bin.byteLength, true)
  view.setUint32(24 + jsonBytes.byteLength, 0x004e4942, true) // 'BIN\0'
  glb.set(bin, 28 + jsonBytes.byteLength)
  return glb
}
