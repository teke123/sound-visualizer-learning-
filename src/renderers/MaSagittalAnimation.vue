<script setup lang="ts">
/**
 * MaSagittalAnimation：ma 发音动作 2D 正中矢状面交互动画（FR-603 构形内容媒体）。
 * 由内容契约 articulation.media[].component = 'ma-sagittal' 挂载（ArticulationFigure 注册表）；
 * 媒体资产本身（backend/assets/ma/ma-sagittal.html）是同源动画的规范存档。
 *
 * 几何与时序数学移植自原始 SVG 动画（参考 ma-articulation-preview.html 提取）：
 * 下颌绕髁突隐式锚点旋转、软腭沿曲线中线增厚抬升、舌面控制点随张口度插值、
 * 气流路径随鼻/口通路开闭淡入淡出。DOM 定位用 data-ma 属性，多实例（比较页两侧）不串。
 * 尊重 prefers-reduced-motion：默认停在 m 姿态，由学习者手动播放。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { QBtn, QCheckbox, QSelect } from 'quasar'
import { usePreferredReducedMotion } from '@vueuse/core'

defineProps<{
  /** 无障碍说明（媒体条目的 altText） */
  label?: string
}>()

const uid = `ma-sg-${Math.random().toString(36).slice(2, 8)}`
const rootEl = ref<HTMLElement | null>(null)

const reducedMotion = usePreferredReducedMotion()

const N_FRAMES = 180
const DURATION = 1.2 // 1× 速度下一个完整动作的秒数

const progressValue = ref(0)
const phaseText = ref('m')
const phaseDetail = ref('双唇闭合，气流经鼻腔')
const playing = ref(true)
const looping = ref(true)
const speed = ref(0.25)

const speedOptions = [
  { label: '0.125×', value: 0.125 },
  { label: '0.25×', value: 0.25 },
  { label: '0.5×', value: 0.5 },
  { label: '1×', value: 1 },
]

let progress = 0
let last = 0
let rafHandle = 0
let resizeObserver: ResizeObserver | null = null
let phase = ''

const clamp = (x: number) => Math.max(0, Math.min(1, x))
const mix = (a: number, b: number, t: number) => a + (b - a) * t
const smooth = (x: number, a: number, b: number) => {
  const t = clamp((x - a) / (b - a))
  return t * t * (3 - 2 * t)
}
const fmt = (n: number) => Number(n.toFixed(2))
const xy = (p: readonly [number, number] | number[]) => `${fmt(p[0])} ${fmt(p[1])}`
const curve = (pts: number[][]) => `C${pts.map(xy).join(' ')}`

/** 在组件根内按 data-ma 定位动态元素（等价原版的 $('#ma-xxx')） */
function el(key: string): SVGElement | null {
  return rootEl.value?.querySelector(`[data-ma="${key}"]`) ?? null
}

// 下颌运动由牙齿、唇、颏和口底前部共享；髁突位于本剖面外侧，是隐藏的运动锚点。
function jawPoint(x: number, y: number, j: number): [number, number] {
  const a = (-12.5 * j * Math.PI) / 180
  const dx = x - 520
  const dy = y - 270
  return [520 + dx * Math.cos(a) - dy * Math.sin(a) - 6 * j, 270 + dx * Math.sin(a) + dy * Math.cos(a) + 4 * j]
}

