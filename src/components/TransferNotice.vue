<script setup lang="ts">
/** TransferNotice：登录 / 同意触发的转存结果提示（§6.6：completed / partial / none） */
import { useConsent } from '@/features/consent'

const consent = useConsent()
</script>

<template>
  <div
    v-if="consent.transferNotice.value && consent.transferNotice.value.status !== 'none'"
    class="transfer-notice"
    role="status"
  >
    <span aria-hidden="true">{{ consent.transferNotice.value.status === 'completed' ? '✅' : '⚠️' }}</span>
    <p v-if="consent.transferNotice.value.status === 'completed'">
      已自动保存 {{ consent.transferNotice.value.transferredCount }} 条本会话录音与结果
      <template v-if="consent.transferNotice.value.calibrationUpgraded">；音域标定已升级为个人音域</template>。
    </p>
    <p v-else>
      有 {{ consent.transferNotice.value.transferredCount }} 条记录已保存，但转存未全部完成。
    </p>
    <button
      v-if="consent.transferNotice.value.status === 'partial'"
      type="button"
      class="notice-btn"
      :disabled="consent.submitting.value"
      @click="consent.retryTransfer()"
    >
      重试
    </button>
    <button type="button" class="notice-close" aria-label="关闭提示" @click="consent.dismissTransfer()">✕</button>
  </div>
</template>

<style scoped lang="sass">
.transfer-notice
  position: fixed
  top: 70px
  left: 50%
  transform: translateX(-50%)
  z-index: 150
  display: flex
  align-items: center
  gap: 10px
  background: #e8f5e9
  border: 1px solid #a5d6a7
  border-radius: 10px
  padding: 10px 14px
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08)
  max-width: min(560px, 92vw)
  p
    margin: 0
    font-size: 14px
    color: #1b5e20

.notice-btn
  min-height: 36px
  padding: 2px 14px
  border-radius: 8px
  border: 1px solid #2e7d32
  background: #fff
  color: #2e7d32
  cursor: pointer
  white-space: nowrap
  &:disabled
    opacity: 0.5

.notice-close
  min-width: 36px
  min-height: 36px
  border: none
  background: none
  color: #78909c
  cursor: pointer
</style>
