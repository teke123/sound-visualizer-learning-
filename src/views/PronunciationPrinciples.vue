<script setup lang="ts">
// 发音原理（P04，FR-501~505）：按「气 → 声 → 口型」三步组织内容；每步配可跟做的
// 短练习并链到已发布的相关关卡；专业句默认折叠；同一原理至少一个可播放示范。
// 教学内容经内容服务下发（FR-1206），不在前端硬编码。
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { usePageCopy } from '@/composables/usePageCopy'
import PageState from '@/components/PageState.vue'
import PageFeedback from '@/components/PageFeedback.vue'
import SiteFooter from '@/components/SiteFooter.vue'

const router = useRouter()
const { copy } = usePageCopy('P04')

/** 原理段落（气/声/口型三步），TODO(重构): 从内容服务拉取 */
const sections = ref<Array<{ id: string; title: string; summary: string; body: string; practiceLevelId?: string }>>([])
</script>

<template>
  <div class="principles-view">
    <h2>发音原理</h2>
    <p class="intro">{{ copy.subtitle }}</p>

    <!-- 三步结构（FR-501 固定：气 → 声 → 口型） -->
    <el-card class="overview-card">
      <div class="flow">气 → 声 → 口型</div>
      <p class="note">气从哪里来、声音怎么响、嘴和舌头怎么摆；每一步都有短练习和已发布关入口。</p>
    </el-card>

    <PageState v-if="!sections?.length" state="empty" :copy="copy" />

    <div v-else class="sections">
      <el-card v-for="s in sections" :key="s.id" shadow="hover" class="section-card">
        <h3>{{ s.title }}</h3>
        <p class="summary">{{ s.summary }}</p>
        <el-collapse>
          <el-collapse-item title="详细说明" :name="s.id">
            <p>{{ s.body }}</p>
          </el-collapse-item>
          <!-- 专业句默认折叠（FR-503：部位名称、气流通道、声带细节） -->
          <el-collapse-item title="专业句（按需展开）" :name="s.id + '-pro'">
            <p class="boundary">专业内容仅用于理解发音，学习参考，不作为普通话等级认定或医学诊断。</p>
          </el-collapse-item>
        </el-collapse>
        <el-button v-if="s.practiceLevelId" type="primary" link @click="router.push(`/learn/${s.practiceLevelId}`)">
          进入相关关卡练习
        </el-button>
      </el-card>
    </div>

    <PageFeedback page="principles" type="learning" />
    <SiteFooter />
  </div>
</template>

<style scoped>
.principles-view { max-width: 900px; margin: 0 auto; }
.intro { color: #606266; margin-bottom: 20px; }
.overview-card { margin-bottom: 20px; }
.flow { font-size: 20px; font-weight: 600; color: #409eff; margin: 12px 0; }
.note, .boundary { font-size: 13px; color: #909399; }
.sections { display: flex; flex-direction: column; gap: 16px; }
.summary { color: #606266; }
</style>