// 沿弯曲中线构造软腭：抬升过程中厚度保持存在，端点插值时不塌缩。
function velum(v: number): { d: string; tip: [number, number] } {
  const p0: [number, number] = [423, 251]
  const p1: [number, number] = [477, 251]
  const p2: [number, number] = [mix(511, 521, v), mix(286, 266, v)]
  const p3: [number, number] = [mix(524, 559, v), mix(324, 268, v)]
  const upper: [number, number][] = []
  const lower: [number, number][] = []
  let endNormal: [number, number] = [0, 0]
  let endTangent: [number, number] = [0, 0]
  for (let i = 0; i <= 32; i++) {
    const t = i / 32
    const u = 1 - t
    const x = u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0]
    const y = u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]
    const dx = 3 * u * u * (p1[0] - p0[0]) + 6 * u * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0])
    const dy = 3 * u * u * (p1[1] - p0[1]) + 6 * u * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1])
    const len = Math.hypot(dx, dy)
    const nx = dy / len
    const ny = -dx / len
    const w = mix(11, mix(7, 10, v), t)
    upper.push([x + nx * w, y + ny * w])
    lower.push([x - nx * w, y - ny * w])
    if (i === 32) {
      endNormal = [nx, ny]
      endTangent = [dx / len, dy / len]
    }
  }
  const cap: [number, number][] = []
  const r = mix(7, 10, v)
  for (let i = 1; i < 9; i++) {
    const a = (Math.PI * i) / 9
    cap.push([p3[0] + r * (endNormal[0] * Math.cos(a) + endTangent[0] * Math.sin(a)),
      p3[1] + r * (endNormal[1] * Math.cos(a) + endTangent[1] * Math.sin(a))])
  }
  return { d: `M${xy(upper[0]!)} L${[...upper.slice(1), ...cap, ...lower.reverse()].map(xy).join(' L')} Z`, tip: p3 }
}

function setAttr(key: string, attr: string, value: string | number) {
  el(key)?.setAttribute(attr, String(value))
}

