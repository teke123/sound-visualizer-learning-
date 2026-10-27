<script setup lang="ts">
/**
 * P10 声音档案（FR-1101–1103）：未登录 → 登录引导；已登录 → 存档列表 + 删除。
 */
import { computed, onMounted, watch } from 'vue'
import { QBtn, QCard, QCardSection } from 'quasar'
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
      <QCard flat bordered class="no-archive-card">
        <QCardSection>
          <h2>登录后查看你的声音档案</h2>
          <p>登录后每次录音检测的结果都会自动保存到这里，随时回看每一次的录音与成绩。</p>
          <div class="no-archive-actions">
            <QBtn unelevated no-caps color="primary" label="登录" to="/account/login?redirect=/archive" />
            <QBtn outline no-caps color="primary" label="注册" to="/account/register" />
          </div>
        </QCardSection>
      </QCard>
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

// 卡片视觉由 QCard flat bordered 提供
.no-archive-card
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
</style>
