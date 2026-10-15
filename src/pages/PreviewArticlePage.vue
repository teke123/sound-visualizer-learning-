<script setup lang="ts">
/** /preview/articles/:slug?token=（FD-12 / §6.8）：文章草稿预览（只读） */
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { usePreview } from '@/features/preview'
import { useLevelsStore } from '@/stores/levels'
import ArticleView from '@/renderers/ArticleView.vue'
import PageState from '@/components/PageState.vue'

const route = useRoute()
const preview = usePreview()
const levelsStore = useLevelsStore()

const slug = computed(() => String(route.params.slug ?? ''))

onMounted(() => {
  void preview.loadArticle(slug.value)
  if (!levelsStore.loaded) void levelsStore.refresh()
})

const publishedLevelIds = computed(() => new Set(levelsStore.published.map((level) => level.id)))
</script>

<template>
  <div class="preview-page">
    <header class="preview-banner" role="note">
      <span>👁 文章草稿预览（不计入大众端页面）</span>
      <span v-if="preview.article.value && preview.article.value.contentVersion">
        内容版本 v{{ preview.article.value.contentVersion }}
      </span>
    </header>

    <PageState v-if="preview.loading.value" state="loading" />
    <div v-else-if="preview.invalid.value" class="preview-invalid">
      <p>预览已失效，请回后台重新打开。</p>
      <p class="invalid-sub">预览令牌默认 15 分钟有效，且绑定管理员会话与草稿修订。</p>
    </div>
    <PageState v-else-if="!preview.article.value" state="not-visible" text="草稿内容读取失败" />
    <ArticleView
      v-else
      :article="preview.article.value"
      :media-resolver="preview.previewMediaUrl"
      :published-level-ids="publishedLevelIds"
      :interactive="false"
    />
  </div>
</template>

<style scoped lang="sass">
.preview-page
  max-width: 860px
  margin: 0 auto
  padding: 12px 16px 40px

.preview-banner
  display: flex
  justify-content: space-between
  gap: 10px
  background: #ede7f6
  border: 1px solid #b39ddb
  color: #4527a0
  border-radius: 8px
  padding: 8px 14px
  font-size: 13px
  margin-bottom: 16px

.preview-invalid
  text-align: center
  padding: 60px 0
  p
    margin: 4px 0
  .invalid-sub
    color: #90a4ae
    font-size: 13px
</style>