function render(t: number) {
  progress = clamp(t)
  const j = smooth(progress, 0.24, 0.66)
  const v = smooth(progress, 0.23, 0.6)
  const tongue = smooth(progress, 0.12, 0.66)
  const P = (x: number, y: number) => jawPoint(x, y, j)
  const lowerFront = P(146, 300)
  const lowerInner = P(190, 298)
  const chin = [P(151, 315), P(159, 329), P(157, 348), P(164, 365), P(173, 388), P(199, 402), P(228, 409), P(275, 423), P(332, 419), P(375, 433)]
  const lowerFace = `M${xy(lowerFront)} ${curve(chin.slice(0, 3))} ${curve(chin.slice(3, 6))} ${curve(chin.slice(6, 9))} C${xy(chin[9]!)} 429 490 440 528 C450 553 455 578 458 598`
  setAttr('lower-face', 'd', lowerFace)
  setAttr('head-fill', 'd', `M238 36 C229 78 201 123 175 156 C157 178 126 195 123 213 C120 229 137 242 157 238 C172 234 178 244 173 257 C171 265 165 271 164 277 C155 279 146 281 143 287 C140 291 142 297 146 300 L${xy(lowerFront)} ${lowerFace.substring(lowerFace.indexOf(' C') + 1)} L626 598 L622 377 C620 347 611 318 606 284 C602 251 607 219 620 178 L640 36 Z`)

  const floor = [P(375, 421), P(309, 416), P(255, 390), P(221, 365), P(208, 342), lowerInner]
  setAttr('cavity', 'd', `M155 238 C177 235 187 211 204 185 C236 144 282 132 337 136 C375 138 399 145 412 169 C425 194 437 199 460 212 C489 228 516 225 537 240 C560 256 567 278 568 304 C570 342 580 373 582 411 C584 445 581 478 578 504 L581 598 L529 598 C527 562 518 520 490 478 C474 459 461 449 446 443 ${curve(floor.slice(0, 3))} ${curve(floor.slice(3, 6))} C${xy(P(179, 304))} ${xy(P(159, 304))} ${xy(lowerFront)} L146 300 C159 304 179 304 190 298 C198 285 195 278 190 275 C180 270 169 271 173 257 C177 245 169 237 155 238 Z`)

  const angle = -12.5 * j
  setAttr('jaw', 'transform', `translate(${fmt(-6 * j)} ${fmt(4 * j)}) rotate(${fmt(angle)} 520 270)`)

  // 舌前部跟随下颌支承，舌根与口底保持连续；准备动作先于唇释放开始。
  const tip = P(219, 337)
  tip[1] += 2 * tongue
  const A = [mix(239, 259, tongue), mix(333, 392, tongue)]
  const B = [mix(268, 296, tongue), mix(322, 378, tongue)]
  const C = [mix(305, 335, tongue), mix(322, 378, tongue)]
  const D = [mix(347, 382, tongue), mix(322, 377, tongue)]
  const E = [mix(381, 426, tongue), mix(332, 388, tongue)]
  const F = [mix(411, 452, tongue), mix(353, 409, tongue)]
  const G = [mix(447, 478, tongue), mix(378, 430, tongue)]
  const H = [mix(474, 489, tongue), mix(412, 449, tongue)]
  const I = [mix(485, 490, tongue), mix(448, 473, tongue)]
  const surface = `M${xy(tip)} ${curve([A, B, C])} ${curve([D, E, F])} ${curve([G, H, I])}`
  setAttr('tongue-surface', 'd', surface)
  setAttr('tongue-fill', 'd', `${surface} C490 486 496 497 502 505 C479 499 467 477 450 461 C433 445 ${xy(P(401, 438))} ${xy(P(365, 425))} C${xy(P(303, 417))} ${xy(P(247, 388))} ${xy(P(225, 361))} Q${xy(P(214, 346))} ${xy(tip)} Z`)
  setAttr('floor', 'd', `M${xy(P(227, 372))} C${xy(P(259, 400))} ${xy(P(319, 421))} ${xy(P(372, 426))}`)
  setAttr('tongue-label', 'x', String(mix(352, 370, tongue)))
  setAttr('tongue-label', 'y', String(mix(383, 431, tongue)))

  const epi = 2 * tongue
  setAttr('epiglottis', 'd', `M514 541 C503 517 503 493 ${495 + epi} 480 C${490 + epi} 469 ${492 + epi} 456 ${497 + epi} 451 C${503 + epi} 448 ${507 + epi} 456 ${505 + epi} 465 C${502 + epi} 478 509 494 514 509 L521 536 Z`)
  const palate = velum(v)
  setAttr('soft-palate', 'd', palate.d)
  setAttr('palate-leader', 'd', `M594 222 L577 222 L${xy([palate.tip[0] - 21, palate.tip[1] - 8])}`)
  setAttr('lip-leader', 'd', 'M123 280 L136 280 L151 291')

  const trunk = 'M551 580 C548 554 544 530 545 506 C547 469 551 438 549 406'
  const gapX = (palate.tip[0] + mix(7, 10, v) + 567) / 2
  const tipY = palate.tip[1]
  const nasal = `M549 406 C548 369 552 349 ${fmt(gapX)} ${fmt(tipY + 15)} C${fmt(gapX + 1)} ${fmt(tipY - 4)} 559 269 540 254 C530 245 510 243 489 237 C447 224 412 217 371 220 C313 222 267 236 221 243 C193 247 170 245 145 241 L112 237`
  const mouthY = (300 + lowerFront[1]) / 2
  const passageY = Math.max(316, mouthY)
  const oral = `M549 406 C548 373 535 350 509 338 C460 318 398 316 332 321 C270 326 238 ${fmt(passageY)} 216 ${fmt(passageY)} C205 ${fmt(passageY)} 196 ${fmt(passageY)} 185 ${fmt(passageY)} C170 ${fmt(passageY)} 160 ${fmt(mouthY)} 143 ${fmt(mouthY)} L113 ${fmt(mouthY)}`
  for (const key of ['trunk-guide', 'trunk-flow']) setAttr(key, 'd', trunk)
  for (const key of ['nasal-guide', 'nasal-dashes']) setAttr(key, 'd', nasal)
  for (const key of ['oral-guide', 'oral-dashes']) setAttr(key, 'd', oral)
  setAttr('nasal-arrow', 'd', 'M132 239 L112 237')
  setAttr('oral-arrow', 'd', `M134 ${fmt(mouthY)} L113 ${fmt(mouthY)}`)
  const nasalAlpha = 1 - smooth(v, 0.42, 0.94)
  const oralAlpha = smooth(j, 0.015, 0.38)
  setAttr('nasal-flow', 'opacity', String(nasalAlpha))
  setAttr('oral-flow', 'opacity', String(oralAlpha))
  // 所有运动标记共用同一时间轴，暂停时虚线也同步停住。
  const dash = fmt(-progress * 360)
  for (const key of ['trunk-flow', 'nasal-dashes', 'oral-dashes']) setAttr(key, 'stroke-dashoffset', dash)

  const key = progress < 0.255 ? 'm' : progress < 0.66 ? 'transition' : 'a'
  if (phase !== key) {
    phase = key
    phaseText.value = key === 'transition' ? 'm → a' : key
    phaseDetail.value = key === 'm' ? '双唇闭合，气流经鼻腔' : key === 'transition' ? '双唇打开，舌体降低，软腭抬升' : '口腔打开，气流经口腔'
  }
  progressValue.value = Math.round(progress * N_FRAMES)
}

