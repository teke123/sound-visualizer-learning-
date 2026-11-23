<script setup lang="ts">
/** FourStepsList：规则四步反馈（FR-1007）：现象 → 可能相关环节 → 可感知提示 → 安全短练习（纯文本） */
import type { FourStep } from '@/api'

defineProps<{ steps: FourStep[] }>()
</script>

<template>
  <section class="four-steps vs-card" aria-label="下一步怎么练">
    <h3>下一步怎么练</h3>
    <p v-if="steps.length === 0" class="fs-empty">没有需要改进的项；可以试试更难的关。</p>
    <ol v-else class="fs-list">
      <li v-for="(step, index) in steps" :key="index" class="fs-item">
        <div class="fs-row">
          <span class="vs-tag fs-tag">现象</span>
          <p>{{ step.phenomenon }}</p>
        </div>
        <div class="fs-row">
          <span class="vs-tag fs-tag cause">可能相关</span>
          <p>{{ step.possibleCause }}</p>
        </div>
        <div class="fs-row">
          <span class="vs-tag fs-tag cue">提示</span>
          <p>{{ step.cue }}</p>
        </div>
        <div v-if="step.practice" class="fs-row">
          <span class="vs-tag fs-tag practice">短练习</span>
          <p>{{ step.practice }}</p>
        </div>
      </li>
    </ol>
  </section>
</template>

<style scoped lang="sass">
.four-steps
  padding: 24px

.four-steps h3
  font-size: 20px
  font-weight: 900
  letter-spacing: -0.3px
  margin: 0 0 8px

.fs-empty
  color: var(--vs-sub)
  font-size: 13.5px
  margin: 0

.fs-list
  list-style: none
  margin: 8px 0 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 12px

.fs-item
  border-top: 1px solid var(--vs-line)
  padding-top: 12px
  display: flex
  flex-direction: column
  gap: 8px

.fs-item:first-child
  border-top: none
  padding-top: 0

.fs-row
  display: flex
  gap: 10px
  align-items: baseline
  p
    margin: 0
    font-size: 13.5px
    color: var(--vs-ink2)
    line-height: 1.7

.fs-tag
  flex: none
  align-self: baseline

.fs-tag.cause
  background: var(--vs-amber-soft)
  color: var(--vs-amber-ink)

.fs-tag.cue
  background: var(--vs-brand-soft)
  color: var(--vs-brand-d)

.fs-tag.practice
  background: var(--vs-soft)
  color: var(--vs-coffee)
</style>
