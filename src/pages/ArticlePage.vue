<script setup lang="ts">
/** P04 文章页（FR-501–506）：ArticleView + 进入已开放关卡；404 落统一不可见状态 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, contentApi, mediaUrl, type ArticleDetail } from '@/api'
import { usePlayerStore } from '@/stores/player'
import { useLevelsStore } from '@/stores/levels'
import ArticleView from '@/renderers/ArticleView.vue'
import PageState from '@/components/PageState.vue'

const route = useRoute()
const router = useRouter()
const player = usePlayerStore()
const levelsStore = useLevelsStore()

const slug = computed(() => String(route.params.slug ?? ''))
const article = ref<ArticleDetail | null>(null)
const loading = ref(true)
const error = ref<unknown>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await contentApi.article(slug.value)
    article.value = res.data
  } catch (err) {
    article.value = null
    error.value = err
    // 内容 404：统一不可见状态
    if (err instanceof ApiError && (err.status === 404 || err.code === 'NOT_FOUND')) {
      // 保持 not-visible 展示
    }
  } finally {
    loading.value = false
  }
}

watch(slug, () => void load(), { immediate: true })

const publishedLevelIds = computed(() => new Set(levelsStore.published.map((level) => level.id)))

function playMedia(mediaId: string) {
  void player.play({ key: `article:${mediaId}`, url: mediaUrl(mediaId), label: '文章示范' })
}

function openLevel(levelId: string) {
  void router.push(`/learn/${levelId}`)
}
</script>

<template>
  <div class="article-page">
    <nav class="back-nav">
      <RouterLink to="/principles">← 全部文章</RouterLink>
    </nav>

    <PageState v-if="loading" state="loading" />
    <PageState v-else-if="!article" state="not-visible" text="文章不存在或暂不可见" />
    <template v-else>
      <ArticleView
        :article="article"
        :media-resolver="mediaUrl"
        :published-level-ids="publishedLevelIds"
        @play-media="playMedia"
        @open-level="openLevel"
      />
    </template>
  </div>
</template>

<style scoped lang="sass">
.article-page
  max-width: 760px
  margin: 0 auto

.back-nav
  margin-bottom: 12px
  a
    color: #00897b
    text-decoration: none
    font-size: 14px
</style>
