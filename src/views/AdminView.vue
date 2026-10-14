<script setup lang="ts">
// 后台管理台（CMS，FR-1401~1408，单一管理员 D-09）：按关卡字段录入与媒体上传、
// 发布 / 下架（三态：草稿 / 已发布 / 已下架，SRS 05 附录 C）、检测开关（FR-1204 前置校验）、
// 版本管理与回退、反馈处理（待处理 / 已采纳 / 暂不采纳）。数据全部来自 /api/admin/*。
// 以下为占位状态与动作（不包含任何假实现），重构时按意图恢复并接管理员鉴权（NFR-16）。
import { ref } from 'vue'
import { usePageCopy } from '@/composables/usePageCopy'

usePageCopy('ADMIN')

const activeTab = ref('content')

/** TODO(重构): 单元行 = 附录 A 字段组 + 三态 + 检测开关 + 版本 */
type UnitRow = {
  id: string; order?: number; code?: string; pinyin?: string; character?: string
  category?: string; status: 'draft' | 'published' | 'unpublished'; verified?: boolean
  version?: number; conclusion?: string; detail?: string; demoAudio?: string; promptText?: string
}
const units = ref<UnitRow[]>([])
const feedbacks = ref<Array<{ id: string; createdAt: string; page?: string; rating?: string; message?: string; status?: string }>>([])
const versions = ref<Array<{ version: number; publishedAt: string; operator?: string; note?: string }>>([])

const dialogVisible = ref(false)
const editingUnit = ref<UnitRow | null>(null)

function openCreate(): void { /* TODO(重构): 新建草稿（录入即草稿） */ }
function editUnit(row: UnitRow): void { editingUnit.value = row; dialogVisible.value = true }
function preview(unitId: string): void { /* TODO(重构): 大众端真实效果预览（FR-1401） */ void unitId }
function publishUnit(unitId: string): void { /* TODO(重构): POST /api/admin/units/{id}/publish（FR-1203 校验在后端） */ void unitId }
function unpublishUnit(unitId: string): void { /* TODO(重构): POST /api/admin/units/{id}/unpublish */ void unitId }
function toggleDetection(row: UnitRow): void { /* TODO(重构): POST set-detection（FR-1204） */ void row }
function onMediaUpload(): boolean { /* TODO(重构): /api/media/upload */ return false }
function rollback(row: { version: number }): void { /* TODO(重构): 以历史快照再发布新版本（FR-1408） */ void row }
function handleFeedback(fbId: string, status: 'adopted' | 'rejected'): void { /* TODO(重构): 反馈状态流转（FR-1407） */ void fbId; void status }
function saveUnit(): void { /* TODO(重构): 保存草稿（仅草稿/已下架可编辑） */ }
</script>

