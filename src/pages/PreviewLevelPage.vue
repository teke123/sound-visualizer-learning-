<script setup lang="ts">
/**
 * /preview/levels/:id?token=（FD-12 / §6.8）：管理员草稿真实预览。
 * 只读能力：不挂载 assessment、不产生学习事件、不显示反馈；
 * 401/403/404 → 「预览已失效，请回后台重新打开」。
 */
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { usePreview } from '@/features/preview'
import LevelView from '@/renderers/LevelView.vue'
import PageState from '@/components/PageState.vue'
import { formatDateTime } from '@/utils'

const route = useRoute()
const preview = usePreview()

const levelId = computed(() => String(route.params.id ?? ''))

onMounted(() => {
  void preview.loadLevel(levelId.value)
})
</script>

<template>
  <div class="preview-page">
    <header class="preview-banner" role="note">
      <span>👁 草稿预览（不计入大众端页面）</span>
      <span v-if="preview.level.value && preview.level.value.contentVersion">
        内容版本 v{{ preview.level.value.contentVersion }}
      </span>
    </header>

    <PageState v-if="preview.loading.value" state="loading" />
    <div v-else-if="preview.invalid.value" class="preview-invalid">
      <p>预览已失效，请回后台重新打开。</p>
      <p class="invalid-sub">预览令牌默认 15 分钟有效，且绑定管理员会话与草稿修订。</p>
    </div>
    <PageState v-else-if="!preview.level.value" state="not-visible" text="草稿内容读取失败" />
    <LevelView
      v-else
      :level="preview.level.value"
      :media-resolver="preview.previewMediaUrl"
      :practice-done-ids="new Set()"
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
