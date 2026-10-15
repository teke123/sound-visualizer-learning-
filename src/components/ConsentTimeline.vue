<script setup lang="ts">
/** ConsentTimeline：同意决定历史（只追加，FR-102） */
import type { ConsentDecision } from '@/api'
import { formatDateTime } from '@/utils'

const DECISION_LABELS: Record<ConsentDecision['decision'], string> = {
  granted: '同意保存',
  rejected: '拒绝保存',
  revoked: '撤回同意',
}

defineProps<{ decisions: ConsentDecision[] }>()
</script>

<template>
  <section class="consent-timeline" aria-label="同意记录">
    <h3>同意记录</h3>
    <p v-if="decisions.length === 0" class="tl-empty">暂无记录（未做过同意决定）</p>
    <ol v-else class="tl-list">
      <li v-for="(decision, index) in decisions" :key="index" :class="`tl-item ${decision.decision}`">
        <span class="tl-dot" aria-hidden="true"></span>
        <span class="tl-label">{{ DECISION_LABELS[decision.decision] }}</span>
        <span class="tl-time">{{ formatDateTime(decision.createdAt) }}</span>
        <span class="tl-version">文案版本 {{ decision.consentTextVersion }}</span>
      </li>
    </ol>
  </section>
</template>

<style scoped lang="sass">
.consent-timeline
  h3
    margin: 0 0 8px
    font-size: 15px

.tl-empty
  color: #90a4ae
  font-size: 13px

.tl-list
  list-style: none
  margin: 0
  padding: 0

.tl-item
  display: flex
  align-items: center
  gap: 10px
  padding: 8px 0
  border-bottom: 1px dashed #eceff1
  font-size: 13px
  flex-wrap: wrap

.tl-dot
  width: 10px
  height: 10px
  border-radius: 50%
  background: #b0bec5

.tl-item.granted .tl-dot
  background: #66bb6a

.tl-item.rejected .tl-dot
  background: #ff8a65

.tl-item.revoked .tl-dot
  background: #ef5350

.tl-label
  font-weight: 600

.tl-time
  color: #90a4ae

.tl-version
  color: #b0bec5
  font-size: 12px
</style>
