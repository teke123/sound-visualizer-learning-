<script setup lang="ts">
/** FourStepsList：规则四步反馈（FR-1007）：现象 → 可能相关环节 → 可感知提示 → 安全短练习（纯文本） */
import { QBadge } from 'quasar'
import type { FourStep } from '@/api'

defineProps<{ steps: FourStep[] }>()
</script>

<template>
  <section class="four-steps" aria-label="下一步怎么练">
    <h2>下一步怎么练</h2>
    <p v-if="steps.length === 0" class="fs-empty">没有需要改进的项；可以试试更难的关。</p>
    <ol v-else class="fs-list">
      <li v-for="(step, index) in steps" :key="index" class="fs-item">
        <div class="fs-row">
          <QBadge class="fs-tag">现象</QBadge>
          <p>{{ step.phenomenon }}</p>
        </div>
        <div class="fs-row">
          <QBadge class="fs-tag cause">可能相关</QBadge>
          <p>{{ step.possibleCause }}</p>
        </div>
        <div class="fs-row">
          <QBadge class="fs-tag cue">提示</QBadge>
          <p>{{ step.cue }}</p>
        </div>
        <div v-if="step.practice" class="fs-row practice">
          <QBadge class="fs-tag practice">短练习</QBadge>
          <p>{{ step.practice }}</p>
        </div>
      </li>
    </ol>
  </section>
</template>

<style scoped lang="sass">
.four-steps
  h2
    font-size: 18px
    margin: 0 0 10px

.fs-empty
  color: #546e7a

.fs-list
  list-style: none
  margin: 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 14px

.fs-item
  border: 1px solid #eceff1
  border-radius: 10px
  padding: 12px 14px
  display: flex
  flex-direction: column
  gap: 8px

.fs-row
  display: flex
  gap: 10px
  align-items: baseline
  p
    margin: 0
    font-size: 14px
    color: #37474f

/* 语义色块（现象/可能相关/提示/短练习）保留原配色，底色/圆角/字号基础形态交给 QBadge */
.fs-tag
  flex-shrink: 0
  align-self: baseline
  background: #eceff1
  color: #546e7a
  &.cause
    background: #fff3e0
    color: #8d5b00
  &.cue
    background: #e1f5fe
    color: #01579b
  &.practice
    background: #e0f2f1
    color: #00695c
</style>
