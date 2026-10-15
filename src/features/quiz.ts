/**
 * 听辨练习流程（FR-606 / D-24）：
 * 播放题干 → 单选 → 立即判对（访客本地判对，answerIndex 随详情下发）；
 * 答错展示解释并可再答；每次作答记一次 listen_quiz 事件。
 */
import { computed, reactive } from 'vue'
import type { LevelDetail, QuizQuestion } from '@/api'
import { useProgressStore } from '@/stores/progress'

export interface QuizAnswerRecord {
  choiceIndex: number
  correct: boolean
}

export function useQuiz(level: LevelDetail, options: { interactive?: boolean } = {}) {
  const progress = useProgressStore()
  const interactive = options.interactive !== false

  /** questionId → 最近一次作答 */
  const answers = reactive(new Map<string, QuizAnswerRecord>())

  const total = computed(() => level.quiz.length)
  const passedIds = computed(() => {
    const passed = new Set<string>()
    for (const question of level.quiz) {
      const record = answers.get(question.id)
      if (record?.correct) passed.add(question.id)
    }
    return passed
  })

  function answer(question: QuizQuestion, choiceIndex: number): QuizAnswerRecord {
    const correct = choiceIndex === question.answerIndex
    const record: QuizAnswerRecord = { choiceIndex, correct }
    answers.set(question.id, record)
    if (interactive) {
      progress.recordQuizAnswer({
        levelId: level.id,
        questionId: question.id,
        choiceIndex,
        correct,
        contentVersion: level.contentVersion,
      })
    }
    return record
  }

  /** 供 LevelView 事件转发使用：按 questionId 定位题目后作答 */
  function answerById(payload: { questionId: string; choiceIndex: number; correct?: boolean }): void {
    const question = level.quiz.find((item) => item.id === payload.questionId)
    if (question) answer(question, payload.choiceIndex)
  }

  return { answers, total, passedIds, answer, answerById }
}
