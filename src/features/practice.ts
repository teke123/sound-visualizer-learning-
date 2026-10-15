/**
 * 跟着练流程（FR-605 / D-24）：每步可播放、暂停、重做、标记完成；
 * 标记按稳定步骤 ID 记一次 practice_done 事件。
 */
import { computed, ref } from 'vue'
import type { LevelDetail, PracticeStep } from '@/api'
import { useProgressStore } from '@/stores/progress'

export function usePractice(level: LevelDetail, options: { interactive?: boolean } = {}) {
  const progress = useProgressStore()
  const interactive = options.interactive !== false

  /** 会话内标记（与既有进度合并展示） */
  const sessionDone = ref(new Set<string>())

  const doneIds = computed(() => {
    const persisted = progress.entryOf(level.id).practiceDone
    return new Set([...persisted, ...sessionDone.value])
  })

  const allDone = computed(
    () => level.practice.length > 0 && level.practice.every((step) => doneIds.value.has(step.id)),
  )

  function markDone(step: PracticeStep) {
    if (!interactive || doneIds.value.has(step.id)) return
    sessionDone.value.add(step.id)
    sessionDone.value = new Set(sessionDone.value)
    progress.recordPracticeDone({
      levelId: level.id,
      stepId: step.id,
      contentVersion: level.contentVersion,
    })
  }

  /** 重做：清除本会话标记（事件不撤回；再次完成会再记一次） */
  function redo(step: PracticeStep) {
    sessionDone.value.delete(step.id)
    sessionDone.value = new Set(sessionDone.value)
  }

  /** 供 LevelView 事件转发使用 */
  function markDoneById(payload: { stepId: string }): void {
    const step = level.practice.find((item) => item.id === payload.stepId)
    if (step) markDone(step)
  }

  function redoById(payload: { stepId: string }): void {
    const step = level.practice.find((item) => item.id === payload.stepId)
    if (step) redo(step)
  }

  return { doneIds, allDone, markDone, redo, markDoneById, redoById }
}
