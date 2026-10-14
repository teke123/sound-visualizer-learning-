<script setup lang="ts">
// 搜索（P02，FR-301~305）：支持汉字、拼音、关卡名搜索；结果仅含已发布关卡，
// 字段完整（检测开放）的关优先；无结果时给出相近已发布关与「希望增加」提交口。
// 以下为占位状态与动作（不包含任何假实现），重构时按意图恢复。
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUnitsStore } from '@/stores/units'
import { usePageCopy } from '@/composables/usePageCopy'
import PageState from '@/components/PageState.vue'
import PageFeedback from '@/components/PageFeedback.vue'
import SiteFooter from '@/components/SiteFooter.vue'

const route = useRoute()
const router = useRouter()
const unitsStore = useUnitsStore()
const { copy } = usePageCopy('P02')

const q = computed(() => (route.query.q as string) || '')
const filterCategory = ref('all')

/** TODO(重构): 结果与相近关由后端搜索驱动（仅已发布，FR-303；完整关优先 FR-305） */
type UnitHit = { id: string; character: string; pinyin: string; category?: string; conclusion?: string; description?: string }
const results = ref<UnitHit[]>([])
const similar = ref<UnitHit[]>([])

const requestText = ref('')
const submitting = ref(false)
function submitRequest(): void { /* TODO(重构): 「希望增加」提交口（FR-304/FR-1503） */ }
</script>

<template>
  <div class="search-view">
    <h2>搜索结果</h2>
    <p v-if="q" class="query">关键词：{{ q }}</p>
    <p class="hint">{{ copy.subtitle }}</p>

    <div class="filters">
      <el-select v-model="filterCategory" placeholder="类型" style="width: 140px">
        <el-option label="全部类型" value="all" />
        <el-option label="单韵母" value="单韵母" />
        <el-option label="声母" value="声母" />
        <el-option label="拼读" value="拼读" />
      </el-select>
    </div>

    <!-- 后端不可用 ≠ 没有内容：错误态走 P02 文案位，并把 store 的原始错误放进 detail，便于定位后端没起 -->
    <PageState
      v-if="unitsStore.error"
      state="error"
      :copy="copy"
      :detail="unitsStore.error"
      @action="unitsStore.fetchPublished()"
    />

    <div v-if="results.length" class="result-list">
      <!-- 结果字段（FR-302）：关卡名称、类型、一句话结论、进入关卡按钮 -->
      <el-card v-for="u in results" :key="u.id" shadow="hover" class="result-card">
        <div class="head">
          <strong>{{ u.character }}</strong>
          <span>{{ u.pinyin }}</span>
          <el-tag size="small">{{ u.category }}</el-tag>
        </div>
        <p>{{ u.conclusion || u.description }}</p>
        <el-button type="primary" size="small" @click="router.push(`/learn/${u.id}`)">进入关卡</el-button>
      </el-card>
    </div>

    <!-- 空态：文案位只说「没找到」，相近内容与提交需求仍是现有功能，保留在下方 -->
    <div v-else-if="!unitsStore.error" class="empty">
      <PageState state="empty" :copy="copy" />
      <template v-if="similar.length">
        <h3>相近的已发布关</h3>
        <div class="result-list">
          <el-card v-for="u in similar" :key="u.id" shadow="hover" class="result-card">
            <div class="head"><strong>{{ u.character }}</strong><span>{{ u.pinyin }}</span></div>
            <p>{{ u.conclusion }}</p>
            <el-button size="small" @click="router.push(`/learn/${u.id}`)">进入关卡</el-button>
          </el-card>
        </div>
      </template>
      <el-button @click="router.push('/map')">返回发音地图</el-button>
      <div class="request-box">
        <h3>希望增加</h3>
        <el-input v-model="requestText" :placeholder="q ? `例如：希望增加「${q}」相关内容` : '描述希望增加的音、字或问题'" />
        <el-button type="primary" :loading="submitting" @click="submitRequest">提交</el-button>
      </div>
    </div>

    <PageFeedback page="search" type="request" />
    <SiteFooter />
  </div>
</template>

<style scoped>
.search-view { max-width: 800px; margin: 0 auto; }
.query, .hint { color: #909399; font-size: 13px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 16px; }
.result-list { display: flex; flex-direction: column; gap: 12px; margin: 16px 0; }
.result-card .head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.result-card p { color: #606266; font-size: 14px; margin: 0 0 12px; }
.empty { padding: 16px; background: #fff; border-radius: 12px; }
.request-box { margin-top: 20px; display: flex; flex-direction: column; gap: 8px; }
@media (max-width: 600px) { .filters .el-select { width: 100% !important; } }
</style>
