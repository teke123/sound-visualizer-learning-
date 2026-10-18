<script setup lang="ts">
/**
 * P10 声音档案（FR-1101–1103）：未登录 → 登录引导；已登录 → 存档列表 + 删除 + 同关比较。
 */
import { computed, onMounted, watch } from 'vue'
import { useArchive } from '@/features/archive'
import ArchiveList from '@/components/ArchiveList.vue'
import PageState from '@/components/PageState.vue'

const archive = useArchive()

const view = computed(() => archive.view.value)

onMounted(() => {
  void archive.load()
})
watch(view, () => void archive.load())
</script>

<template>
  <div class="archive-page">
    <header class="arch-head">
      <h1>声音档案</h1>
    </header>

    <!-- 未登录：登录后自动保存录音与进度 -->
    <section v-if="view === 'guest'" class="no-archive">
      <div class="no-archive-card">
        <h2>登录后查看你的声音档案</h2>
        <p>登录后每次录音检测的结果都会自动保存到这里，可以在同一关比较两次录音，看到变化。</p>
        <div class="no-archive-actions">
          <RouterLink to="/account/login?redirect=/archive" class="na-btn primary">登录</RouterLink>
          <RouterLink to="/account/register" class="na-btn">注册</RouterLink>
        </div>
      </div>
    </section>

    <!-- 已登录：档案列表 -->
    <section v-else class="archive-list-wrap">
      <PageState v-if="archive.loading.value && archive.items.value.length === 0" state="loading" />
      <ArchiveList v-else />
    </section>
  </div>
</template>

<style scoped lang="sass">
.archive-page
  display: flex
  flex-direction: column
  gap: 20px

.arch-head h1
  margin: 0
  font-size: 24px

.no-archive-card
  background: #fff
  border: 1px solid #eceff1
  border-radius: 14px
  padding: 20px
  h2
    margin: 0 0 8px
    font-size: 18px
  p
    margin: 4px 0
    color: #546e7a
    font-size: 14px

.no-archive-actions
  display: flex
  gap: 10px
  margin-top: 12px

.na-btn
  min-height: 44px
  display: inline-flex
  align-items: center
  padding: 4px 20px
  border-radius: 999px
  border: 1px solid #90a4ae
  background: #fff
  color: #37474f
  text-decoration: none
  cursor: pointer
  &.primary
    background: #00897b
    border-color: #00897b
    color: #fff
    font-weight: 600
</style>
