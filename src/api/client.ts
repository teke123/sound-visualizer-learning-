/**
 * fetch 客户端：envelope 解析、类型化错误、202 与 Retry-After
 * 全项目唯一的网络层；其他层只处理 ApiResult / ApiError。
 */
import type { Envelope } from './generated/types'

export const API_BASE = '/api'

/** 202 缺省轮询间隔 */
export const DEFAULT_RETRY_AFTER_MS = 2000

export interface ApiResult<T> {
  status: 200 | 202
  code: string
  data: T
  requestId: string
  nextStep?: string
  /** 202 / 429 / 503 SERVER_BUSY 附带；毫秒 */
  retryAfterMs?: number
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId?: string
  readonly nextStep?: string
  /** 毫秒；429 / 503 SERVER_BUSY / 202 场景 */
  readonly retryAfterMs?: number
  /** 409 冲突等场景下随错误带回的业务数据（如 {recordingId, retryable}） */
  readonly data?: unknown

  constructor(init: {
    status: number
    code: string
    message: string
    requestId?: string
    nextStep?: string
    retryAfterMs?: number
    data?: unknown
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.status = init.status
    this.code = init.code
    this.requestId = init.requestId
    this.nextStep = init.nextStep
    this.retryAfterMs = init.retryAfterMs
    this.data = init.data
  }
}

function parseRetryAfter(header: string | null): number | undefined {
  if (!header) return undefined
  const seconds = Number(header)
  if (Number.isFinite(seconds) && seconds >= 0) return Math.round(seconds * 1000)
  return undefined
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE' | 'PUT' | 'PATCH'
  body?: unknown
  formData?: FormData
  signal?: AbortSignal
}

/** 解析 JSON envelope；文件类响应（音频/图片）不经本函数 */
async function readEnvelope<T>(res: Response): Promise<ApiResult<T>> {
  let raw = ''
  try {
    raw = await res.text()
  } catch {
    throw new ApiError({ status: res.status, code: 'NETWORK', message: '读取响应失败' })
  }
  let parsed: Envelope<T> | undefined
  try {
    parsed = JSON.parse(raw) as Envelope<T>
  } catch {
    throw new ApiError({
      status: res.status,
      code: res.status >= 500 ? 'INTERNAL_ERROR' : 'VALIDATION_ERROR',
      message: '响应格式异常',
    })
  }
  if (!res.ok) {
    throw new ApiError({
      status: res.status,
      code: parsed.code ?? 'INTERNAL_ERROR',
      message: parsed.message ?? '请求失败',
      requestId: parsed.requestId,
      nextStep: parsed.nextStep,
      retryAfterMs: parseRetryAfter(res.headers.get('Retry-After')),
      data: parsed.data,
    })
  }
  const retryAfterMs =
    res.status === 202
      ? parseRetryAfter(res.headers.get('Retry-After')) ?? DEFAULT_RETRY_AFTER_MS
      : parseRetryAfter(res.headers.get('Retry-After'))
  return {
    status: res.status as 200 | 202,
    code: parsed.code ?? 'OK',
    data: parsed.data as T,
    requestId: parsed.requestId,
    nextStep: parsed.nextStep,
    retryAfterMs,
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
  const { method = 'GET', body, formData, signal } = options
  const init: RequestInit = {
    method,
    credentials: 'same-origin',
    signal,
  }
  if (formData) {
    init.body = formData
  } else if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, init)
  } catch (err) {
    if ((err as DOMException)?.name === 'AbortError') throw err
    throw new ApiError({
      status: 0,
      code: 'NETWORK',
      message: '网络连接失败，请检查网络后重试',
    })
  }
  return readEnvelope<T>(res)
}
