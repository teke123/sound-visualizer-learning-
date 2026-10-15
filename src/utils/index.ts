/** 客户端 UUID：学习事件 eventId / 检测 submissionId 均在产生时生成，重试沿用 */
export function uuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // 兜底（旧 Safari）：RFC4122 v4
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/** localStorage 安全读写（隐私模式 / 配额异常时静默降级为内存态） */
const memoryFallback = new Map<string, string>()

export const safeStorage = {
  get(key: string): string | null {
    try {
      return window.localStorage.getItem(key)
    } catch {
      return memoryFallback.get(key) ?? null
    }
  },
  set(key: string, value: string): void {
    try {
      window.localStorage.setItem(key, value)
    } catch {
      memoryFallback.set(key, value)
    }
  },
  remove(key: string): void {
    try {
      window.localStorage.removeItem(key)
    } catch {
      memoryFallback.delete(key)
    }
  },
  /** 删除所有匹配前缀的键（清理旧代次账号数据） */
  removeByPrefix(prefix: string): void {
    try {
      const keys: string[] = []
      for (let i = 0; i < window.localStorage.length; i += 1) {
        const key = window.localStorage.key(i)
        if (key?.startsWith(prefix)) keys.push(key)
      }
      keys.forEach((key) => window.localStorage.removeItem(key))
    } catch {
      // 忽略：存储不可用时无本地数据可清理
    }
  },
}

/** 只接受站内路径（?redirect= 白名单校验） */
export function sanitizeRedirect(target: string | undefined | null): string | null {
  if (!target) return null
  if (!target.startsWith('/') || target.startsWith('//')) return null
  return target
}

export function formatDateTime(iso?: string): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', { hour12: false })
}

/** 距到期还剩多久（用于「临时保存，N 小时后到期」） */
export function formatRemaining(expiresAt?: string): string {
  if (!expiresAt) return ''
  const remain = new Date(expiresAt).getTime() - Date.now()
  if (Number.isNaN(remain) || remain <= 0) return '已到期'
  const hours = Math.floor(remain / 3_600_000)
  if (hours >= 1) return `约 ${hours} 小时后到期`
  const minutes = Math.max(1, Math.floor(remain / 60_000))
  return `约 ${minutes} 分钟后到期`
}
