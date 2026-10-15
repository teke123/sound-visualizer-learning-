/**
 * D-24 完成度判定（纯函数，前端本地与服务端同一规则）：
 * 本关当前公开版本的全部听辨题各至少答对一次，
 * 且全部练习步骤各至少标记完成一次；录音不计入。
 */
import type { CompletionKeys, LevelSummary, MeProgress } from '@/api'

export interface LevelProgressState {
  quizPassed: ReadonlySet<string>
  practiceDone: ReadonlySet<string>
}

export function isLevelCompleted(
  keys: CompletionKeys,
  quizPassed: ReadonlySet<string>,
  practiceDone: ReadonlySet<string>,
): boolean {
  return keys.quizIds.every((id) => quizPassed.has(id)) && keys.practiceStepIds.every((id) => practiceDone.has(id))
}

/**
 * nextLevelId = 公开顺序中第一个未完成的已发布关；
 * 全部完成或无进度时回落 L01；L01 未发布时回落第一已发布关（FR-205 / FD-02）。
 */
export function computeNextLevelId(
  published: LevelSummary[],
  completed: (level: LevelSummary) => boolean,
): string | null {
  const ordered = [...published].sort((a, b) => a.order - b.order)
  const next = ordered.find((level) => !completed(level))
  if (next) return next.id
  const fallback = ordered.find((level) => level.id === 'L01') ?? ordered[0]
  return fallback?.id ?? null
}

/** 服务端 me/progress → 快速查询表 */
export function progressIndex(progress: MeProgress): Map<string, boolean> {
  return new Map(progress.levels.map((item) => [item.levelId, item.completed]))
}
