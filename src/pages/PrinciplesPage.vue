<script setup lang="ts">
/** P04 发音原理目录（FR-501）：气 → 声 → 口型三分类；提供进入 P03 的入口 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { contentApi, type ArticleCategory, type ArticleSummary } from '@/api'
import PageState from '@/components/PageState.vue'

const route = useRoute()
const router = useRouter()

const categories = ref<ArticleCategory[]>([])
const articles = ref<ArticleSummary[]>([])
const loading = ref(true)
const error = ref<unknown>(null)

const activeCategory = computed(() => {
  const raw = route.query.category
  return typeof raw === 'string' && raw !== '' ? raw : ''
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const [catRes, artRes] = await Promise.all([
      contentApi.articleCategories(),
      contentApi.articles(activeCategory.value || undefined),
    ])
    categories.value = catRes.data.categories
    articles.value = artRes.data.articles
  } catch (err) {
    error.value = err
  } finally {
    loading.value = false
  }
}

watch(activeCategory, () => void load(), { immediate: true })
onMounted(() => void load())

function switchCategory(name: string) {
  void router.push({ path: '/principles', query: name ? { category: name } : {} })
}
</script>

<template>
  <div class="principles-page">
    <header class="pr-head">
      <h1>看懂发音</h1>
      <p>先懂原理，再进关卡：气从哪里来 → 声音怎么响 → 嘴和舌头怎么摆。</p>
    </header>

    <PageState v-if="loading" state="loading" />
    <PageState v-else-if="error" state="error" :error="error" @retry="load" />
    <template v-else>
      <nav class="category-tabs" aria-label="文章分类">
        <button
          type="button"
          :class="['cat-tab', { active: activeCategory === '' }]"
          @click="switchCategory('')"
        >
          全部
        </button>
        <button
          v-for="category in categories"
          :key="category.id"
          type="button"
          :class="['cat-tab', { active: activeCategory === category.name }]"
          @click="switchCategory(category.name)"
        >
          {{ category.name }}
        </button>
      </nav>

      <p v-if="articles.length === 0" class="no-articles">这一类暂时没有已发布的文章。</p>
      <ul v-else class="article-list">
        <li v-for="article in articles" :key="article.slug" class="article-item">
          <RouterLink :to="`/principles/${article.slug}`" class="article-link">
            <strong>{{ article.title }}</strong>
            <span v-if="article.summary" class="article-excerpt">{{ article.summary }}</span>
          </RouterLink>
        </li>
      </ul>
    </template>

    <footer class="pr-foot">
      <RouterLink to="/map" class="to-map">已经在地图上亮起的关卡，可以直接去学 →</RouterLink>
    </footer>
  </div>
</template>

<style scoped lang="sass">
.principles-page
  max-width: 720px
  margin: 0 auto

.pr-head
  h1
    margin: 0 0 4px
    font-size: 24px
  p
    margin: 0 0 16px
    color: #78909c
    font-size: 14px

.category-tabs
  display: flex
  gap: 8px
  flex-wrap: wrap
  margin-bottom: 16px

.cat-tab
  min-height: 44px
  padding: 4px 16px
  border-radius: 999px
  border: 1px solid #cfd8dc
  background: #fff
  cursor: pointer
  &.active
    border-color: #00897b
    background: #e0f2f1
    color: #00695c
    font-weight: 700

.no-articles
  color: #90a4ae

.article-list
  list-style: none
  margin: 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 10px

.article-item
  border: 1px solid #eceff1
  border-radius: 10px
  background: #fff

.article-link
  display: flex
  flex-direction: column
  gap: 4px
  padding: 14px 16px
  text-decoration: none
  color: #263238
  strong
    font-size: 16px

.article-excerpt
  font-size: 13px
  color: #90a4ae

.pr-foot
  margin-top: 28px
  text-align: center

.to-map
  color: #00897b
  text-decoration: none
  font-size: 14px
</style>
