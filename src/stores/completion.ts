/**
 * 完成度派生规则（前端本地展示用，与服务端同一规则）：
 * 关卡完成 = 该账号在本关至少提交过一次录音检测。
 */

/**
 * nextLevelId = 公开顺序中第一个未完成的已开放关；
 * 全部完成或无进度时回落 L01；L01 未开放时回落第一已开放关（FR-205 / FD-02）。
 */
export function computeNextLevelId(
  published: { id: string; order: number }[],
  completed: (level: { id: string }) => boolean,
): string | null {
  const ordered = [...published].sort((a, b) => a.order - b.order)
  const next = ordered.find((level) => !completed(level))
  if (next) return next.id
  const fallback = ordered.find((level) => level.id === 'L01') ?? ordered[0]
  return fallback?.id ?? null
}
