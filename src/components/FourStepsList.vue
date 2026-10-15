<script setup lang="ts">
/** FourStepsList：规则四步反馈（FR-1007）：现象 → 可能相关环节 → 可感知提示 → 安全短练习（可跳回关卡练习） */
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
          <span class="fs-tag">现象</span>
          <p>{{ step.phenomenon }}</p>
        </div>
        <div class="fs-row">
          <span class="fs-tag cause">可能相关</span>
          <p>{{ step.possibleCause }}</p>
        </div>
        <div class="fs-row">
          <span class="fs-tag cue">提示</span>
          <p>{{ step.cue }}</p>
        </div>
        <div class="fs-row practice">
          <span class="fs-tag practice">短练习</span>
          <div>
            <RouterLink
              v-if="step.practice.levelId"
              :to="`/learn/${step.practice.levelId}#step-${step.practice.stepRef}`"
              class="fs-link"
            >
              跟着练：{{ step.practice.stepRef }} →
            </RouterLink>
          </div>
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

.fs-tag
  flex-shrink: 0
  font-size: 12px
  background: #eceff1
  color: #546e7a
  border-radius: 4px
  padding: 2px 8px
  &.cause
    background: #fff3e0
    color: #8d5b00
  &.cue
    background: #e1f5fe
    color: #01579b
  &.practice
    background: #e0f2f1
    color: #00695c

.fs-link
  color: #00897b
  font-weight: 600
  text-decoration: none
  &:hover
    text-decoration: underline
</style>
