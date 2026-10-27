/**
 * 听辨练习流程（FR-606）：播放题干 → 单选 → 立即判对（answerIndex 随详情下发）；
 * 答错展示解释并可再答。
 */
import { computed, reactive } from 'vue'
import type { LevelDetail, QuizQuestion } from '@/api'

export interface QuizAnswerRecord {
  choiceIndex: number
  correct: boolean
}

export function useQuiz(level: LevelDetail, options: { interactive?: boolean } = {}) {
  const interactive = options.interactive !== false

  /** questionId → 最近一次作答（仅会话内状态） */
  const answers = reactive(new Map<string, QuizAnswerRecord>())
  // 草稿预览等场景可能缺 quizzes，按空处理
  const quizzes = level.quizzes ?? []

  const total = computed(() => quizzes.length)
  const passedIds = computed(() => {
    const passed = new Set<string>()
    for (const question of quizzes) {
      const record = answers.get(question.id)
      if (record?.correct) passed.add(question.id)
    }
    return passed
  })

  function answer(question: QuizQuestion, choiceIndex: number): QuizAnswerRecord {
    const correct = choiceIndex === question.answerIndex
    const record: QuizAnswerRecord = { choiceIndex, correct }
    if (interactive) {
      answers.set(question.id, record)
    }
    return record
  }

  /** 供视图层事件转发使用：按 questionId 定位题目后作答 */
  function answerById(payload: { questionId: string; choiceIndex: number; correct?: boolean }): void {
    const question = quizzes.find((item) => item.id === payload.questionId)
    if (question) answer(question, payload.choiceIndex)
  }

  return { answers, total, passedIds, answer, answerById }
}
