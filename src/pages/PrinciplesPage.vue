<script setup lang="ts">
/**
 * P04 专业资料（FR-501）：气 → 声 → 口型三段固定原理（不依赖后端内容，任何环境都有内容），
 * 下方挂 CMS 已发布文章列表（有就按分类筛，没有就不占位）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { contentApi, type ArticleCategory, type ArticleSummary } from '@/api'
import PageState from '@/components/PageState.vue'
import PageHead from '@/components/ui/PageHead.vue'
import AppIcon from '@/components/ui/AppIcon.vue'

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

/** 发音三要素：气 → 声 → 口型（稳定教学口径，与关卡页的「发音要领」互补） */
const steps = [
  {
    title: '气',
    body: '气从肺里出来，经过喉咙，再从嘴巴或鼻子出去。说话时气要匀，不要憋着用力喊。',
    drill: '手放在嘴巴前面，轻轻说「啊」，能感到一点小风。',
  },
  {
    title: '声',
    body: '气经过喉咙时，声带轻轻合起来振动，才发出声音。嗓子放松，声音就自然。',
    drill: '手放在喉咙上，说「啊」，能感到轻轻麻麻的振动。',
  },
  {
    title: '口型',
    body: '嘴巴的开合、圆扁，舌头的上下前后，决定了气从哪里出去，也就决定了是哪个音。',
    drill: '对着镜子说三个音：a 张嘴、i 咧嘴、u 嘟嘴，看嘴巴的形状。',
  },
]
</script>

<template>
  <div class="principles-page">
    <PageHead title="专业资料" icon="doc" />

    <section class="steps" aria-label="发音三步">
      <article v-for="(step, index) in steps" :key="step.title" class="step-card">
        <header class="step-head">
          <span class="step-no">{{ index + 1 }}</span>
          <h2>{{ step.title }}</h2>
        </header>
        <p class="step-body">{{ step.body }}</p>
        <p class="step-drill"><AppIcon name="run" size="sm" />小练习：{{ step.drill }}</p>
      </article>
    </section>

    <section class="articles" aria-label="发音文章">
      <h2 class="art-title"><span class="vs-bar" />更多讲解</h2>

      <PageState v-if="loading" state="loading" />
      <PageState v-else-if="error" state="error" :error="error" @retry="load" />
      <template v-else-if="articles.length > 0 || categories.length > 0">
        <nav v-if="categories.length > 0" class="category-tabs" aria-label="文章分类">
          <button
            type="button"
            class="vs-chip"
            :aria-pressed="activeCategory === ''"
            @click="switchCategory('')"
          >
            全部
          </button>
          <button
            v-for="category in categories"
            :key="category.id"
            type="button"
            class="vs-chip"
            :aria-pressed="activeCategory === category.name"
            @click="switchCategory(category.name)"
          >
            {{ category.name }}
          </button>
        </nav>

        <p v-if="articles.length === 0" class="vs-note">这一类暂时没有已开放的文章。</p>
        <ul v-else class="article-list">
          <li v-for="article in articles" :key="article.slug">
            <RouterLink :to="`/principles/${article.slug}`" class="article-link">
              <span class="article-mark"><AppIcon name="doc" size="sm" /></span>
              <span class="article-tx">
                <strong>{{ article.title }}</strong>
                <span v-if="article.summary" class="article-excerpt">{{ article.summary }}</span>
              </span>
              <AppIcon name="arrow" size="sm" class="article-chev" />
            </RouterLink>
          </li>
        </ul>
      </template>
      <p v-else class="vs-note">文章正在整理中；上面这三步已经能帮你把发音想明白。</p>
    </section>
  </div>
</template>

<style scoped lang="sass">
.principles-page
  display: flex
  flex-direction: column
  gap: 20px
  max-width: 860px
  margin: 0 auto

.steps
  display: grid
  grid-template-columns: repeat(3, 1fr)
  gap: 16px

.step-card
  background: var(--vs-card)
  border: 1px solid var(--vs-line)
  border-radius: 8px
  padding: 24px 20px
  box-shadow: var(--vs-sh-1)
  display: flex
  flex-direction: column
  gap: 10px

.step-head
  display: flex
  align-items: center
  gap: 8px
  h2
    margin: 0
    font-size: 20px
    font-weight: 900
    letter-spacing: -0.3px

.step-no
  width: 24px
  height: 24px
  border-radius: 8px
  background: var(--vs-soft)
  color: var(--vs-ink2)
  display: flex
  align-items: center
  justify-content: center
  font-size: 12px
  font-weight: 700
  flex: none

.step-body
  margin: 0
  font-size: 13.5px
  color: var(--vs-sub)
  line-height: 1.8

.step-drill
  margin: auto 0 0
  background: var(--vs-brand-soft)
  border-radius: 8px
  padding: 11px 13px
  font-size: 13px
  color: var(--vs-brand-d)
  line-height: 1.7
  display: flex
  align-items: flex-start
  gap: 6px

.step-drill .vs-ico
  margin-top: 2px

.articles
  display: flex
  flex-direction: column
  gap: 12px

.art-title
  font-size: 20px
  font-weight: 900
  letter-spacing: -0.3px
  display: flex
  align-items: center
  gap: 10px
  margin: 8px 0 0

.art-title .vs-bar
  display: block
  flex: none
  width: 4px
  height: 20px
  border-radius: 2px
  background: linear-gradient(180deg, var(--vs-sand), var(--vs-brand))

.category-tabs
  display: flex
  gap: 8px
  flex-wrap: wrap

.article-list
  list-style: none
  margin: 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 12px

.article-link
  display: flex
  align-items: center
  gap: 14px
  padding: 16px 20px
  border: 1px solid var(--vs-line)
  border-radius: 8px
  background: var(--vs-card)
  box-shadow: var(--vs-sh-1)
  text-decoration: none
  color: var(--vs-ink)
  transition: border-color 0.2s var(--vs-ease), box-shadow 0.2s var(--vs-ease)

.article-link:hover
  border-color: var(--vs-line-hover)
  box-shadow: var(--vs-sh-2)

.article-mark
  width: 32px
  height: 32px
  flex: none
  border-radius: 8px
  display: flex
  align-items: center
  justify-content: center
  background: var(--vs-soft)
  color: var(--vs-brand)

.article-tx
  display: flex
  flex-direction: column
  gap: 2px
  flex: 1
  min-width: 0
  strong
    font-size: 15px

.article-excerpt
  font-size: 12.5px
  color: var(--vs-sub)
  line-height: 1.6

.article-chev
  color: var(--vs-mute)
  transition: transform 0.2s var(--vs-ease), color 0.2s var(--vs-ease)

.article-link:hover .article-chev
  transform: translateX(2px)
  color: var(--vs-brand)

@media (max-width: 900px)
  .steps
    grid-template-columns: 1fr
</style>
