<script setup lang="ts">
/**
 * ArchiveList：本人存档列表（FR-1102 / FR-1103）：按关卡分组，
 * 播放、删除（二次确认）。
 */
import { computed, ref } from 'vue'
import { audioFileUrl, type ArchiveRecordingSummary } from '@/api'
import { usePlayerStore } from '@/stores/player'
import { useArchive } from '@/features/archive'
import { errorCopy } from '@/copy/usePageCopy'
import { formatDateTime } from '@/utils'
import AppIcon from '@/components/ui/AppIcon.vue'
import DangerConfirmDialog from './DangerConfirmDialog.vue'

const archive = useArchive()
const player = usePlayerStore()

const deleting = ref<ArchiveRecordingSummary | null>(null)
const clearing = ref(false)

const groups = computed(() =>
  [...archive.byLevel.value.entries()].map(([levelId, items]) => ({
    levelId,
    title: archive.levelTitle(levelId),
    items: [...items].sort((x, y) => new Date(y.createdAt ?? 0).getTime() - new Date(x.createdAt ?? 0).getTime()),
  })),
)

function play(item: ArchiveRecordingSummary) {
  void player.play({ key: `audio:${item.audioId}`, url: audioFileUrl(item.audioId), label: '存演回放' })
}

/** 紧凑分数：声母/韵母/声调为主，综合分次之（与 ScoreCard 同口径） */
function scoreText(score: NonNullable<ArchiveRecordingSummary['score']>): string {
  const part = (v: number | null | undefined) => (typeof v === 'number' ? Math.round(v) : '—')
  return `声母${part(score.initial)} 韵母${part(score.final)} 声调${part(score.tone)} · 综合${Math.round(score.overall)}`
}
</script>

<template>
  <div class="archive-list">
    <p v-if="archive.loading.value" class="al-note">读取中…</p>
    <p v-else-if="groups.length === 0 && !archive.error.value" class="al-note">
      还没有保存的录音。去关卡页录一关，结果会自动保存到这里。
    </p>
    <p v-else-if="archive.error.value" class="al-error">{{ errorCopy(archive.error.value).title }}</p>

    <div v-if="groups.length > 0" class="al-toolbar">
      <span class="al-total">{{ groups.length }} 关 · {{ archive.items.value.length }} 条记录</span>
      <button type="button" class="vs-btn vs-btn--ghost vs-btn--small al-danger" @click="clearing = true">
        <AppIcon name="trash" size="sm" />清空全部档案
      </button>
    </div>

    <section v-for="group in groups" :key="group.levelId" class="al-group">
      <header class="al-group-head">
        <h3>{{ group.title }}</h3>
        <span class="al-count">{{ group.items.length }} 条记录</span>
      </header>
      <ul class="al-items">
        <li v-for="item in group.items" :key="item.recordingId" class="al-item">
          <div class="al-main">
            <span class="al-date">{{ formatDateTime(item.createdAt ?? undefined) }}</span>
            <span class="vs-tag" :class="item.verdict === 'pass' ? 'al-pass' : 'al-fail'">
              {{ item.verdict === 'pass' ? '录音质量良好' : '录音质量欠佳' }}
            </span>
            <span v-if="item.score" class="al-score">{{ scoreText(item.score) }}</span>
          </div>
          <div class="al-actions">
            <button type="button" class="vs-btn vs-btn--ghost vs-btn--small" @click="play(item)">
              <AppIcon :name="player.isCurrent(`audio:${item.audioId}`) ? 'pause' : 'play'" size="sm" />
              {{ player.isCurrent(`audio:${item.audioId}`) ? '暂停' : '播放' }}
            </button>
            <RouterLink class="vs-btn vs-btn--small" :to="`/result/${item.recordingId}`">查看</RouterLink>
            <button type="button" class="vs-btn vs-btn--ghost vs-btn--small al-danger" @click="deleting = item">
              <AppIcon name="trash" size="sm" />删除
            </button>
          </div>
        </li>
      </ul>
    </section>

    <!-- 键集分页：超过一页（默认 20 条）时加载更多，避免列表被静默截断 -->
    <div v-if="archive.hasMore.value" class="al-more-row">
      <button
        type="button"
        class="vs-btn vs-btn--ghost vs-btn--small"
        :disabled="archive.loadingMore.value"
        @click="archive.loadMore()"
      >
        {{ archive.loadingMore.value ? '加载中…' : '加载更多记录' }}
      </button>
      <span v-if="archive.loadMoreError.value" class="al-error">加载更多失败，请再试一次。</span>
    </div>

    <DangerConfirmDialog
      :open="deleting !== null"
      title="删除这条录音？"
      message="将删除这条录音及其结果、特征与缓存，不可恢复；若音域依赖这条录音，音域会按剩余记录重算。"
      confirm-label="删除"
      @confirm="deleting && archive.removeOne(deleting.recordingId); deleting = null"
      @cancel="deleting = null"
    />
    <DangerConfirmDialog
      :open="clearing"
      title="清空全部档案？"
      message="将删除全部已存档录音、结果、特征与缓存；学习进度保留，音域按剩余数据重算。此操作不可恢复。"
      confirm-label="全部删除"
      @confirm="clearing = false; archive.clearAll()"
      @cancel="clearing = false"
    />
  </div>
</template>

<style scoped lang="sass">
.al-note
  color: var(--vs-sub)
  padding: 16px 0
  font-size: 14px

.al-error
  color: var(--vs-brand-d)
  font-size: 13px

.al-toolbar
  display: flex
  justify-content: space-between
  align-items: center
  gap: 10px
  flex-wrap: wrap
  margin-bottom: 4px

.al-total
  font-size: 12.5px
  color: var(--vs-mute)

.al-group
  margin-top: 12px
  border: 1px solid var(--vs-line)
  border-radius: 8px
  padding: 18px 20px
  background: var(--vs-card)
  box-shadow: var(--vs-sh-1)

.al-group-head
  display: flex
  justify-content: space-between
  align-items: baseline
  h3
    margin: 0
    font-size: 16px
    font-weight: 800

.al-count
  font-size: 12px
  color: var(--vs-mute)

.al-items
  list-style: none
  margin: 10px 0 0
  padding: 0
  display: flex
  flex-direction: column

.al-item
  display: flex
  justify-content: space-between
  align-items: center
  gap: 10px
  flex-wrap: wrap
  border-top: 1px solid var(--vs-line)
  padding: 12px 0

.al-item:first-child
  border-top: none

.al-main
  display: flex
  gap: 10px
  align-items: center
  flex-wrap: wrap
  min-width: 0

.al-date
  font-size: 13px
  color: var(--vs-ink2)

.al-pass
  background: var(--vs-green-soft)
  color: var(--vs-green)

.al-fail
  background: var(--vs-amber-soft)
  color: var(--vs-amber-ink)

.al-score
  font-weight: 700
  font-size: 13px
  color: var(--vs-ink2)
  font-variant-numeric: tabular-nums

.al-actions
  display: flex
  gap: 8px
  flex-wrap: wrap

.al-danger
  color: var(--vs-brand-d)

.al-more-row
  margin-top: 16px
  display: flex
  align-items: center
  gap: 12px
</style>
