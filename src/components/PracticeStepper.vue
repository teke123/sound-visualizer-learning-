<script setup lang="ts">
/**
 * PracticeStepper：跟着练（FR-605）：每步可播放、暂停、重做、标记完成，
 * 显示次数或时长；步骤卡片锚点 #step-{stepId}。
 */
import type { PracticeStep } from '@/api'
import { usePlayerStore } from '@/stores/player'

const props = defineProps<{
  steps: PracticeStep[]
  doneIds: ReadonlySet<string>
  mediaResolver: (mediaId: string) => string
  interactive?: boolean
}>()

const emit = defineEmits<{
  (e: 'done', step: PracticeStep): void
  (e: 'redo', step: PracticeStep): void
}>()

const player = usePlayerStore()

function playStep(step: PracticeStep) {
  if (!step.mediaId) return
  void player.play({ key: `practice:${step.id}`, url: props.mediaResolver(step.mediaId), label: step.title })
}

function workload(step: PracticeStep): string {
  if (step.repeat) return `${step.repeat} 次`
  if (step.durationSec) return `${step.durationSec} 秒`
  return '若干次'
}
</script>

<template>
  <div class="practice-stepper">
    <p v-if="steps.length === 0" class="practice-empty">本关暂无练习步骤</p>
    <ol class="practice-list">
      <li
        v-for="(step, index) in steps"
        :id="`step-${step.id}`"
        :key="step.id"
        class="practice-step"
        :class="{ done: doneIds.has(step.id) }"
      >
        <div class="step-head">
          <span class="step-no">第 {{ index + 1 }} 步</span>
          <span class="step-title">{{ step.title }}</span>
          <span v-if="doneIds.has(step.id)" class="step-done-badge">已完成</span>
        </div>
        <p class="step-instruction">{{ step.instruction }}</p>
        <p class="step-meta">建议 {{ workload(step) }} · 身体感受：{{ step.bodyCue }}</p>
        <div class="step-actions">
          <button v-if="step.mediaId" type="button" class="step-btn" @click="playStep(step)">
            {{ player.isCurrent(`practice:${step.id}`) ? '暂停' : '播放' }}
          </button>
          <button
            v-if="interactive !== false && doneIds.has(step.id)"
            type="button"
            class="step-btn"
            @click="emit('redo', step)"
          >
            重做
          </button>
          <button
            v-if="interactive !== false"
            type="button"
            class="step-btn primary"
            :disabled="doneIds.has(step.id)"
            @click="emit('done', step)"
          >
            完成这一步
          </button>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped lang="sass">
.practice-empty
  color: #90a4ae

.practice-list
  list-style: none
  margin: 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 14px

.practice-step
  border: 1px solid #eceff1
  border-left: 4px solid #cfd8dc
  border-radius: 10px
  padding: 14px
  scroll-margin-top: 84px
  &.done
    border-left-color: #66bb6a

.step-head
  display: flex
  align-items: center
  gap: 10px
  flex-wrap: wrap

.step-no
  color: #78909c
  font-size: 13px

.step-title
  font-weight: 600

.step-done-badge
  font-size: 12px
  color: #2e7d32
  background: #e8f5e9
  border-radius: 999px
  padding: 2px 10px

.step-instruction
  margin: 8px 0 4px
  line-height: 1.7

.step-meta
  margin: 0
  font-size: 13px
  color: #00838f

.step-actions
  display: flex
  gap: 10px
  margin-top: 8px

.step-btn
  min-height: 44px
  padding: 4px 16px
  border-radius: 8px
  border: 1px solid #90a4ae
  background: #fff
  cursor: pointer
  &.primary
    border-color: #00897b
    background: #e0f2f1
    color: #00695c
    font-weight: 600
  &:disabled
    opacity: 0.55
    cursor: default
</style>
