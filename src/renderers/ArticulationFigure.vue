<script setup lang="ts">
/**
 * ArticulationFigure：构形多视图渲染器（FR-603 / FD-07）。
 * 内容媒体（图/动画/视频）与 3D 模型两视图切换；缺席视图不显示切换项。
 * 交互动画经 media[].component 声明，由内置组件注册表渲染（懒加载分包），
 * 未知 component 键退回静态图/视频直出。3D 视图由 Model3DView 以 three.js 懒加载渲染；
 * 关卡无 model3dMediaId 时按缺席处理。
 * 纯展示：媒体地址由 props.mediaResolver 提供（公开 /api/media 或预览 /api/preview/media）。
 */
import { computed, defineAsyncComponent, ref, watch, type Component } from 'vue'
import type { Articulation } from '@/api'
import AppIcon from '@/components/ui/AppIcon.vue'
import Model3DView from './Model3DView.vue'

const props = defineProps<{
  articulation: Articulation | null | undefined
  /** mediaId → URL（公开 /api/media 或预览 /api/preview/media） */
  mediaResolver: (mediaId: string) => string
}>()

/** 交互动画内置组件注册表：component 键 → 懒加载组件（按需代码分割） */
const INTERACTIVE_COMPONENTS: Record<string, Component> = {
  'ma-sagittal': defineAsyncComponent(() => import('./MaSagittalAnimation.vue')),
}

function interactiveComponent(component: string | null | undefined): Component | null {
  return component ? INTERACTIVE_COMPONENTS[component] ?? null : null
}

type ViewKind = 'media' | 'model3d'

const hasMedia = computed(() => (props.articulation?.media ?? []).length > 0)
const hasModel3d = computed(() => Boolean(props.articulation?.model3dMediaId))
const model3dSrc = computed(() => {
  const mediaId = props.articulation?.model3dMediaId
  return mediaId ? props.mediaResolver(mediaId) : ''
})

const availableViews = computed<Array<{ key: ViewKind; label: string }>>(() => {
  const views: Array<{ key: ViewKind; label: string }> = []
  if (hasMedia.value) views.push({ key: 'media', label: '内容媒体' })
  if (hasModel3d.value) views.push({ key: 'model3d', label: '三维模型' })
  return views
})

const activeView = ref<ViewKind>('media')

watch(
  availableViews,
  (views) => {
    if (!views.some((view) => view.key === activeView.value)) {
      activeView.value = views[0]?.key ?? 'media'
    }
  },
  { immediate: true },
)
</script>

<template>
  <section class="articulation-figure" aria-label="构形">
    <h3 class="fig-title"><AppIcon name="mouth" size="sm" />看见口型</h3>
    <div class="view-tabs" v-if="availableViews.length > 1" role="tablist">
      <button
        v-for="view in availableViews"
        :key="view.key"
        type="button"
        role="tab"
        :aria-selected="activeView === view.key"
        :class="['view-tab', { active: activeView === view.key }]"
        @click="activeView = view.key"
      >
        {{ view.label }}
      </button>
    </div>

    <div v-if="availableViews.length === 0" class="figure-empty">
      <svg width="176" height="108" viewBox="0 0 176 108" aria-hidden="true">
        <ellipse cx="88" cy="54" rx="72" ry="46" fill="#fdf6ea" />
        <ellipse cx="88" cy="64" rx="38" ry="19" fill="#faecd8" stroke="#e3c2a0" stroke-width="2.5" />
        <path d="M61 64c8-12 46-12 54 0-8 12-46 12-54 0Z" fill="#e9b49e" />
        <path d="M61 64h54" stroke="#c08068" stroke-width="1.6" />
      </svg>
      <p>本关暂无构形素材。</p>
    </div>

    <!-- 内容媒体视图：交互动画组件 / 图 / 动画 / 视频 -->
    <div v-if="activeView === 'media' && hasMedia" class="media-view">
      <figure v-for="item in articulation?.media ?? []" :key="item.mediaId" class="media-item" :class="{ interactive: interactiveComponent(item.component) }">
        <component
          :is="interactiveComponent(item.component)"
          v-if="interactiveComponent(item.component)"
          :label="item.altText"
        />
        <video v-else-if="item.kind === 'video'" controls :src="mediaResolver(item.mediaId)" preload="none"></video>
        <img v-else :src="mediaResolver(item.mediaId)" :alt="item.altText" loading="lazy" />
        <figcaption v-if="!interactiveComponent(item.component)">{{ item.altText }}</figcaption>
      </figure>
    </div>

    <!-- 3D 视图：three.js 懒加载渲染 model3dMediaId（FD-07） -->
    <div v-if="activeView === 'model3d' && hasModel3d" class="model3d-wrap">
      <Model3DView :src="model3dSrc" />
    </div>
  </section>
</template>

<style scoped lang="sass">
.articulation-figure
  background: var(--vs-card)
  border: 1px solid var(--vs-line)
  border-radius: 8px
  padding: 24px
  box-shadow: 0 1px 2px rgba(var(--vs-shadow-rgb), 0.05), 0 1px 3px rgba(var(--vs-shadow-rgb), 0.04)

.fig-title
  display: flex
  align-items: center
  gap: 8px
  margin: 0 0 12px
  font-size: 20px
  font-weight: 900
  letter-spacing: -0.3px

.fig-title .ico,
.fig-title .vs-ico
  color: var(--vs-brand)

.view-tabs
  display: flex
  gap: 8px
  margin-bottom: 12px

.view-tab
  min-height: 36px
  padding: 4px 16px
  border-radius: 999px
  border: 1px solid var(--vs-line2)
  background: var(--vs-card)
  cursor: pointer
  font-family: inherit
  font-size: 14px
  color: var(--vs-ink2)
  transition: background 0.16s ease, border-color 0.16s ease
  &.active
    background: var(--vs-soft)
    border-color: var(--vs-coffee)
    color: var(--vs-coffee)
    font-weight: 600
  &:hover
    border-color: var(--vs-line-hover)

.figure-empty
  color: var(--vs-sub)
  padding: 16px 0
  text-align: center
  display: flex
  flex-direction: column
  align-items: center
  gap: 8px
  svg
    max-width: 100%
    height: auto
  p
    margin: 0
    max-width: 100%
    font-size: 12.5px
    line-height: 1.7
    overflow-wrap: anywhere

.media-view
  display: grid
  gap: 16px
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr))

.media-item
  margin: 0
  img, video
    width: 100%
    border-radius: 8px
    background: var(--vs-soft-2)
  figcaption
    font-size: 13px
    color: var(--vs-sub)
    margin-top: 6px
  &.interactive
    grid-column: 1 / -1

.model3d-wrap
  display: flex
  justify-content: center
</style>