function tick(now: number) {
  if (!playing.value) return
  const dt = Math.min((now - last) / 1000, 0.08)
  last = now
  let next = progress + (dt * speed.value) / DURATION
  if (next >= 1) {
    if (looping.value) next %= 1
    else {
      render(1)
      setPlaying(false)
      return
    }
  }
  render(next)
  rafHandle = requestAnimationFrame(tick)
}

function setPlaying(next: boolean) {
  playing.value = next
  cancelAnimationFrame(rafHandle)
  if (playing.value) {
    last = performance.now()
    rafHandle = requestAnimationFrame(tick)
  }
}

function togglePlay() {
  if (!playing.value && progress >= 1) render(0)
  setPlaying(!playing.value)
}

function onSeek(value: number) {
  setPlaying(false)
  render(value / N_FRAMES)
}

/** SVG 内文字随宽度反缩放，保持屏幕上的实际字号稳定 */
function resizeLabels() {
  const svg = rootEl.value?.querySelector('.anatomy')
  if (!svg || !rootEl.value) return
  const width = svg.getBoundingClientRect().width
  if (width > 0) rootEl.value.style.setProperty('--ma-svg-scale', String(586 / width))
}

onMounted(() => {
  if (!rootEl.value) return
  resizeObserver = new ResizeObserver(resizeLabels)
  resizeObserver.observe(rootEl.value)
  resizeLabels()
  render(0)
  if (reducedMotion.value) playing.value = false
  setPlaying(playing.value)
})

onBeforeUnmount(() => {
  playing.value = false
  cancelAnimationFrame(rafHandle)
  resizeObserver?.disconnect()
  resizeObserver = null
})
</script>

