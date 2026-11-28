<script setup lang="ts">
/**
 * FeedbackScriptCard：P09 四步话术卡（验收项 AC01）。
 * 结构固定为「① 现象 → ② 可能环节 → ③ 可感知提示 → ④ 安全短练习」，
 * 与后端 FourStep 的 phenomenon / possibleCause / cue / practice 一一对应；
 * wordingSource 标明这段文字来自规则模板还是大模型改写——大模型只改写法，字段不变。
 * 本卡是静态版：规则话术直接可用；大模型改写的话术接入后只换文本，不改结构与字段。
 */
import { computed } from 'vue'
import type { FourStep } from '@/api'

const props = defineProps<{
  /** 本次结论对应的四步话术（后端 fourSteps；为空表示本次没有需要改写的现象） */
  steps: FourStep[]
  /** 覆盖来源徽标文案（缺省按 wordingSource 判定） */
  sourceLabel?: string
  /** 卡片下方的说明条：回落说明、占位说明等 */
  notice?: string
  headingLevel?: 'h2' | 'h3'
}>()

const FIELDS: Array<{
  key: 'phenomenon' | 'possibleCause' | 'cue' | 'practice'
  index: string
  label: string
}> = [
  { key: 'phenomenon', index: '①', label: '现象' },
  { key: 'possibleCause', index: '②', label: '可能环节' },
  { key: 'cue', index: '③', label: '可感知提示' },
  { key: 'practice', index: '④', label: '安全短练习' },
]

const SOURCE_LABELS: Record<string, string> = {
  rule_template: '规则模板',
  llm: '大模型改写',
}

const badge = computed(() => {
  if (props.sourceLabel) return props.sourceLabel
  const sources = new Set(props.steps.map((step) => step.wordingSource))
  if (sources.size === 0) return '规则模板'
  if (sources.size === 1) {
    const only = sources.values().next().value ?? ''
    return SOURCE_LABELS[only] ?? only
  }
  return '混合来源'
})
</script>

<template>
  <section class="script-card vs-card" aria-label="四步话术">
    <header class="script-head">
      <component :is="headingLevel ?? 'h2'">四步话术</component>
      <span class="script-badge">{{ badge }}</span>
    </header>

    <p class="script-intro">
      按四步给出：先说你听到了什么，再指可能相关的环节，给一个当场能感觉到的提示，最后是一个安全的短练习。
    </p>

    <p v-if="!steps.length" class="script-empty">
      本次没有检出需要改写的现象，四步话术为空；换一关或再录一次会重新给结论。
    </p>

    <ol v-else class="script-list">
      <li v-for="(step, index) in steps" :key="index" class="script-item">
        <p class="script-index">第 {{ index + 1 }} 条</p>
        <div v-for="field in FIELDS" :key="field.key" class="script-row">
          <span class="script-label">{{ field.index }} {{ field.label }}</span>
          <p class="script-text">{{ step[field.key] || '（这一项本次没有内容）' }}</p>
        </div>
      </li>
    </ol>

    <p v-if="notice" class="script-notice">{{ notice }}</p>
  </section>
</template>

<style scoped lang="sass">
.script-card
  padding: 20px

.script-head
  display: flex
  align-items: baseline
  gap: 10px
  flex-wrap: wrap
  h2, h3
    margin: 0
    font-weight: 900
    letter-spacing: -0.3px
  h2
    font-size: 20px
  h3
    font-size: 17px

.script-badge
  flex: none
  font-size: 12px
  font-weight: 700
  padding: 3px 8px
  border-radius: 999px
  background: var(--vs-brand-soft)
  color: var(--vs-brand-d)

.script-intro
  margin: 8px 0 0
  font-size: 13px
  color: var(--vs-sub)
  line-height: 1.7

.script-empty
  margin: 12px 0 0
  font-size: 13.5px
  color: var(--vs-sub)

.script-list
  list-style: none
  margin: 12px 0 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 14px

.script-item
  border-top: 1px solid var(--vs-line)
  padding-top: 12px

.script-item:first-child
  border-top: none
  padding-top: 0

.script-index
  margin: 0 0 6px
  font-size: 12.5px
  font-weight: 700
  color: var(--vs-mute)

.script-row
  display: flex
  gap: 10px
  align-items: baseline
  margin-bottom: 6px

.script-row:last-child
  margin-bottom: 0

.script-label
  flex: none
  width: 6.6em
  font-size: 13px
  font-weight: 700
  color: var(--vs-ink)

.script-text
  margin: 0
  font-size: 13.5px
  color: var(--vs-ink2)
  line-height: 1.7

.script-notice
  margin: 12px 0 0
  padding: 8px 12px
  border-radius: 8px
  background: var(--vs-soft)
  color: var(--vs-coffee)
  font-size: 12.5px
  line-height: 1.6
</style>
