<script setup lang="ts">
/** ProFold：专业折叠（FR-610 / FD-13）：专业解释、声学参考值、来源与适用边界，默认收起 */
import { ref } from 'vue'
import type { ProFold as ProFoldData } from '@/api'

defineProps<{ pro: ProFoldData }>()
const expanded = ref(false)
</script>

<template>
  <div class="pro-fold">
    <button type="button" class="pro-toggle" :aria-expanded="expanded" @click="expanded = !expanded">
      {{ expanded ? '收起专业说明' : '展开专业说明（选看）' }}
      <span class="pro-arrow" aria-hidden="true">{{ expanded ? '▲' : '▼' }}</span>
    </button>
    <div v-if="expanded" class="pro-body">
      <div class="pro-content">{{ pro.content }}</div>
      <div v-if="pro.acousticNotes" class="pro-notes">
        <h4>声学参考值</h4>
        <p>{{ pro.acousticNotes }}</p>
      </div>
      <div v-if="pro.references?.length" class="pro-references">
        <h4>来源与适用边界</h4>
        <ul>
          <li v-for="reference in pro.references" :key="reference.title">
            {{ reference.title }} — {{ reference.source }}（许可：{{ reference.license }}；适用：{{ reference.scope }}）
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped lang="sass">
.pro-fold
  border: 1px dashed #cfd8dc
  border-radius: 10px
  padding: 10px 14px
  background: #fafafa

.pro-toggle
  width: 100%
  min-height: 44px
  display: flex
  justify-content: space-between
  align-items: center
  gap: 8px
  background: none
  border: none
  cursor: pointer
  font-size: 14px
  color: #546e7a

.pro-content
  white-space: pre-wrap
  line-height: 1.8
  color: #37474f

.pro-notes, .pro-references
  margin-top: 12px
  h4
    margin: 0 0 6px
    font-size: 14px
  p, li
    font-size: 13px
    color: #546e7a
  ul
    padding-left: 18px
</style>
