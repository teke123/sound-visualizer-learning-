<script setup lang="ts">
/**
 * ArticulationFigure：构形多视图渲染器（FR-603 / FD-07）。
 * 内容媒体（图/动画/视频）、声道剖面、3D 三视图切换；缺席视图不显示切换项。
 * 3D 视图由 Model3DView 以 three.js 懒加载渲染；关卡无 model3dMediaId 时按缺席处理。
 * 纯展示：媒体地址由 props.mediaResolver 提供（公开 / 预览由页面决定）。
 */
import { computed, ref, watch } from 'vue'
import type { Articulation } from '@/api'
import Model3DView from './Model3DView.vue'
import SagittalView from './SagittalView.vue'

const props = defineProps<{
  articulation: Articulation | null | undefined
  /** mediaId → URL（公开 /api/media 或预览 /api/preview/media） */
  mediaResolver: (mediaId: string) => string
}>()

type ViewKind = 'media' | 'sagittal' | 'model3d'

const hasMedia = computed(() => (props.articulation?.media ?? []).length > 0)
const hasSagittal = computed(
  () => (props.articulation?.sagittal?.keyframes.length ?? 0) > 0,
)
const hasModel3d = computed(() => Boolean(props.articulation?.model3dMediaId))
const model3dSrc = computed(() => {
  const mediaId = props.articulation?.model3dMediaId
  return mediaId ? props.mediaResolver(mediaId) : ''
})

const availableViews = computed<Array<{ key: ViewKind; label: string }>>(() => {
  const views: Array<{ key: ViewKind; label: string }> = []
  if (hasMedia.value) views.push({ key: 'media', label: '内容媒体' })
  if (hasSagittal.value) views.push({ key: 'sagittal', label: '声道剖面' })
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

    <div v-if="availableViews.length === 0" class="figure-empty">本关暂无构形内容</div>

    <!-- 内容媒体视图：图 / 动画 / 视频 -->
    <div v-if="activeView === 'media' && hasMedia" class="media-view">
      <figure v-for="item in articulation?.media ?? []" :key="item.mediaId" class="media-item">
        <video v-if="item.kind === 'video'" controls :src="mediaResolver(item.mediaId)" preload="none"></video>
        <img v-else :src="mediaResolver(item.mediaId)" :alt="item.altText" loading="lazy" />
        <figcaption>{{ item.altText }}</figcaption>
      </figure>
    </div>

    <!-- 声道剖面视图：关键帧参数驱动 -->
    <div v-if="activeView === 'sagittal' && hasSagittal" class="sagittal-wrap">
      <SagittalView
        :keyframes="articulation?.sagittal?.keyframes ?? []"
        :description="articulation?.description ?? ''"
      />
    </div>

    <!-- 3D 视图：three.js 懒加载渲染 model3dMediaId（FD-07） -->
    <div v-if="activeView === 'model3d' && hasModel3d" class="model3d-wrap">
      <Model3DView :src="model3dSrc" />
    </div>
  </section>
</template>

<style scoped lang="sass">
.articulation-figure
  background: #fff
  border: 1px solid #eceff1
  border-radius: 12px
  padding: 16px

.view-tabs
  display: flex
  gap: 8px
  margin-bottom: 12px

.view-tab
  min-height: 36px
  padding: 4px 16px
  border-radius: 999px
  border: 1px solid #cfd8dc
  background: #fff
  cursor: pointer
  font-size: 14px
  &.active
    background: #e0f2f1
    border-color: #00897b
    color: #00695c
    font-weight: 600

.figure-empty
  color: #90a4ae
  padding: 24px 0
  text-align: center

.media-view
  display: grid
  gap: 16px
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr))

.media-item
  margin: 0
  img, video
    width: 100%
    border-radius: 8px
    background: #f5f5f5
  figcaption
    font-size: 13px
    color: #607d8b
    margin-top: 6px

.sagittal-wrap
  display: flex
  justify-content: center

.model3d-wrap
  display: flex
  justify-content: center
</style>
