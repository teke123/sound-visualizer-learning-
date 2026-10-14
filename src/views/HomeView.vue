<script setup lang="ts">
// 首页（P01，FR-201~207）：四个主按钮（文案固定：搜一个音 / 看懂发音 / 跟着练 /
// 录音比较）、搜索框（提示可输入汉字、拼音或关卡名）、已发布关列表
// （默认从 L01 或当前进度的下一已发布关开始）、底部站点说明（普通话发音学习；
// 结果仅供学习参考——边界句见 SRS 07 章）。
// 「录音比较」进已开放检测的一关；若无，说明暂不可测并引导学习（FR-202）。
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useLevelsStore } from '@/stores/levels'
import { usePageCopy } from '@/composables/usePageCopy'
import type { PageStateKind } from '@/components/PageState.vue'
import PageState from '@/components/PageState.vue'
import SiteFooter from '@/components/SiteFooter.vue'

const router = useRouter()
const levelsStore = useLevelsStore()
const { copy } = usePageCopy('P01')

const searchQuery = ref('')

function doSearch() {
  const q = searchQuery.value.trim()
  router.push(q ? `/search?q=${encodeURIComponent(q)}` : '/search')
}

// TODO(重构): store 补 loading/error 状态后接入；当前关卡数据为空时不渲染状态块
const levelsState = computed<PageStateKind | null>(() => null)
</script>

<template>
  <div class="home-view">
    <section class="hero">
      <h1>看得见的声音</h1>
      <p class="tagline">普通话发音学习：看懂口型、听清示范、跟着练、录音比较。</p>
      <el-input
        v-model="searchQuery"
        size="large"
        placeholder="可输入汉字、拼音或关卡名，例如「a」「妈」「翘舌」"
        prefix-icon="Search"
        clearable
        @keyup.enter="doSearch"
      >
        <template #append>
          <el-button type="primary" @click="doSearch">搜索</el-button>
        </template>
      </el-input>
    </section>

    <!-- 四个主按钮（FR-202：文案固定，不可改） -->
    <section class="actions">
      <el-button size="large" class="action-btn" @click="router.push('/search')">
        <strong>搜一个音</strong>
        <span>用汉字、拼音或关卡名找到一关</span>
      </el-button>
      <el-button size="large" class="action-btn" @click="router.push('/principles')">
        <strong>看懂发音</strong>
        <span>气 → 声 → 口型，也可进入发音地图</span>
      </el-button>
      <el-button size="large" class="action-btn" @click="router.push('/learn')">
        <strong>跟着练</strong>
        <span>进入关卡页的练习区，一关一关来</span>
      </el-button>
      <el-button size="large" class="action-btn" @click="router.push('/test')">
        <strong>录音比较</strong>
        <span>在已开放检测的关录音，看曲线和反馈</span>
      </el-button>
    </section>

    <section class="levels">
      <h2>已发布关卡</h2>
      <p class="subtitle">{{ copy.subtitle }}</p>

      <!-- 加载 / 错误 / 空态统一走文案位：后端没连上要说清，不能让人误以为「就是没有内容」 -->
      <PageState :state="levelsState" :copy="copy" @action="levelsStore.fetchLevels()" />

      <div v-if="levelsStore.levels.length" class="level-grid">
        <el-card
          v-for="l in levelsStore.levels"
          :key="l.code"
          shadow="hover"
          class="level-card"
          @click="router.push(`/learn/${l.code}`)"
        >
          <div class="char">{{ l.char }}</div>
          <div class="code">{{ l.code }}</div>
        </el-card>
      </div>
    </section>

    <section class="profile-entry">
      <el-button text type="primary" @click="router.push('/archive')">进入我的声音档案 →</el-button>
      <el-button text type="primary" @click="router.push('/account')">账号与保存同意 →</el-button>
      <span class="guest-hint">未登录也可学习和录音（当次可见）；保存进度和录音需先登录并同意。</span>
    </section>

    <SiteFooter />
  </div>
</template>

<style scoped>
.home-view { max-width: 960px; margin: 0 auto; display: flex; flex-direction: column; gap: 28px; }
.hero { background: #fff; border-radius: 12px; padding: 32px 24px; }
.hero h1 { margin: 0 0 8px; font-size: 28px; color: #303133; }
.tagline { margin: 0 0 20px; color: #606266; }
.actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.action-btn { height: auto; padding: 16px; display: flex; flex-direction: column; align-items: flex-start; text-align: left; white-space: normal; }
.action-btn strong { font-size: 16px; margin-bottom: 4px; }
.action-btn span { font-size: 12px; color: #909399; font-weight: normal; }
.levels h2 { margin: 0 0 12px; font-size: 18px; }
.subtitle { color: #909399; font-size: 13px; margin: 0 0 12px; }
.level-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 12px; }
.level-card { cursor: pointer; text-align: center; }
.char { font-size: 32px; font-weight: 700; }
.code { color: #909399; font-size: 12px; margin-top: 4px; }
.profile-entry { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.guest-hint { font-size: 13px; color: #909399; }
</style>
