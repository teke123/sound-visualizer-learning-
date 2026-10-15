<script setup lang="ts">
/**
 * P10 声音档案（FR-1101–1103 / FD-09）：按 context 三种态：
 * 访客 / 未同意 → 无档案说明 + 本会话临时记录；已同意 → 存档列表 + 删除 + 同关比较。
 */
import { computed, onMounted, watch } from 'vue'
import { useArchive } from '@/features/archive'
import { useConsent } from '@/features/consent'
import { useContextStore } from '@/stores/context'
import ArchiveList from '@/components/ArchiveList.vue'
import SessionRecordsPanel from '@/components/SessionRecordsPanel.vue'
import PageState from '@/components/PageState.vue'

const contextStore = useContextStore()
const archive = useArchive()
const consent = useConsent()

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

    <!-- 访客 / 未同意：无档案说明（FR-1101） -->
    <section v-if="view === 'guest' || view === 'no-consent'" class="no-archive">
      <div class="no-archive-card">
        <h2>还没有保存的录音</h2>
        <p>未{{ view === 'guest' ? '登录' : '同意保存' }}时，录音只在本会话可见，最长 72 小时。</p>
        <p>登录并同意保存后：</p>
        <ul>
          <li>本会话全部未过期录音与结果自动转存到档案</li>
          <li>之后每次录音都会自动保存，无须逐条操作</li>
          <li>可以在同一关比较两次录音，看到变化</li>
        </ul>
        <div class="no-archive-actions">
          <RouterLink v-if="view === 'guest'" to="/account/login?redirect=/archive" class="na-btn primary">
            登录
          </RouterLink>
          <RouterLink v-if="view === 'guest'" to="/account/register" class="na-btn">注册</RouterLink>
          <button v-if="view === 'no-consent'" type="button" class="na-btn primary" @click="consent.openDialog()">
            阅读保存说明并同意
          </button>
        </div>
      </div>

      <SessionRecordsPanel class="arch-session" />
    </section>

    <!-- 已同意：档案列表 -->
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
  ul
    margin: 8px 0
    padding-left: 18px
    color: #546e7a
    font-size: 14px
    line-height: 1.9

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

.arch-session
  margin-top: 18px
</style>
