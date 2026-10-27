<script setup lang="ts">
/**
 * QuizPanel：听辨练习（FR-606）：听题干 → 单选 → 立即判对；
 * 答错展示解释并可再答。模块暂不在关卡页展示，保留待后续启用（作答不计入完成度）。
 */
import { reactive } from 'vue'
import { QBtn, QCard, QCardSection } from 'quasar'
import type { QuizQuestion } from '@/api'
import { usePlayerStore } from '@/stores/player'

const props = defineProps<{
  questions: QuizQuestion[]
  mediaResolver: (mediaId: string) => string
  /** false = 预览：可播放但不作答 */
  interactive?: boolean
}>()

const emit = defineEmits<{
  (e: 'answer', payload: { question: QuizQuestion; choiceIndex: number; correct: boolean }): void
}>()

const player = usePlayerStore()
const answers = reactive(new Map<string, { choiceIndex: number; correct: boolean }>())

function playStimulus(question: QuizQuestion) {
  void player.play({ key: `quiz:${question.id}`, url: props.mediaResolver(question.stimulusMediaId), label: '题干' })
}

function playOption(questionId: string, mediaId: string) {
  void player.play({ key: `quiz-opt:${questionId}:${mediaId}`, url: props.mediaResolver(mediaId), label: '选项' })
}

function choose(question: QuizQuestion, choiceIndex: number) {
  if (props.interactive === false) return
  const correct = choiceIndex === question.answerIndex
  answers.set(question.id, { choiceIndex, correct })
  emit('answer', { question, choiceIndex, correct })
}

/** 选项按钮呈现态（纯展示）：未答/未选 = 描边；判分后正确项 positive、所选错误项 negative 实心 */
function optionVisual(question: QuizQuestion, index: number): { filled: boolean; color: 'primary' | 'positive' | 'negative' } {
  const answer = answers.get(question.id)
  if (!answer) return { filled: false, color: 'primary' }
  if (index === question.answerIndex) return { filled: true, color: 'positive' }
  if (answer.choiceIndex === index && !answer.correct) return { filled: true, color: 'negative' }
  return { filled: false, color: 'primary' }
}
</script>

<template>
  <div class="quiz-panel">
    <p v-if="questions.length === 0" class="quiz-empty">本关暂无听辨题</p>
    <QCard v-for="(question, qIndex) in questions" :key="question.id" flat bordered class="quiz-item">
      <QCardSection>
        <div class="quiz-head">
          <span class="quiz-no">第 {{ qIndex + 1 }} 题</span>
          <QBtn outline no-caps rounded color="primary" class="quiz-stimulus" @click="playStimulus(question)">
            <span aria-hidden="true">▶</span> 播放题干音频
          </QBtn>
          <span class="quiz-prompt">{{ question.prompt }}</span>
        </div>
        <div class="quiz-options" role="radiogroup" :aria-label="question.prompt">
          <QBtn
            v-for="(option, index) in question.options"
            :key="index"
            role="radio"
            :aria-checked="answers.get(question.id)?.choiceIndex === index"
            no-caps
            class="quiz-option"
            :color="optionVisual(question, index).color"
            :unelevated="optionVisual(question, index).filled"
            :outline="!optionVisual(question, index).filled"
            :disable="interactive === false"
            @click="choose(question, index)"
          >
            <span class="quiz-option-text">{{ option.text }}</span>
            <span
              v-if="option.mediaId"
              class="quiz-option-play"
              role="button"
              tabindex="0"
              aria-label="播放选项音频"
              @click.stop="playOption(question.id, option.mediaId!)"
              @keydown.enter.prevent="playOption(question.id, option.mediaId!)"
            >
              ▶
            </span>
          </QBtn>
        </div>
        <p
          v-if="answers.get(question.id) && !answers.get(question.id)?.correct"
          class="quiz-explain"
        >
          不对哦，再听一遍选选看。{{ question.explanation ?? '' }}
        </p>
        <p v-else-if="answers.get(question.id)?.correct" class="quiz-explain ok">答对了！</p>
      </QCardSection>
    </QCard>
  </div>
</template>

<style scoped lang="sass">
.quiz-panel
  display: flex
  flex-direction: column
  gap: 20px

.quiz-empty
  color: #90a4ae

.quiz-head
  display: flex
  align-items: center
  gap: 10px
  flex-wrap: wrap

.quiz-no
  font-weight: 600
  color: #37474f

.quiz-stimulus
  min-height: 40px

.quiz-prompt
  color: #546e7a
  font-size: 14px

.quiz-options
  display: flex
  flex-wrap: wrap
  gap: 10px
  margin-top: 10px

.quiz-option
  min-height: 44px
  padding: 6px 16px
  font-size: 15px

.quiz-option-play
  color: #0288d1
  font-size: 13px

.quiz-explain
  margin: 10px 0 0
  font-size: 14px
  color: #c62828
  &.ok
    color: #2e7d32
</style>
