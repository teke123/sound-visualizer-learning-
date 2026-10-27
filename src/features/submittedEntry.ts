/**
 * 提交流程 → 结果查询的内存交接（FD-15：跨页面只提供重新录音）。
 * 提交流程（assessment）提交成功后写入，结果查询（result）读取做同键重试；
 * 刷新 / 直接打开结果页后为 null（只提供重新录音）。
 * 纯内存模块：不依赖路由与任何 store，也无持久化，语义即「最近一次成功提交」。
 */
export interface SubmittedEntry {
  recordingId: string
  submissionId: string
  audioId: string
  levelId: string
}

let submittedEntry: SubmittedEntry | null = null

export function setSubmittedEntry(entry: SubmittedEntry | null) {
  submittedEntry = entry
}

export function getSubmittedEntry(): SubmittedEntry | null {
  return submittedEntry
}