<template>
  <figure class="ma-sagittal" ref="rootEl" :aria-label="label ?? 'ma 正中矢状面发音动画'">
    <svg class="anatomy" xmlns="http://www.w3.org/2000/svg" viewBox="72 65 586 545" role="img" :aria-labelledby="`${uid}-title`">
      <title :id="`${uid}-title`">{{ label ?? 'ma 发音动作，正中矢状面' }}</title>
      <desc>面部朝左。发 m 时双唇闭合，软腭降低，气流经鼻腔；过渡到 a 时下颌打开，舌体降低，软腭抬起关闭鼻咽通路，气流从口腔流出。形态与时序为教学示意。</desc>
      <defs>
        <linearGradient :id="`${uid}-root-blend`" x1="0" y1="430" x2="0" y2="507" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="var(--ma-tongue)" />
          <stop offset="1" stop-color="var(--ma-tissue)" />
        </linearGradient>
        <marker :id="`${uid}-arrow`" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M1 1 L7 4 L1 7" fill="none" stroke="var(--ma-air)" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" />
        </marker>
      </defs>

      <path data-ma="head-fill" fill="var(--ma-tissue)" />
      <path data-ma="cavity" fill="var(--ma-background)" />
      <path class="edge" d="M238 36 C229 78 201 123 175 156 C157 178 126 195 123 213 C120 229 137 242 157 238 C172 234 178 244 173 257 C171 265 165 271 164 277 C155 279 146 281 143 287" />
      <path class="edge" d="M640 36 L620 178 C607 219 602 251 606 284 C611 318 620 347 622 377 L626 598" />
      <path data-ma="lower-face" class="edge" />
      <path class="fine" d="M157 238 C177 235 187 211 204 185 C236 144 282 132 337 136 C375 138 399 145 412 169 C425 194 437 199 460 212 C489 228 516 225 537 240 C560 256 567 278 568 304 C570 342 580 373 582 411 C584 445 581 478 578 504 L581 598" />

      <path fill="var(--ma-bone)" stroke="var(--ma-bone-edge)" stroke-width="1.3" d="M190 275 C251 249 335 237 424 240 L424 262 C343 254 267 258 213 285 L195 291 Z" />
      <path class="fine" opacity=".55" d="M206 270 C265 250 343 246 408 249" />
      <path data-ma="soft-palate" fill="var(--ma-velum)" stroke="var(--ma-velum-edge)" stroke-width="1.6" stroke-linejoin="round" />
      <path fill="var(--ma-lip)" opacity=".45" d="M190 275 C201 273 211 279 216 286 L214 294 C205 296 196 294 192 290 Z" />
      <path class="tooth" d="M195 284 C201 281 209 282 213 286 L211 308 Q205 314 197 309 Z" />

      <g data-ma="jaw">
        <path fill="var(--ma-bone)" stroke="var(--ma-bone-edge)" stroke-width="1.3" d="M195 331 C186 342 186 359 196 375 C203 386 216 393 231 395 L237 384 C222 377 215 365 214 349 L214 332 Z" />
        <path fill="var(--ma-lip)" opacity=".5" d="M185 320 C193 316 204 321 216 332 L217 345 C207 350 194 341 190 335 Z" />
        <path class="tooth" d="M199 321 Q207 317 215 321 L216 338 Q209 344 201 338 Z" />
        <path class="lip" d="M146 300 C159 304 179 304 190 298 C196 307 191 315 183 319 C169 324 157 320 151 315 C148 310 146 306 146 300 Z" />
      </g>

      <path data-ma="tongue-fill" :fill="`url(#${uid}-root-blend)`" />
      <path data-ma="tongue-surface" fill="none" stroke="var(--ma-tongue-edge)" stroke-width="1.7" stroke-linecap="round" />
      <path data-ma="floor" class="fine" opacity=".55" />
      <path data-ma="epiglottis" fill="var(--ma-tissue)" stroke="var(--ma-tissue-edge)" stroke-width="1.2" />
      <path class="fine" d="M521 540 C527 553 529 574 529 598" />

      <path class="lip" d="M143 287 C155 280 178 285 190 298 C179 304 159 304 146 300 C142 297 140 291 143 287 Z" />

      <g aria-hidden="true">
        <path data-ma="trunk-guide" class="flow flow-guide" />
        <path data-ma="trunk-flow" class="flow flow-motion" />
        <g data-ma="nasal-flow">
          <path data-ma="nasal-guide" class="flow flow-guide" />
          <path data-ma="nasal-dashes" class="flow flow-motion" />
          <path data-ma="nasal-arrow" class="flow" :marker-end="`url(#${uid}-arrow)`" />
        </g>
        <g data-ma="oral-flow">
          <path data-ma="oral-guide" class="flow flow-guide" />
          <path data-ma="oral-dashes" class="flow flow-motion" />
          <path data-ma="oral-arrow" class="flow" :marker-end="`url(#${uid}-arrow)`" />
        </g>
        <text class="label" x="310" y="188" text-anchor="middle">鼻腔</text>
        <text data-ma="tongue-label" class="label" text-anchor="middle">舌</text>
        <path data-ma="palate-leader" class="leader" />
        <text class="label" x="594" y="215">软腭</text>
        <path data-ma="lip-leader" class="leader optional-label" />
        <text class="label optional-label" x="132" y="273" text-anchor="end">双唇</text>
      </g>
    </svg>

    <figcaption class="readout">
      <span>
        <span class="phase">{{ phaseText }}</span>
        <span class="dot"> · </span>{{ phaseDetail }}
      </span>
    </figcaption>

    <div class="timeline">
      <input
        class="progress"
        type="range"
        min="0"
        :max="N_FRAMES"
        step="1"
        :value="progressValue"
        aria-label="动画进度"
        :aria-valuetext="`${Math.round((progressValue / N_FRAMES) * 100)}%`"
        @input="onSeek(Number(($event.target as HTMLInputElement).value))"
      />
    </div>

    <div class="transport">
      <QBtn unelevated no-caps color="primary" size="13px" class="transport-btn" :icon="playing ? 'pause' : 'play_arrow'" @click="togglePlay">
        {{ playing ? '暂停' : '播放' }}
      </QBtn>
      <QSelect
        v-model.number="speed"
        :options="speedOptions"
        emit-value
        map-options
        dense
        outlined
        color="primary"
        class="speed-select"
        aria-label="播放速度"
      />
      <QCheckbox v-model="looping" label="循环" dense color="primary" class="loop-check" />
    </div>
  </figure>
