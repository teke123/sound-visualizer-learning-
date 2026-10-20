import { describe, expect, it } from 'vitest'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import type { GLTF } from 'three/addons/loaders/GLTFLoader.js'
import { makeMouthGlb } from '../media'

/** 按 glTF 2.0 二进制容器规范校验 mock 占位模型组包正确性 */
describe('makeMouthGlb', () => {
  it('GLB 头部：魔数、版本号、总长度一致且 4 字节对齐', () => {
    const glb = makeMouthGlb()
    const view = new DataView(glb.buffer, glb.byteOffset, glb.byteLength)
    expect(view.getUint32(0, true)).toBe(0x46546c67) // 'glTF'
    expect(view.getUint32(4, true)).toBe(2)
    expect(view.getUint32(8, true)).toBe(glb.byteLength)
    expect(glb.byteLength % 4).toBe(0)
  })

  it('JSON 块可解析，asset/mesh/materials 齐备', () => {
    const glb = makeMouthGlb()
    const view = new DataView(glb.buffer, glb.byteOffset, glb.byteLength)
    const jsonLength = view.getUint32(12, true)
    expect(view.getUint32(16, true)).toBe(0x4e4f534a) // 'JSON'
    expect(jsonLength % 4).toBe(0)
    const gltf = JSON.parse(new TextDecoder().decode(glb.subarray(20, 20 + jsonLength)))
    expect(gltf.asset.version).toBe('2.0')
    // 上颚 + 舌体两个椭球
    expect(gltf.meshes[0].primitives).toHaveLength(2)
    expect(gltf.materials).toHaveLength(2)
  })

  it('BIN 块长度与 buffers 声明一致，所有 accessor 引用不越界', () => {
    const glb = makeMouthGlb()
    const view = new DataView(glb.buffer, glb.byteOffset, glb.byteLength)
    const jsonLength = view.getUint32(12, true)
    const binOffset = 20 + jsonLength
    expect(view.getUint32(binOffset + 4, true)).toBe(0x004e4942) // 'BIN\0'
    const binLength = view.getUint32(binOffset, true)
    expect(12 + 8 + jsonLength + 8 + binLength).toBe(glb.byteLength)

    const gltf = JSON.parse(new TextDecoder().decode(glb.subarray(20, 20 + jsonLength)))
    expect(gltf.buffers[0].byteLength).toBe(binLength)
    for (const accessor of gltf.accessors) {
      const bufferView = gltf.bufferViews[accessor.bufferView]
      expect(bufferView.byteOffset + bufferView.byteLength).toBeLessThanOrEqual(binLength)
      expect(bufferView.byteOffset % 4).toBe(0)
    }
    // POSITION accessor 必须带 min/max（glTF 规范要求）
    const positionIndices = gltf.meshes[0].primitives.map((p: { attributes: { POSITION: number } }) => p.attributes.POSITION)
    expect(positionIndices).toHaveLength(2)
    for (const index of positionIndices) {
      expect(gltf.accessors[index].min).toHaveLength(3)
      expect(gltf.accessors[index].max).toHaveLength(3)
    }
  })

  it('生产同款 GLTFLoader 可解析，得到上颚 + 舌体两个网格', async () => {
    const glb = makeMouthGlb()
    const gltf = await new Promise<GLTF>((resolve, reject) =>
      new GLTFLoader().parse(glb.buffer, '', resolve, reject),
    )
    const meshes: unknown[] = []
    gltf.scene.traverse((obj) => {
      if ((obj as { isMesh?: boolean }).isMesh) meshes.push(obj)
    })
    expect(meshes).toHaveLength(2)
  })
})
