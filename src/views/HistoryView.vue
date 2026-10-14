<script setup lang="ts">
// 声音档案（P10，FR-1101~1103）：未登录或未同意时显示「还没有保存的录音」说明；
// 同意后按关卡保存记录，同关至少两次可并排播放与比较；可单条删除与清空。
// 同意展示基于服务端状态（NFR-15），删除为不可逆操作须二次确认。
// 以下为占位状态与动作（不包含任何假实现），重构时按意图恢复。
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useArchiveConsent } from '@/composables/useArchiveConsent'
import { usePageCopy } from '@/composables/usePageCopy'
import PageState from '@/components/PageState.vue'
import PageFeedback from '@/components/PageFeedback.vue'
import SiteFooter from '@/components/SiteFooter.vue'

const router = useRouter()
const userStore = useUserStore()
const { copy } = usePageCopy('P10')
const { consented, grant, revoke } = useArchiveConsent()

type ArchiveRecord = {
  id: string; unitId: string; character?: string; createdAt: string
  score: number; initialScore?: number; toneScore?: number
}
const records = ref<ArchiveRecord[]>([])

const showLoading = computed(() => false)       // TODO(重构): 接学习记录列表加载态
const showError = computed(() => !!userStore.error)
const showEmpty = computed(() => !records.value.length)

const compareUnit = ref('')
const unitOptions = computed(() => [...new Set(records.value.map(r => r.unitId))])
const compareRecords = computed(() => records.value.filter(r => r.unitId === compareUnit.value))
const leftId = ref('')
const rightId = ref('')
const leftRecord = computed(() => compareRecords.value.find(r => r.id === leftId.value) || null)
const rightRecord = computed(() => compareRecords.value.find(r => r.id === rightId.value) || null)

function enableArchive(): void { grant() }
function clearArchive(): void { /* TODO(重构): 二次确认后撤回同意并清空档案（FR-104） */ }
function reloadArchive(): void { /* TODO(重构): 重新拉取档案记录 */ }
function play(recordId: string): void { /* TODO(重构): 按记录 id 拉录音流并播放 */ }
function deleteOne(recordId: string): void { /* TODO(重构): 二次确认后删除单条（校验归属 NFR-18） */ }
</script>

<template>
  <div class="archive-view">
    <h2>我的声音学习档案</h2>

    <el-card class="consent-card">
      <h3>保存与隐私</h3>
      <p>访客录音默认不长期保留。同意后才写入个人档案，可随时单条删除或全部清空。</p>
      <div class="consent-actions">
        <el-button v-if="!consented" type="primary" @click="enableArchive">同意保存到我的档案</el-button>
        <template v-else>
          <el-tag type="success">已同意保存</el-tag>
          <el-button type="danger" plain @click="clearArchive">撤回同意并全部删除</el-button>
        </template>
      </div>
    </el-card>

    <template v-if="consented">
      <!-- 加载中 / 接口失败 / 还没有记录：三态互斥，文案统一走 P10 文案位 -->
      <PageState v-if="showLoading" state="loading" :copy="copy" />
      <PageState
        v-else-if="showError"
        state="error"
        :copy="copy"
        :detail="userStore.error || ''"
        @action="reloadArchive"
      />
      <PageState v-else-if="showEmpty" state="empty" :copy="copy" @action="router.push('/learn')" />

      <template v-else>
        <el-card class="compare-card">
          <h3>同关比较</h3>
          <el-select v-model="compareUnit" placeholder="选择关卡" style="width:100%;margin-bottom:12px">
            <el-option v-for="u in unitOptions" :key="u" :label="u" :value="u" />
          </el-select>
          <div v-if="compareRecords.length >= 2" class="compare-pick">
            <el-select v-model="leftId" placeholder="较早一次">
              <el-option v-for="r in compareRecords" :key="r.id" :label="new Date(r.createdAt).toLocaleString()" :value="r.id" />
            </el-select>
            <el-select v-model="rightId" placeholder="较近一次">
              <el-option v-for="r in compareRecords" :key="r.id" :label="new Date(r.createdAt).toLocaleString()" :value="r.id" />
            </el-select>
          </div>
          <div v-if="leftRecord && rightRecord" class="compare-result">
            <div><strong>记录 A</strong> 总分 {{ leftRecord.score }} · 声韵 {{ leftRecord.initialScore }} · 调型 {{ leftRecord.toneScore }}</div>
            <div><strong>记录 B</strong> 总分 {{ rightRecord.score }} · 声韵 {{ rightRecord.initialScore }} · 调型 {{ rightRecord.toneScore }}</div>
            <p>变化提示：总分差 {{ rightRecord.score - leftRecord.score }} 分（仅表示本关本次录音，仅供个人参考）</p>
            <el-button size="small" @click="play(leftRecord.id)">播放 A</el-button>
            <el-button size="small" @click="play(rightRecord.id)">播放 B</el-button>
          </div>
          <p v-else-if="compareUnit" class="hint">同一关至少需要 2 条记录才可并排比较（FR-1103）。</p>
        </el-card>

        <el-card>
          <template #header><span>时间线</span></template>
          <el-table :data="records" stripe>
            <el-table-column label="时间" width="170"><template #default="{ row }">{{ new Date(row.createdAt).toLocaleString() }}</template></el-table-column>
            <el-table-column prop="unitId" label="关卡" width="100" />
            <el-table-column prop="character" label="汉字" width="70" />
            <el-table-column prop="score" label="总分" width="80" />
            <el-table-column prop="reliabilityNote" label="结论" show-overflow-tooltip />
            <el-table-column label="操作" width="220">
              <template #default="{ row }">
                <el-button size="small" @click="play(row.id)">播放</el-button>
                <el-button size="small" @click="router.push(`/learn/${row.unitId}`)">重练</el-button>
                <el-button size="small" type="danger" @click="deleteOne(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </template>
    </template>

    <PageFeedback page="archive" type="learning" />
    <SiteFooter />
  </div>
</template>

<style scoped>
.archive-view { max-width: 960px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.consent-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.compare-pick { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.compare-result { font-size: 14px; line-height: 1.8; }
.hint { color: #909399; font-size: 13px; }
@media (max-width: 600px) { .compare-pick { grid-template-columns: 1fr; } }
</style>
