<script setup lang="ts">
/**
 * Model3DView：三维构形渲染器（FR-603 / FD-07）。
 * three.js 仅在本组件挂载时动态 import（按需代码分割，不拖慢首屏），
 * 经 GLTFLoader 加载 model3dMediaId 对应的 glTF/GLB 模型；
 * 支持拖拽旋转 / 滚轮缩放；遵循 prefers-reduced-motion（不自动旋转）。
 * 纯展示：不调 api、不读 store，模型地址由 props.src 提供。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePreferredReducedMotion } from '@vueuse/core'
import type { Mesh, Object3D, PerspectiveCamera, Scene, WebGLRenderer } from 'three'
import type { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import type { OrbitControls } from 'three/addons/controls/OrbitControls.js'

const props = defineProps<{
  /** glTF/GLB 模型地址（model3dMediaId 经 mediaResolver 解析） */
  src: string
  /** 无障碍说明（缺省用默认文案） */
  label?: string
}>()

const reducedMotion = usePreferredReducedMotion()
const status = ref<'loading' | 'ready' | 'error'>('loading')
const errorMessage = ref('')
const container = ref<HTMLDivElement | null>(null)

// three 资源句柄：挂载并懒加载完成后填充，卸载时全部释放
let threeModule: typeof import('three') | null = null
let renderer: WebGLRenderer | null = null
let scene: Scene | null = null
let camera: PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let loader: GLTFLoader | null = null
let model: Object3D | null = null
let resizeObserver: ResizeObserver | null = null
let rafHandle = 0
let disposed = false

onMounted(async () => {
  if (!container.value) return
  try {
    const [three, gltfModule, orbitModule] = await Promise.all([
      import('three'),
      import('three/addons/loaders/GLTFLoader.js'),
      import('three/addons/controls/OrbitControls.js'),
    ])
    if (disposed || !container.value) return
    threeModule = three

    try {
      renderer = new three.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      status.value = 'error'
      errorMessage.value = '当前浏览器不支持 WebGL，无法显示三维模型'
      return
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    const { clientWidth: width, clientHeight: height } = container.value
    renderer.setSize(Math.max(width, 1), Math.max(height, 1))
    container.value.appendChild(renderer.domElement)

    scene = new three.Scene()
    const hemisphere = new three.HemisphereLight(0xffffff, 0xb0bec5, 2.4)
    const key = new three.DirectionalLight(0xffffff, 2.2)
    key.position.set(2.5, 3, 4)
    scene.add(hemisphere, key)

    camera = new three.PerspectiveCamera(40, Math.max(width / Math.max(height, 1), 1), 0.01, 100)
    camera.position.set(0, 0.55, 3.1)

    controls = new orbitModule.OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.enablePan = false
    controls.minDistance = 1.4
    controls.maxDistance = 6
    controls.autoRotate = !reducedMotion.value
    controls.autoRotateSpeed = 1.2
    // 学习者上手拖拽后停掉自动旋转，避免抢镜头
    controls.addEventListener('start', () => {
      if (controls) controls.autoRotate = false
    })

    loader = new gltfModule.GLTFLoader()
    loadModel()

    resizeObserver = new ResizeObserver(fitCanvas)
    resizeObserver.observe(container.value)
    animate()
  } catch {
    if (!disposed) {
      status.value = 'error'
      errorMessage.value = '三维引擎加载失败，请检查网络后重试'
    }
  }
})

function fitCanvas() {
  if (!container.value || !renderer || !camera) return
  const { clientWidth: width, clientHeight: height } = container.value
  if (width === 0 || height === 0) return
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
}

function animate() {
  rafHandle = requestAnimationFrame(animate)
  controls?.update()
  if (renderer && scene && camera) renderer.render(scene, camera)
}

function loadModel() {
  if (!threeModule || !scene || !loader) return
  const THREE = threeModule
  status.value = 'loading'
  loader.load(
    props.src,
    (gltf) => {
      if (disposed || !scene) return
      disposeModel()
      const next = gltf.scene
      // 归一化取景：模型来源多样，统一居中缩放到相机可视范围
      const box = new THREE.Box3().setFromObject(next)
      const size = box.getSize(new THREE.Vector3())
      const center = box.getCenter(new THREE.Vector3())
      const maxDim = Math.max(size.x, size.y, size.z) || 1
      const scale = 1.7 / maxDim
      next.scale.setScalar(scale)
      next.position.set(-center.x * scale, -center.y * scale, -center.z * scale)
      scene.add(next)
      model = next
      status.value = 'ready'
    },
    undefined,
    () => {
      if (!disposed) {
        status.value = 'error'
        errorMessage.value = '三维模型加载失败，请稍后重试'
      }
    },
  )
}

function disposeModel() {
  if (!model) return
  model.traverse((obj) => {
    const mesh = obj as Mesh
    mesh.geometry?.dispose()
    const material = mesh.material
    if (Array.isArray(material)) material.forEach((item) => item.dispose())
    else material?.dispose()
  })
  model.removeFromParent()
  model = null
}

watch(
  () => props.src,
  () => loadModel(),
)
watch(reducedMotion, (value) => {
  if (controls) controls.autoRotate = !value
})

onBeforeUnmount(() => {
  disposed = true
  cancelAnimationFrame(rafHandle)
  resizeObserver?.disconnect()
  resizeObserver = null
  controls?.dispose()
  controls = null
  disposeModel()
  scene = null
  if (renderer) {
    renderer.dispose()
    renderer.domElement.remove()
    renderer = null
  }
})
</script>

<template>
  <figure class="model3d-view">
    <div ref="container" class="model3d-canvas" role="img" :aria-label="label ?? '三维构形模型'"></div>
    <figcaption class="model3d-caption">
      <span v-if="status === 'loading'">三维模型加载中…</span>
      <span v-else-if="status === 'error'" class="error">{{ errorMessage }}</span>
      <span v-else>拖拽旋转 · 滚轮缩放</span>
    </figcaption>
  </figure>
</template>

<style scoped lang="sass">
.model3d-view
  width: 100%
  max-width: 420px

.model3d-canvas
  position: relative
  width: 100%
  height: 300px
  background: #fff
  border: 1px solid #e0e0e0
  border-radius: 12px
  overflow: hidden
  canvas
    display: block

.model3d-caption
  font-size: 13px
  color: #78909c
  margin-top: 6px
  text-align: center
  .error
    color: #c62828
</style>
