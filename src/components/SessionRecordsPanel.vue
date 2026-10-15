<script setup lang="ts">
/**
 * SessionRecordsPanel：本会话临时记录（FR-110 / FD-09）。
 * 位于 P10（未登录或未同意时）与 P11；单删 + 清空并重新开始会话。
 */
import { onMounted } from 'vue'
import { useSessionRecords } from '@/features/session'
import { useContextStore } from '@/stores/context'
import { useLevelsStore } from '@/stores/levels'
import { errorCopy } from '@/copy/usePageCopy'
import { formatDateTime, formatRemaining } from '@/utils'
import DangerConfirmDialog from './DangerConfirmDialog.vue'
import { ref } from 'vue'

const contextStore = useContextStore()
const levelsStore = useLevelsStore()
const session = useSessionRecords()
const resetOpen = ref(false)

onMounted(() => {
  void session.load()
})

function levelTitle(levelId: string): string {
  return levelsStore.byId.get(levelId)?.title ?? levelId
}
</script>

<template>
  <section class="session-records" aria-label="本会话临时记录">
    <header class="sr-head">
      <h3>本会话临时记录</h3>
      <p class="sr-hint">
        这些录音与结果只在本会话可见，最长保留 72 小时
        <template v-if="!contextStore.consentGranted">；登录并同意后会自动转存</template>。
        <template v-if="session.transferableCount.value > 0">同意后将转存 {{ session.transferableCount.value }} 条。</template>
      </p>
    </header>

    <p v-if="session.loading.value" class="sr-loading">读取中…</p>
    <p v-else-if="session.items.value.length === 0" class="sr-empty">本会话还没有临时录音。</p>
    <ul v-else class="sr-list">
      <li v-for="item in session.items.value" :key="item.recordingId" class="sr-item">
        <div class="sr-main">
          <RouterLink :to="`/result/${item.recordingId}`" class="sr-level">
            {{ levelTitle(item.levelId) }}
          </RouterLink>
          <span class="sr-time">{{ formatDateTime(item.createdAt ?? undefined) }}</span>
        </div>
        <div class="sr-meta">
          <span :class="['sr-verdict', item.verdict]">{{ item.verdict === 'pass' ? '可评' : '本次不能评' }}</span>
          <span v-if="typeof item.score === 'number'" class="sr-score">{{ Math.round(item.score) }} 分</span>
          <span class="sr-expire">{{ formatRemaining(item.expiresAt ?? undefined) }}</span>
        </div>
        <button type="button" class="sr-delete" @click="session.removeOne(item.recordingId)">删除</button>
      </li>
    </ul>

    <p v-if="session.error.value" class="sr-error">{{ errorCopy(session.error.value).title }}</p>

    <footer class="sr-foot">
      <button
        type="button"
        class="sr-reset"
        :disabled="session.items.value.length === 0"
        @click="resetOpen = true"
      >
        清空并重新开始会话
      </button>
      <p class="sr-foot-note">共用设备时可先清空，避免他人看到你的录音。</p>
    </footer>

    <DangerConfirmDialog
      :open="resetOpen"
      title="清空本会话临时数据？"
      message="将删除当前会话的全部临时录音、结果与临时标定，不可恢复；已存档记录不受影响。"
      confirm-label="清空并重新开始"
      @confirm="resetOpen = false; session.resetSession()"
      @cancel="resetOpen = false"
    />
  </section>
</template>

<style scoped lang="sass">
.session-records
  border: 1px solid #eceff1
  border-radius: 12px
  background: #fff
  padding: 16px

.sr-head
  h3
    margin: 0 0 4px
    font-size: 16px

.sr-hint
  margin: 0
  font-size: 13px
  color: #90a4ae
  line-height: 1.7

.sr-loading, .sr-empty
  color: #90a4ae
  font-size: 14px
  padding: 12px 0

.sr-list
  list-style: none
  margin: 12px 0 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 10px

.sr-item
  display: grid
  grid-template-columns: 1fr auto
  gap: 4px 12px
  border: 1px solid #eceff1
  border-radius: 10px
  padding: 10px 12px
  align-items: center

.sr-main
  display: flex
  gap: 10px
  align-items: baseline

.sr-level
  color: #00897b
  font-weight: 600
  text-decoration: none

.sr-time
  font-size: 12px
  color: #b0bec5

.sr-meta
  grid-column: 1
  display: flex
  gap: 8px
  align-items: center
  flex-wrap: wrap

.sr-verdict
  font-size: 12px
  border-radius: 4px
  padding: 1px 8px
  &.pass
    background: #e8f5e9
    color: #2e7d32
  &.fail
    background: #fff3e0
    color: #8d5b00

.sr-score
  font-size: 13px
  font-weight: 700
  color: #37474f

.sr-expire
  font-size: 12px
  color: #90a4ae

.sr-delete
  grid-row: 1 / span 2
  grid-column: 2
  min-height: 40px
  padding: 2px 14px
  border: 1px solid #ef9a9a
  color: #c62828
  background: #fff
  border-radius: 8px
  cursor: pointer

.sr-error
  color: #c62828
  font-size: 13px

.sr-foot
  margin-top: 14px
  display: flex
  flex-direction: column
  gap: 4px

.sr-reset
  min-height: 44px
  padding: 4px 16px
  width: fit-content
  border: 1px solid #ef9a9a
  color: #c62828
  background: #fff
  border-radius: 8px
  cursor: pointer
  &:disabled
    opacity: 0.45
    cursor: default

.sr-foot-note
  font-size: 12px
  color: #b0bec5
</style>
