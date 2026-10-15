<script setup lang="ts">
/**
 * SaveStatusBanner：保存状态横幅（P09）：
 * session → 临时保存 + 到期时间 + 登录/同意入口；archived → 已保存到档案。
 */
import { computed } from 'vue'
import type { StorageKind } from '@/api'
import { useContextStore } from '@/stores/context'
import { useConsent } from '@/features/consent'
import { formatDateTime, formatRemaining } from '@/utils'

const props = defineProps<{
  storage: StorageKind
  expiresAt?: string
}>()

const contextStore = useContextStore()
const consent = useConsent()

const isSession = computed(() => props.storage === 'session')
</script>

<template>
  <aside v-if="isSession" class="save-banner session" aria-label="保存状态">
    <div class="banner-text">
      <p class="banner-title">🔒 临时保存</p>
      <p class="banner-sub">
        本次结果只在本会话可见{{ expiresAt ? `，${formatRemaining(expiresAt)}（${formatDateTime(expiresAt)}）` : '' }}，到期后不可恢复。
      </p>
      <p class="banner-sub">登录并同意保存后，会自动把本会话全部未过期录音与结果转存到你的档案。</p>
    </div>
    <div class="banner-actions">
      <RouterLink v-if="!contextStore.isAuthenticated" to="/account/login?redirect=/archive" class="banner-btn">
        登录
      </RouterLink>
      <button
        v-if="consent.consentEntryAvailable.value"
        type="button"
        class="banner-btn"
        @click="consent.openDialog()"
      >
        同意保存
      </button>
    </div>
  </aside>
  <aside v-else class="save-banner archived" aria-label="保存状态">
    <p class="banner-title">✅ 已自动保存到声音档案</p>
    <p class="banner-sub">可在「声音档案」中回看、删除，或与之前的记录比较。</p>
    <RouterLink to="/archive" class="banner-link">去档案看看 →</RouterLink>
  </aside>
</template>

<style scoped lang="sass">
.save-banner
  display: flex
  gap: 14px
  align-items: center
  justify-content: space-between
  flex-wrap: wrap
  border-radius: 10px
  padding: 12px 16px

  &.session
    background: #e3f2fd
    border: 1px solid #90caf9

  &.archived
    background: #e8f5e9
    border: 1px solid #a5d6a7

.banner-text
  flex: 1
  min-width: 220px

.banner-title
  margin: 0
  font-weight: 700
  font-size: 14px

.banner-sub
  margin: 4px 0 0
  font-size: 13px
  color: #37474f

.banner-actions
  display: flex
  gap: 10px

.banner-btn
  min-height: 44px
  display: inline-flex
  align-items: center
  padding: 4px 18px
  border-radius: 999px
  background: #1565c0
  color: #fff
  text-decoration: none
  font-weight: 600
  border: none
  cursor: pointer

.banner-link
  color: #2e7d32
  font-size: 14px
  font-weight: 600
</style>