</template>

<style scoped lang="sass">
/* 调色板与 backend/assets/ma/ma-sagittal.html（原始 codex 主题浅色推导值）保持一致 */
.ma-sagittal
  --ma-ink: #37474f
  --ma-tissue: #eceff1
  --ma-tissue-edge: #78909c
  --ma-bone: #f1ecdc
  --ma-bone-edge: #8ba0ab
  --ma-tongue: #e7a59e
  --ma-tongue-edge: #a6827f
  --ma-lip: #e6999b
  --ma-velum: #bce0cd
  --ma-velum-edge: #90b8a4
  --ma-air: #1f9eb2
  --ma-background: #fff
  margin: 0
  max-width: 560px
  width: 100%
  margin-inline: auto
  color: #37474f

.anatomy
  width: 100%
  height: auto
  display: block

.edge
  fill: none
  stroke: var(--ma-tissue-edge)
  stroke-width: 1.7
  stroke-linecap: round
  stroke-linejoin: round

.fine
  fill: none
  stroke: var(--ma-tissue-edge)
  stroke-width: 1.1
  stroke-linecap: round
  stroke-linejoin: round

.tooth
  fill: var(--ma-bone)
  stroke: var(--ma-bone-edge)
  stroke-width: 1.3
  stroke-linejoin: round

.lip
  fill: var(--ma-lip)
  stroke: var(--ma-tongue-edge)
  stroke-width: 1.3
  stroke-linejoin: round

.label
  fill: var(--ma-ink)
  font-size: calc(16px * var(--ma-svg-scale, 1))

.leader
  fill: none
  stroke: var(--ma-tissue-edge)
  stroke-width: 1
  stroke-linecap: round

.flow
  fill: none
  stroke: var(--ma-air)
  stroke-width: 2.5
  stroke-linecap: round
  stroke-linejoin: round

.flow-guide
  opacity: .16
  stroke-width: 1.4

.flow-motion
  stroke-dasharray: 5 15

.readout
  display: flex
  justify-content: space-between
  align-items: baseline
  flex-wrap: wrap
  gap: 4px 16px
  margin: 8px 0 4px
  font-size: 14px

.phase
  font-weight: 600
  color: #00695c
  font-family: var(--font-ipa)

.dot
  color: #90a4ae

.progress
  width: 100%
  accent-color: #00897b

.transport
  display: flex
  align-items: center
  flex-wrap: wrap
  gap: 8px
  margin-top: 8px

.transport-btn
  min-height: 32px

.speed-select
  width: 110px

.loop-check
  margin-left: auto

@media (max-width: 440px)
  .transport
    gap: 6px
  .loop-check
    margin-left: 0
  .optional-label
    display: none
</style>
