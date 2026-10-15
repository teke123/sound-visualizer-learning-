<script setup lang="ts">
/**
 * ConsentDialog：保存同意对话框（FR-102 / FD-07）。
 * 展示保存说明、将自动转存条数、本地进度不导入说明；同意 / 拒绝 / 暂不；
 * transfer 结果：completed「已保存 N 条」、partial「重试」、none 不提示。
 */
import { useConsent } from '@/features/consent'
import { errorCopy } from '@/copy/usePageCopy'

const consent = useConsent()
</script>

<template>
  <div v-if="consent.dialogOpen.value" class="consent-overlay" role="dialog" aria-modal="true" aria-label="保存同意">
    <div class="consent-dialog">
      <h2>保存你的进度和录音，需要你的同意</h2>

      <div class="consent-body">
        <h3>同意后会保存什么</h3>
        <ul>
          <li>你的学习进度（听辨与练习完成情况），从同意之后的记录开始</li>
          <li>你的录音与检测结果，自动保存到「声音档案」，可随时删除</li>
        </ul>

        <h3>自动转存本会话录音</h3>
        <p>
          同意后会自动保存当前会话中全部<b>未过期、未删除</b>的录音与结果
          <template v-if="consent.transferableCount.value != null">
            （本次共 <b>{{ consent.transferableCount.value }}</b> 条）
          </template>
          <template v-else-if="consent.loadingCount.value">（正在统计条数…）</template>
          ；当前会话未过期的临时音域标定也会一并升级为个人音域。
        </p>

        <h3>期限与删除</h3>
        <ul>
          <li>未保存的临时录音与结果，自首次上传起最多保留 72 小时，到期自动删除</li>
          <li>已保存的内容保留至你删除；撤回同意会删除全部录音、学习进度与音域</li>
        </ul>

        <p class="consent-local-note">
          ℹ️ 此前在本设备上记录的本地学习进度<b>不会导入账号</b>；同意后进度从服务端重新累计。
        </p>
      </div>

      <p v-if="consent.submitError.value" class="consent-error">{{ errorCopy(consent.submitError.value).title }}</p>

      <div class="consent-actions">
        <button type="button" class="consent-btn ghost" :disabled="consent.submitting.value" @click="consent.decide('deferred')">
          暂不
        </button>
        <button type="button" class="consent-btn" :disabled="consent.submitting.value" @click="consent.decide('rejected')">
          拒绝
        </button>
        <button type="button" class="consent-btn primary" :disabled="consent.submitting.value" @click="consent.decide('granted')">
          {{ consent.submitting.value ? '处理中…' : '同意并保存' }}
        </button>
      </div>
      <p class="consent-foot">拒绝后仍可查看当次结果；之后需要保存时可随时从档案页重新同意。</p>
    </div>
  </div>
</template>

<style scoped lang="sass">
.consent-overlay
  position: fixed
  inset: 0
  background: rgba(38, 50, 56, 0.55)
  display: flex
  align-items: center
  justify-content: center
  z-index: 200
  padding: 16px

.consent-dialog
  background: #fff
  border-radius: 16px
  width: min(560px, 96vw)
  max-height: 90vh
  overflow: auto
  padding: 22px

  h2
    margin: 0 0 12px
    font-size: 19px

.consent-body
  h3
    font-size: 14px
    margin: 14px 0 6px
    color: #00695c
  ul
    margin: 0
    padding-left: 18px
    font-size: 14px
    color: #455a64
    line-height: 1.9
  p
    font-size: 14px
    color: #455a64
    line-height: 1.9
    margin: 0

.consent-local-note
  margin-top: 12px
  background: #fff8e1
  border: 1px solid #ffe082
  border-radius: 8px
  padding: 8px 12px
  color: #5d4037

.consent-error
  color: #c62828
  font-size: 13px
  margin-top: 10px

.consent-actions
  display: flex
  gap: 10px
  margin-top: 18px

.consent-btn
  flex: 1
  min-height: 48px
  border-radius: 10px
  border: 1px solid #90a4ae
  background: #fff
  cursor: pointer
  font-size: 15px
  &.primary
    flex: 1.4
    background: #00897b
    border-color: #00897b
    color: #fff
    font-weight: 700
  &:disabled
    opacity: 0.6
    cursor: default

.consent-foot
  margin: 10px 0 0
  font-size: 12px
  color: #90a4ae
  text-align: center
</style>
