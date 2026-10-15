<script setup lang="ts">
/**
 * LevelView：关卡页纯展示组件（FR-601 统一结构，公开与预览共用，FD-12）。
 * 认知顺序：一句话结论 → 构形 → 示范 → 听辨 → 跟着练 → 误区 → 专业折叠。
 * 本关录音区与反馈由页面通过 slot 挂载（预览页不挂载 assessment / 反馈 / 学习事件）。
 */
import type { LevelDetail } from '@/api'
import ArticulationFigure from './ArticulationFigure.vue'
import DemoPlayer from '@/components/DemoPlayer.vue'
import QuizPanel from '@/components/QuizPanel.vue'
import PracticeStepper from '@/components/PracticeStepper.vue'
import MisconceptionList from '@/components/MisconceptionList.vue'
import ProFold from '@/components/ProFold.vue'

defineProps<{
  level: LevelDetail
  mediaResolver: (mediaId: string) => string
  /** 练习步骤完成集合（用于展示完成标记；预览传空集合） */
  practiceDoneIds: ReadonlySet<string>
  interactive?: boolean
}>()

const emit = defineEmits<{
  (e: 'quiz-answer', payload: { questionId: string; choiceIndex: number; correct: boolean }): void
  (e: 'practice-done', payload: { stepId: string }): void
  (e: 'practice-redo', payload: { stepId: string }): void
}>()
</script>

<template>
  <article class="level-view">
    <!-- 一句话结论（FR-602） -->
    <header class="level-header">
      <div class="level-identity">
        <span class="level-id">{{ level.id }}</span>
        <h1>{{ level.title }}</h1>
        <span class="level-pinyin">{{ level.pinyin }}</span>
        <span v-if="level.representativeChar" class="level-char">「{{ level.representativeChar }}」</span>
      </div>
      <p class="level-oneliner">{{ level.oneLiner }}</p>
      <p class="level-goal">这一关要学会：{{ level.goal }}</p>
    </header>

    <!-- 看得见的构形（FR-603） -->
    <section id="figure" class="level-section" aria-label="构形">
      <h2>看得见的构形</h2>
      <ArticulationFigure :articulation="level.articulation" :media-resolver="mediaResolver" />
      <p class="section-note">{{ level.articulation?.description }}</p>
    </section>

    <!-- 示范音（FR-604） -->
    <section id="demo" class="level-section" aria-label="示范">
      <h2>听示范</h2>
      <DemoPlayer :items="level.demos ?? []" :media-resolver="mediaResolver" />
    </section>

    <!-- 听辨（FR-606） -->
    <section id="quiz" class="level-section" aria-label="听辨练习">
      <h2>听辨练习</h2>
      <QuizPanel
        :questions="level.quizzes ?? []"
        :media-resolver="mediaResolver"
        :interactive="interactive"
        @answer="(payload) => emit('quiz-answer', { questionId: payload.question.id, choiceIndex: payload.choiceIndex, correct: payload.correct })"
      />
    </section>

    <!-- 跟着练（FR-605） -->
    <section id="practice" class="level-section" aria-label="跟着练">
      <h2>跟着练</h2>
      <PracticeStepper
        :steps="level.practice ?? []"
        :done-ids="practiceDoneIds"
        :media-resolver="mediaResolver"
        :interactive="interactive"
        @done="(step) => emit('practice-done', { stepId: step.id })"
        @redo="(step) => emit('practice-redo', { stepId: step.id })"
      />
    </section>

    <!-- 误区（FR-608） -->
    <section id="misconception" class="level-section" aria-label="常见误区">
      <h2>可能出现的误区</h2>
      <MisconceptionList :items="level.misconceptions ?? []" />
    </section>

    <!-- 本关录音（FR-609）：由页面挂载 assessment 区 -->
    <section v-if="$slots.assessment" id="record" class="level-section" aria-label="本关录音">
      <h2>录一录：检测这一关</h2>
      <slot name="assessment" />
    </section>

    <!-- 专业折叠（FR-610） -->
    <section class="level-section" aria-label="专业说明">
      <ProFold :pro="level.professional" />
    </section>
  </article>
</template>

<style scoped lang="sass">
.level-view
  max-width: 820px
  margin: 0 auto

.level-header
  margin-bottom: 20px

.level-identity
  display: flex
  align-items: baseline
  gap: 10px
  flex-wrap: wrap

.level-id
  font-size: 13px
  color: #fff
  background: #00897b
  border-radius: 6px
  padding: 2px 8px

.level-header h1
  font-size: 26px
  margin: 0

.level-pinyin, .level-char
  color: #607d8b
  font-size: 16px

.level-oneliner
  font-size: 18px
  color: #00695c
  font-weight: 600
  margin: 12px 0 4px

.level-goal
  color: #546e7a
  margin: 0

.level-section
  margin-top: 28px
  h2
    font-size: 19px
    margin: 0 0 12px
    border-left: 4px solid #4db6ac
    padding-left: 10px

.section-note
  font-size: 14px
  color: #546e7a
  margin-top: 10px
</style>
