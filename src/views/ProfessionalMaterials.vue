<script setup lang="ts">
// 专业资料（P07，FR-801~804）：默认折叠进入；只提供已授权的摘要、说明或合法链接；
// 每条资料有标题、来源、许可、适用边界，并链到至少一关已发布关卡；
// 页面明确「资料用于帮助理解发音，仅供学习参考」。
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { usePageCopy } from '@/composables/usePageCopy'
import PageState from '@/components/PageState.vue'
import PageFeedback from '@/components/PageFeedback.vue'
import SiteFooter from '@/components/SiteFooter.vue'

const router = useRouter()
const { copy } = usePageCopy('P07')

/** 资料列表，TODO(重构): 从内容服务拉取（须有来源/许可/适用边界与关联关卡） */
const materials = ref<Array<{ id: string; title: string; summary: string; scope: string; source: string; license: string; relatedLevels: string[] }>>([])
</script>

<template>
  <div class="materials-view">
    <h2>专业资料</h2>
    <p class="intro">{{ copy.subtitle }}</p>
    <p class="source-note">资料用于帮助理解发音，仅供学习参考（FR-804）。</p>

    <PageState v-if="!materials?.length" state="empty" :copy="copy" :show-action="false" />

    <div v-else class="list">
      <el-card v-for="m in materials" :key="m.id" shadow="hover">
        <h3>{{ m.title }}</h3>
        <p>{{ m.summary }}</p>
        <p class="scope"><strong>适用边界：</strong>{{ m.scope }}</p>
        <p class="meta">来源：{{ m.source }} · 许可：{{ m.license }}</p>
        <div class="related">
          <span>相关关卡：</span>
          <el-button v-for="lid in m.relatedLevels" :key="lid" link type="primary" @click="router.push(`/learn/${lid}`)">{{ lid }}</el-button>
        </div>
      </el-card>
    </div>

    <PageFeedback page="materials" type="content" />
    <SiteFooter />
  </div>
</template>

<style scoped>
.materials-view { max-width: 900px; margin: 0 auto; }
.intro { color: #606266; margin-bottom: 8px; }
.source-note { color: #909399; font-size: 13px; margin: 0 0 16px; }
.list { display: flex; flex-direction: column; gap: 12px; }
.scope, .meta { font-size: 13px; color: #909399; }
.related { margin-top: 8px; }
</style>
