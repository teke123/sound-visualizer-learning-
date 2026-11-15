<script setup lang="ts">
/**
 * 发音示范（外部口型）：单元音 a 的正视与侧视短视频循环播放 + 发音要点。
 * 素材在 public/media/teacher/；口腔内部剖面图暂不接入。
 * 尊重 prefers-reduced-motion：系统减弱动效时默认停在首帧。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { QBtn } from 'quasar'
import { usePreferredReducedMotion } from '@vueuse/core'

const rootEl = ref<HTMLElement | null>(null)
const playing = ref(true)
const reducedMotion = usePreferredReducedMotion()

/** 正视在前：学生先看正面口型，再看侧面确认下颌 */
const CLIPS = [
  { key: 'front', label: '正视', src: '/media/teacher/a_front.mp4' },
  { key: 'side', label: '侧视', src: '/media/teacher/a_side.mp4' },
]

const TIPS = [
  { tag: '嘴', text: '下颌打开，嘴张到能放进两指' },
  { tag: '舌', text: '舌体放平放低，舌尖轻抵下齿背' },
  { tag: '气', text: '气流从口腔中间出来，不跑鼻子' },
]

function videos(): HTMLVideoElement[] {
  return Array.from(rootEl.value?.querySelectorAll('video') ?? [])
}

function apply() {
  for (const v of videos()) {
    v.muted = true
    if (playing.value) {
      void v.play().catch(() => {
        /* 浏览器拒绝自动播放时保持静态首帧 */
      })
    } else {
      v.pause()
    }
  }
}

function toggle() {
  playing.value = !playing.value
  apply()
}

onMounted(() => {
  if (reducedMotion.value === 'reduce') playing.value = false
  apply()
})

onBeforeUnmount(() => {
  for (const v of videos()) v.pause()
})
</script>

<template>
  <section class="teacher-demo" ref="rootEl" aria-label="单元音 a 的发音示范">
    <div class="demo-head">
      <h2>发音示范 · a</h2>
      <QBtn
        flat
        dense
        no-caps
        color="teal-7"
        :label="playing ? '暂停' : '播放'"
        @click="toggle"
      />
    </div>

    <div class="demo-body">
      <div class="clip-row">
        <figure v-for="clip in CLIPS" :key="clip.key" class="clip">
          <video
            :src="clip.src"
            :aria-label="`${clip.label}示范`"
            class="clip-video"
            loop
            muted
            playsinline
            preload="metadata"
          />
          <figcaption class="clip-label">{{ clip.label }}</figcaption>
        </figure>
      </div>

      <ul class="tip-list">
        <li v-for="tip in TIPS" :key="tip.tag">
          <span class="tip-tag">{{ tip.tag }}</span>
          <span class="tip-text">{{ tip.text }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped lang="sass">
.teacher-demo
  border: 1px solid #eceff1
  border-radius: 12px
  padding: 14px 16px 16px
  background: #fafafa

.demo-head
  display: flex
  align-items: center
  justify-content: space-between
  margin-bottom: 10px
  h2
    margin: 0
    font-size: 16px
    font-weight: 600

.demo-body
  display: flex
  gap: 20px
  align-items: flex-start
  flex-wrap: wrap

.clip-row
  display: flex
  gap: 12px

.clip
  margin: 0
  position: relative
  border-radius: 10px
  overflow: hidden
  background: #ffffff

.clip-video
  display: block
  width: 200px
  height: 200px
  object-fit: contain
  background: #ffffff

.clip-label
  position: absolute
  left: 8px
  top: 8px
  padding: 1px 8px
  font-size: 12px
  color: #ffffff
  background: rgba(38, 50, 56, 0.62)
  border-radius: 999px

.tip-list
  list-style: none
  margin: 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 8px
  min-width: 240px
  flex: 1

  li
    display: flex
    align-items: baseline
    gap: 10px

.tip-tag
  flex: none
  width: 22px
  text-align: center
  font-size: 12px
  font-weight: 600
  color: #00695c
  background: #e0f2f1
  border-radius: 6px
  padding: 1px 0

.tip-text
  font-size: 13px
  color: #455a64
  line-height: 1.5
</style>
