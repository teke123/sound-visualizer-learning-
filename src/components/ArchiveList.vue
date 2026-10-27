<script setup lang="ts">
/**
 * ArchiveList：本人存档列表（FR-1102 / FR-1103）：按关卡分组，
 * 播放、删除（二次确认）。
 */
import { computed, ref } from 'vue'
import { QBadge, QBtn } from 'quasar'
import { audioFileUrl, type ArchiveRecordingSummary } from '@/api'
import { usePlayerStore } from '@/stores/player'
import { useArchive } from '@/features/archive'
import { errorCopy } from '@/copy/usePageCopy'
import { formatDateTime } from '@/utils'
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
    <p v-if="archive.loading.value" class="al-loading">读取中…</p>
    <p v-else-if="groups.length === 0 && !archive.error.value" class="al-empty">
      还没有保存的录音。去关卡页录一关，结果会自动保存到这里。
    </p>
    <p v-else-if="archive.error.value" class="al-error">{{ errorCopy(archive.error.value).title }}</p>

    <div v-if="groups.length > 0" class="al-toolbar">
      <QBtn
        outline
        no-caps
        color="red-3"
        text-color="red-9"
        class="al-clear"
        label="清空全部档案"
        @click="clearing = true"
      />
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
            <QBadge :class="['al-verdict', item.verdict]">{{ item.verdict === 'pass' ? '录音质量良好' : '录音质量欠佳' }}</QBadge>
            <span v-if="item.score" class="al-score">{{ scoreText(item.score) }}</span>
          </div>
          <div class="al-actions">
            <QBtn outline no-caps color="blue-grey-4" text-color="blue-grey-9" class="al-action" @click="play(item)">
              {{ player.isCurrent(`audio:${item.audioId}`) ? '⏸ 暂停' : '▶ 播放' }}
            </QBtn>
            <RouterLink class="al-btn" :to="`/result/${item.recordingId}`">查看</RouterLink>
            <QBtn
              outline
              no-caps
              color="red-3"
              text-color="red-9"
              class="al-action"
              label="删除"
              @click="deleting = item"
            />
          </div>
        </li>
      </ul>
    </section>

    <!-- 键集分页：超过一页（默认 20 条）时加载更多，避免列表被静默截断 -->
    <div v-if="archive.hasMore.value" class="al-more-row">
      <QBtn
        outline
        no-caps
        color="blue-grey-3"
        text-color="blue-grey-9"
        class="al-more"
        :disable="archive.loadingMore.value"
        @click="archive.loadMore()"
      >
        {{ archive.loadingMore.value ? '加载中…' : '加载更多记录' }}
      </QBtn>
      <span v-if="archive.loadMoreError.value" class="al-error">
        加载更多失败，请再试一次。
      </span>
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
.al-loading, .al-empty
  color: #90a4ae
  padding: 16px 0

.al-error
  color: #c62828

.al-toolbar
  display: flex
  justify-content: flex-end
  margin-bottom: 6px

.al-group
  margin-top: 12px
  border: 1px solid #eceff1
  border-radius: 12px
  padding: 14px
  background: #fff

.al-group-head
  display: flex
  justify-content: space-between
  align-items: baseline
  h3
    margin: 0
    font-size: 16px

.al-count
  font-size: 12px
  color: #90a4ae

.al-items
  list-style: none
  margin: 10px 0 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 8px

.al-item
  display: flex
  justify-content: space-between
  align-items: center
  gap: 10px
  flex-wrap: wrap
  border-bottom: 1px dashed #eceff1
  padding: 8px 0

.al-main
  display: flex
  gap: 10px
  align-items: center
  flex-wrap: wrap

.al-date
  font-size: 13px
  color: #546e7a

.al-verdict
  font-size: 12px
  &.pass
    background: #e8f5e9
    color: #2e7d32
  &.fail
    background: #fff3e0
    color: #8d5b00

.al-score
  font-weight: 700

.al-version
  font-size: 11px
  color: #b0bec5

.al-actions
  display: flex
  gap: 8px

/* RouterLink「查看」保留手写按钮观感（RouterLink 不换成 QBtn），与相邻 QBtn outline 视觉对齐 */
.al-btn
  min-height: 40px
  padding: 2px 14px
  border: 1px solid #90a4ae
  border-radius: 8px
  background: #fff
  cursor: pointer
  color: #37474f
  text-decoration: none
  display: inline-flex
  align-items: center

/* QBtn 恢复原版 .al-btn/.al-clear 的 8px 小圆角与 40px 高度 */
.al-action, .al-clear
  border-radius: 8px
  min-height: 40px

/* 原 .al-more 为 #b0bec5 描边胶囊（半径走全局 999px），仅补回 40px 高度 */
.al-more
  min-height: 40px

.al-more-row
  margin-top: 14px
  display: flex
  align-items: center
  gap: 12px
</style>
