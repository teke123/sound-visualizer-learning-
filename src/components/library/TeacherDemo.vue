/**
 * 发音示范：按音素切换的外部口型动画（正视 / 侧视）。
 *
 * 素材仍是静态目录（public/media/teacher/…），但地址统一从 demoClips.ts 取，
 * 将来改走后端媒体只改那一处的两个函数。
 *
 * 设计要点：
 * - 只挂当前选中音素的视频，切换即销毁，避免一次请求几十个文件；
 * - preload="metadata"，只取首帧，不预下载整段；
 * - 某条素材还没上传时显示「待上传」占位，不报错、不影响其它音；
 * - 尊重 prefers-reduced-motion：减弱动效时默认停在首帧。
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { QBtn } from 'quasar'
import { usePreferredReducedMotion } from '@vueuse/core'
import {
  CLIP_BY_KEY,
  DEMO_CLIPS,
  TIPS,
  teacherVideoUrl,
  viewsOf,
  type DemoView,
} from './demoClips'

const rootEl = ref<HTMLElement | null>(null)
const group = ref<'vowel' | 'initial'>('vowel')
const selected = ref('a')
const playing = ref(true)
/** 加载失败的视频地址（素材还没上传时保持占位） */
const failed = ref<Set<string>>(new Set())
const reducedMotion = usePreferredReducedMotion()

const clip = computed(() => CLIP_BY_KEY.get(selected.value))
const views = computed<DemoView[]>(() => (clip.value ? viewsOf(clip.value) : ['front']))
const chips = computed(() => DEMO_CLIPS.filter((c) => c.group === group.value))
const tip = computed(() => TIPS[selected.value] ?? '')

function urlOf(view: DemoView): string {
  return teacherVideoUrl(selected.value, view)
}

function isFailed(view: DemoView): boolean {
  return failed.value.has(urlOf(view))
}

function markFailed(view: DemoView) {
  const next = new Set(failed.value)
  next.add(urlOf(view))
  failed.value = next
}

function videos(): HTMLVideoElement[] {
  return Array.from(rootEl.value?.querySelectorAll('video') ?? [])
}

function apply() {
  for (const v of videos()) {
    v.muted = true
    if (playing.value) {
      void v.play().catch(() => {
        /* 浏览器拒绝自动播放时停在首帧 */
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

function pick(key: string) {
  selected.value = key
}

watch(group, (g) => {
  const first = DEMO_CLIPS.find((c) => c.group === g)
  if (first) selected.value = first.key
})

watch(selected, async () => {
  await nextTick()
  apply()
})

onBeforeUnmount(() => {
  for (const v of videos()) v.pause()
})

// 初始化：减弱动效时不自动播放
if (reducedMotion.value === 'reduce') playing.value = false
</script>

<template>
  <section class="teacher-demo" ref="rootEl" :aria-label="`${selected} 的发音示范`">
    <div class="demo-head">
      <h2>
        发音示范
        <span v-if="clip" class="demo-key">{{ clip.key }}</span>
        <span v-if="clip" class="demo-ipa">/{{ clip.ipa }}/</span>
      </h2>
      <QBtn
        flat
        dense
        no-caps
        color="teal-7"
        :label="playing ? '暂停' : '播放'"
        @click="toggle"
      />
    </div>

    <div class="demo-picker">
      <div class="group-tabs">
        <QBtn
          v-for="g in [{ key: 'vowel', label: '单韵母' }, { key: 'initial', label: '声母' }]"
          :key="g.key"
          dense
          no-caps
          :flat="group !== g.key"
          :outline="group !== g.key"
          :color="group === g.key ? 'teal-7' : 'blue-grey-5'"
          :text-color="group === g.key ? 'white' : 'blue-grey-8'"
          :label="g.label"
          @click="group = g.key as 'vowel' | 'initial'"
        />
      </div>
      <div class="chip-row">
        <button
          v-for="c in chips"
          :key="c.key"
          type="button"
          class="chip"
          :class="{ 'chip-active': c.key === selected }"
          :aria-pressed="c.key === selected"
          @click="pick(c.key)"
        >
          {{ c.key }}
        </button>
      </div>
    </div>

    <div class="demo-body">
      <div class="clip-row">
        <figure v-for="view in views" :key="`${selected}-${view}`" class="clip">
          <video
            v-if="!isFailed(view)"
            :key="`${selected}-${view}`"
            :src="urlOf(view)"
            :aria-label="`${selected} ${view === 'front' ? '正视' : '侧视'}示范`"
            class="clip-video"
            loop
            muted
            playsinline
            preload="metadata"
            @error="markFailed(view)"
          />
          <div v-else class="clip-missing">
            <span>待上传</span>
            <code>{{ view === 'front' ? 'front' : 'side' }}</code>
          </div>
          <figcaption class="clip-label">{{ view === 'front' ? '正视' : '侧视' }}</figcaption>
        </figure>
      </div>

      <div class="tip-area">
        <p v-if="tip" class="tip-text">{{ tip }}</p>
        <p class="tip-note">
          素材按 <code>public/media/teacher/{{ selected }}/{{ selected }}_front.mp4</code> 存放；
          缺失的音素显示「待上传」。
        </p>
      </div>
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
    display: flex
    align-items: baseline
    gap: 8px

.demo-key
  font-size: 20px
  color: #00695c

.demo-ipa
  font-size: 13px
  font-weight: 400
  color: #78909c

.demo-picker
  display: flex
  flex-direction: column
  gap: 8px
  margin-bottom: 12px

.group-tabs
  display: flex
  gap: 6px

.chip-row
  display: flex
  flex-wrap: wrap
  gap: 6px

.chip
  min-width: 38px
  height: 30px
  padding: 0 10px
  font-size: 13px
  color: #455a64
  background: #fff
  border: 1px solid #cfd8dc
  border-radius: 8px
  cursor: pointer
  &:hover
    border-color: #80cbc4
  &.chip-active
    color: #fff
    background: #00897b
    border-color: #00897b

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
  background: #fff
  border: 1px solid #eceff1

.clip-video
  display: block
  width: 200px
  height: 200px
  object-fit: contain
  background: #fff

.clip-missing
  width: 200px
  height: 200px
  display: flex
  flex-direction: column
  align-items: center
  justify-content: center
  gap: 4px
  color: #90a4ae
  font-size: 13px
  background: repeating-linear-gradient(45deg, #fafafa, #fafafa 8px, #f3f5f6 8px, #f3f5f6 16px)
  code
    font-size: 11px
    color: #b0bec5

.clip-label
  position: absolute
  left: 8px
  top: 8px
  padding: 1px 8px
  font-size: 12px
  color: #fff
  background: rgba(38, 50, 56, 0.62)
  border-radius: 999px

.tip-area
  flex: 1
  min-width: 240px

.tip-text
  margin: 0 0 8px
  font-size: 13px
  color: #37474f
  line-height: 1.6

.tip-note
  margin: 0
  font-size: 12px
  color: #b0bec5
  line-height: 1.5
  code
    font-size: 11px
</style>
