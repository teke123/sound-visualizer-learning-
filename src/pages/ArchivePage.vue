<script setup lang="ts">
/**
 * P10 声音档案（FR-1101–1103）：未登录 → 登录引导；
 * 已登录 → 练习概览（练过的关 / 次数 / 平均与最好成绩）+ 存档列表 + 删除。
 */
import { computed, onMounted, watch } from 'vue'
import { useArchive } from '@/features/archive'
import ArchiveList from '@/components/ArchiveList.vue'
import PageState from '@/components/PageState.vue'
import PageHead from '@/components/ui/PageHead.vue'
import AppIcon from '@/components/ui/AppIcon.vue'

const archive = useArchive()

const view = computed(() => archive.view.value)

const stats = computed(() => {
  const items = archive.items.value
  const scores = items
    .map((item) => item.score?.overall)
    .filter((value): value is number => typeof value === 'number')
  return {
    total: items.length,
    levels: new Set(items.map((item) => item.levelId)).size,
    avg: scores.length > 0 ? Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length) : null,
    best: scores.length > 0 ? Math.round(Math.max(...scores)) : null,
  }
})

onMounted(() => {
  void archive.load()
})
watch(view, () => void archive.load())
</script>

<template>
  <div class="archive-page">
    <PageHead title="声音档案" icon="folder" />

    <!-- 未登录：登录引导 -->
    <section v-if="view === 'guest'" class="guest-box">
      <span class="guest-mark"><AppIcon name="lock" size="lg" /></span>
      <h2>登录后查看你的声音档案</h2>
      <p class="guest-note">
        登录后每次录音检测的结果都会自动保存到这里，可以回听录音、对比同一关的进步；
        也可以随时单条删除或清空。
      </p>
      <div class="guest-actions">
        <RouterLink class="vs-btn" to="/account/login?redirect=/archive">登录</RouterLink>
        <RouterLink class="vs-btn vs-btn--ghost" to="/account/register">注册</RouterLink>
      </div>
      <ul class="guest-facts">
        <li>用户名 + 密码即可，不收集邮箱或手机号</li>
      </ul>
    </section>

    <!-- 已登录：概览 + 列表 -->
    <template v-else>
      <div v-if="stats.total > 0" class="stats" aria-label="练习概览">
        <div><b>{{ stats.levels }}</b><span>练过的关</span></div>
        <div><b>{{ stats.total }}</b><span>录音次数</span></div>
        <div><b>{{ stats.avg ?? '—' }}</b><span>平均综合分</span></div>
        <div><b>{{ stats.best ?? '—' }}</b><span>最好成绩</span></div>
      </div>

      <PageState v-if="archive.loading.value && archive.items.value.length === 0" state="loading" />
      <ArchiveList v-else />
    </template>
  </div>
</template>

<style scoped lang="sass">
.archive-page
  display: flex
  flex-direction: column
  gap: 16px

.guest-box
  background: var(--vs-card)
  border: 1px solid var(--vs-line)
  border-radius: 8px
  box-shadow: var(--vs-sh-1)
  padding: 40px 24px
  text-align: center
  display: flex
  flex-direction: column
  align-items: center
  gap: 10px
  h2
    margin: 0
    font-size: 20px
    font-weight: 900
    letter-spacing: -0.3px

.guest-mark
  width: 56px
  height: 56px
  border-radius: 8px
  display: flex
  align-items: center
  justify-content: center
  background: var(--vs-soft)
  color: var(--vs-brand)
  margin-bottom: 4px

.guest-note
  margin: 0
  max-width: 520px
  font-size: 13.5px
  color: var(--vs-sub)
  line-height: 1.8

.guest-actions
  display: flex
  gap: 10px
  margin-top: 6px

.guest-facts
  list-style: none
  margin: 14px 0 0
  padding: 16px 0 0
  border-top: 1px dashed var(--vs-line2)
  display: flex
  flex-direction: column
  gap: 6px
  li
    font-size: 12.5px
    color: var(--vs-mute)

.stats
  display: grid
  grid-template-columns: repeat(4, 1fr)
  background: var(--vs-card)
  border: 1px solid var(--vs-line)
  border-radius: 8px
  padding: 20px 8px
  text-align: center
  box-shadow: var(--vs-sh-1)

.stats > div
  border-left: 1px solid var(--vs-line)

.stats > div:first-child
  border-left: none

.stats b
  display: block
  font-size: 26px
  font-weight: 800
  letter-spacing: -1px
  color: var(--vs-ink)
  font-variant-numeric: tabular-nums
  line-height: 1.2

.stats span
  font-size: 12px
  color: var(--vs-sub)

@media (max-width: 560px)
  .stats
    grid-template-columns: repeat(2, 1fr)
    gap: 12px 0
    padding: 16px 4px
  .stats > div:nth-child(3)
    border-left: none
</style>
