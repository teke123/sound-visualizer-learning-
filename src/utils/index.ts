/** 客户端 UUID：学习事件 eventId / 检测 submissionId 均在产生时生成，重试沿用 */
export function uuid(): string {
  return crypto.randomUUID()
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