<template>
  <div class="admin-view">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="内容管理" name="content">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>关卡内容（CMS）</span>
              <el-button type="primary" size="small" @click="openCreate">添加关卡</el-button>
            </div>
          </template>
          <el-table :data="units" stripe>
            <el-table-column prop="order" label="#" width="50" />
            <el-table-column prop="code" label="关卡" width="70" />
            <el-table-column prop="pinyin" label="拼音" width="100" />
            <el-table-column prop="character" label="汉字" width="80" />
            <el-table-column prop="category" label="类型" width="90" />
            <el-table-column label="发布状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'published' ? 'success' : row.status === 'unpublished' ? 'warning' : 'info'" size="small">
                  {{ ({ draft: '草稿', published: '已发布', unpublished: '已下架' } as Record<string, string>)[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="检测开关" width="90">
              <template #default="{ row }">
                <el-tag :type="row.verified ? 'success' : 'info'" size="small" effect="plain">
                  {{ row.verified ? '开放' : '关闭' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="version" label="版本" width="70" />
            <el-table-column label="操作" min-width="260">
              <template #default="{ row }">
                <el-button size="small" @click="editUnit(row)">编辑</el-button>
                <el-button size="small" @click="preview(row.id)">预览</el-button>
                <el-button v-if="row.status !== 'published'" size="small" type="success" @click="publishUnit(row.id)">发布</el-button>
                <el-button v-else size="small" type="warning" @click="unpublishUnit(row.id)">下架</el-button>
                <el-button size="small" @click="toggleDetection(row)">{{ row.verified ? '关闭检测' : '开放检测' }}</el-button>
              </template>
            </el-table-column>
          </el-table>
          <p class="field-note">
            发布须满足 FR-1203 前置条件（字段完整、示范可播、授权齐全）；开放检测须满足 FR-1204
            （朗读文本与示范一致、质量两维接通、允许指标在评分服务能力内、四步模板齐全）。
            关卡依赖：L30 待 L01 与 L09 均已发布后方可发布。
          </p>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="媒体管理" name="media">
        <el-upload drag :auto-upload="true" :before-upload="onMediaUpload" accept="audio/*,image/*">
          <el-icon :size="48"><UploadFilled /></el-icon>
          <div>上传音频 / 图片 / 动画 / 字幕（写入 uploads/，登记授权记录，FR-1402/1207）</div>
        </el-upload>
      </el-tab-pane>

      <el-tab-pane label="版本管理" name="versions">
        <el-table :data="versions" stripe>
          <el-table-column prop="version" label="版本" width="80" />
          <el-table-column prop="publishedAt" label="发布时间" width="170" />
          <el-table-column prop="operator" label="操作人" width="100" />
          <el-table-column prop="note" label="修改记录" show-overflow-tooltip />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="rollback(row)">回退到此版本</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p class="field-note">版本快照与回退（FR-1408）：回退 = 以历史快照再发布一个新版本。</p>
      </el-tab-pane>

      <el-tab-pane label="用户反馈" name="feedback">
        <el-table :data="feedbacks" stripe>
          <el-table-column prop="createdAt" label="时间" width="170" />
          <el-table-column prop="page" label="页面" width="120" />
          <el-table-column prop="rating" label="评价" width="80" />
          <el-table-column prop="message" label="内容" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column label="处理" width="180">
            <template #default="{ row }">
              <el-button size="small" @click="handleFeedback(row.id, 'adopted')">已采纳</el-button>
              <el-button size="small" @click="handleFeedback(row.id, 'rejected')">暂不采纳</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p class="field-note">反馈须经处理后方可影响检测规则（FR-1407）。</p>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialogVisible" title="编辑关卡" width="560px">
      <el-form v-if="editingUnit" label-width="90px">
        <el-form-item label="关卡 ID"><el-input v-model="editingUnit.id" :disabled="!!editingUnit.id" /></el-form-item>
        <el-form-item label="拼音"><el-input v-model="editingUnit.pinyin" /></el-form-item>
        <el-form-item label="代表汉字"><el-input v-model="editingUnit.character" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="editingUnit.category">
            <el-option label="单韵母" value="单韵母" />
            <el-option label="声母" value="声母" />
            <el-option label="拼读" value="拼读" />
          </el-select>
        </el-form-item>
        <el-form-item label="一句话结论"><el-input v-model="editingUnit.conclusion" type="textarea" /></el-form-item>
        <el-form-item label="构形说明"><el-input v-model="editingUnit.detail" type="textarea" /></el-form-item>
        <!-- 示范音：CMS 已发布的正式授权录音；缺失时前端可用合成示意但必须如实标注 -->
        <el-form-item label="示范音">
          <el-input v-model="editingUnit.demoAudio" placeholder="已授权示范音地址，例如 /api/media/{id}/file" />
          <p class="field-note">填入后关卡页直接播真实录音；留空则用语音合成示意并标注「非正式授权示范音」。</p>
        </el-form-item>
        <el-form-item label="检测任务">
          <el-input v-model="editingUnit.promptText" placeholder="朗读提示词（须与示范一致，FR-1204）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveUnit">保存草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.admin-view { background: #fff; border-radius: 12px; padding: 24px; }
.field-note { margin: 8px 0 0; font-size: 12px; color: #a8abb2; line-height: 1.6; }
</style>
