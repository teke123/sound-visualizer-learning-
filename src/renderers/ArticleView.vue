<script setup lang="ts">
/**
 * ArticleView：文章正文渲染器（P04 与预览共用，FD-12）。
 * Markdown 正文 + 受控指令（practice/audio/image/levels/pro）；
 * 关卡链接只渲染当前已发布关（由 publishedIds 判定）；
 * 播放与跳转为回调（renderers 不调 api、不读 store）。
 */
import { computed, ref, watch } from 'vue'
import type { ArticleDetail } from '@/api'
import { renderArticleMarkdown } from './markdown'

const props = defineProps<{
  article: ArticleDetail
  /** mediaId → URL（公开或预览） */
  mediaResolver: (mediaId: string) => string
  /** 当前已发布关 ID 集合；未发布关卡链接显示不可用 */
  publishedLevelIds: ReadonlySet<string>
  interactive?: boolean
}>()

const emit = defineEmits<{
  (e: 'play-media', mediaId: string): void
  (e: 'open-level', levelId: string): void
}>()

const html = ref('')
const rendering = ref(false)

async function render() {
  rendering.value = true
  try {
    html.value = await renderArticleMarkdown(props.article.content, {
      mediaResolver: props.mediaResolver,
    })
  } finally {
    rendering.value = false
  }
}

watch(
  () => [props.article.slug, props.article.contentVersion] as const,
  () => {
    void render()
  },
  { immediate: true },
)

function onContentClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  const audioBtn = target.closest<HTMLElement>('.md-audio-btn')
  if (audioBtn?.dataset.mediaId) {
    if (props.interactive !== false) emit('play-media', audioBtn.dataset.mediaId)
    return
  }
  const levelChip = target.closest<HTMLElement>('.md-level-chip')
  if (levelChip?.dataset.levelId) {
    const levelId = levelChip.dataset.levelId
    if (props.publishedLevelIds.has(levelId)) {
      if (props.interactive !== false) emit('open-level', levelId)
      levelChip.classList.remove('unavailable')
    } else {
      levelChip.classList.add('unavailable')
    }
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' && event.key !== ' ') return
  const target = event.target as HTMLElement
  const chip = target.closest<HTMLElement>('.md-level-chip')
  if (chip) {
    event.preventDefault()
    onContentClick(event as unknown as MouseEvent)
  }
}

const references = computed(() => props.article.references ?? [])
const practiceItems = computed(() => props.article.practice ?? [])
const relatedLevels = computed(() => props.article.levelIds ?? [])
</script>

<template>
  <article class="article-view">
    <header class="article-header">
      <h1>{{ article.title }}</h1>
      <p v-if="article.excerpt" class="article-excerpt">{{ article.excerpt }}</p>
    </header>

    <div
      class="article-body"
      v-html="html"
      @click="onContentClick"
      @keydown="onKeydown"
    ></div>
    <p v-if="rendering" class="article-rendering">正文加载中…</p>

    <section v-if="practiceItems.length > 0" class="article-section">
      <h2>短练习</h2>
      <ol class="article-practice">
        <li v-for="(item, index) in practiceItems" :key="index">{{ item }}</li>
      </ol>
    </section>

    <section v-if="relatedLevels.length > 0" class="article-section">
      <h2>相关关卡</h2>
      <div class="article-levels">
        <template v-for="levelId in relatedLevels" :key="levelId">
          <button
            v-if="publishedLevelIds.has(levelId) && interactive !== false"
            type="button"
            class="level-chip"
            @click="emit('open-level', levelId)"
          >
            {{ levelId }}
          </button>
          <span v-else class="level-chip unavailable">{{ levelId }}（暂不可进入）</span>
        </template>
      </div>
    </section>

    <section v-if="references.length > 0" class="article-section">
      <h2>参考资料</h2>
      <ul class="article-references">
        <li v-for="reference in references" :key="reference.title">
          <strong>{{ reference.title }}</strong>
          <span class="reference-meta">来源：{{ reference.source }} · 许可：{{ reference.license }}</span>
          <span class="reference-scope">适用边界：{{ reference.scope }}</span>
        </li>
      </ul>
    </section>
  </article>
</template>

<style scoped lang="sass">
.article-view
  max-width: 760px
  margin: 0 auto

.article-header h1
  font-size: 26px
  margin: 0 0 8px

.article-excerpt
  color: #607d8b
  margin: 0 0 16px

.article-body
  font-size: 16px
  line-height: 1.8
  color: #263238
  overflow-wrap: break-word

  :deep(h2)
    font-size: 20px
    margin: 24px 0 8px

  :deep(p)
    margin: 10px 0

  :deep(img)
    max-width: 100%
    border-radius: 8px

  :deep(.md-audio)
    display: flex
    align-items: center
    gap: 10px
    padding: 10px 12px
    background: #e0f7fa
    border-radius: 8px
    margin: 12px 0

  :deep(.md-audio-btn)
    min-height: 36px
    padding: 4px 14px
    border: 1px solid #00acc1
    border-radius: 999px
    background: #fff
    color: #00838f
    cursor: pointer
    font-size: 14px

  :deep(.md-audio-text)
    color: #00695f
    font-size: 14px

  :deep(.md-image)
    margin: 12px 0
    figcaption
      font-size: 13px
      color: #607d8b
      margin-top: 4px

  :deep(.md-level-chip)
    display: inline-block
    margin: 0 8px 8px 0
    padding: 4px 12px
    border: 1px solid #80cbc4
    border-radius: 999px
    color: #00695c
    cursor: pointer
    font-size: 14px
    background: #fff
    &.unavailable
      border-color: #cfd8dc
      color: #90a4ae
      cursor: default

  :deep(.md-practice), :deep(.md-pro)
    border: 1px solid #cfd8dc
    border-radius: 8px
    padding: 10px 14px
    margin: 12px 0
    summary
      cursor: pointer
      font-weight: 600
      color: #37474f

.article-rendering
  color: #90a4ae
  font-size: 13px

.article-section
  margin-top: 28px
  h2
    font-size: 18px
    margin: 0 0 10px

.article-practice
  padding-left: 20px
  line-height: 1.9

.article-levels
  display: flex
  flex-wrap: wrap

.level-chip
  margin: 0 8px 8px 0
  padding: 6px 14px
  border: 1px solid #80cbc4
  border-radius: 999px
  background: #fff
  color: #00695c
  cursor: pointer
  font-size: 14px
  min-height: 36px
  &.unavailable
    border-color: #cfd8dc
    color: #90a4ae
    cursor: default

.article-references
  list-style: none
  padding: 0
  li
    padding: 8px 0
    border-bottom: 1px dashed #eceff1
    display: flex
    flex-direction: column
    gap: 2px

.reference-meta, .reference-scope
  font-size: 13px
  color: #78909c
</style>
