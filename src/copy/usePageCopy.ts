/**
 * 文案集中地：
 * 页面状态文案、错误码 → 文案与下一步动作的映射只有这一处；
 * 现象、四步等内容文案来自后端，不在前端改写。
 */
import { ApiError } from '@/api'

export interface PageStateCopy {
  loading: string
  empty: string
  error: string
  forbidden: string
  notVisible: string
}

export const PAGE_STATE_COPY: PageStateCopy = {
  loading: '正在加载…',
  empty: '这里还没有内容',
  error: '加载失败，请稍后重试',
  forbidden: '当前身份无法查看这部分内容',
  /** 统一不可见状态：不存在、未开放、已删除或已过期 */
  notVisible: '内容不存在或暂不可见',
}

export interface ErrorCopy {
  title: string
  /** 下一步能做什么（NFR 防错反馈：错误提示包含下一步） */
  hint: string
}

const NETWORK_COPY: ErrorCopy = {
  title: '网络连接失败',
  hint: '请检查网络后重试；你的录音仍保留在页面上，可直接重试。',
}

/** 错误码 / 状态码 → 文案与下一步动作 */
const CODE_COPY: Record<string, ErrorCopy> = {
  NETWORK: NETWORK_COPY,
  QUALITY_FAIL: {
    title: '录音质量提示',
    hint: '检测到本次录音环境不理想，可按提示改善后重录；本次评分与结果不受影响。',
  },
  CALIBRATION_FAIL: {
    title: '这次标定没有成功',
    hint: '请按提示在安静处、用平常说话的音量再朗读一遍标定文本；也可以跳过标定直接录音。',
  },
  PROCESSING: { title: '正在处理', hint: '评分仍在进行，稍后自动查询结果。' },
  DECODE_FAILED: { title: '没录上', hint: '这次录音无法读取，请重新录制后再提交。' },
  AUTH_REQUIRED: { title: '需要登录', hint: '请先登录后再进行此操作。' },
  INVALID_CREDENTIALS: { title: '用户名或密码不正确', hint: '本站不提供密码找回；忘记密码只能重新注册。' },
  FORBIDDEN: { title: '没有权限', hint: '当前身份无法执行此操作，请确认登录账号后重试。' },
  NOT_FOUND: { title: PAGE_STATE_COPY.notVisible, hint: '内容可能已删除、下架或过期。' },
  LEVEL_NOT_PUBLISHED: {
    title: '这一关暂时不可见',
    hint: '内容可能已下架或尚未开放；页面会自动刷新关卡列表。',
  },
  CONTENT_VERSION_CHANGED: {
    title: '关卡内容已更新',
    hint: '本关内容刚刚更新，请刷新任务后按新内容重录。',
  },
  IDEMPOTENCY_CONFLICT: {
    title: '提交记录冲突',
    hint: '检测到重复提交，已为你生成新的提交标识，请重新提交一次。',
  },
  USERNAME_TAKEN: { title: '用户名已被使用', hint: '请换一个用户名。' },
  FILE_TOO_LARGE: { title: '录音过长', hint: '录音超出大小限制，请缩短时长重新录制。' },
  RATE_LIMITED: { title: '操作太频繁', hint: '请稍等片刻再试。' },
  PROVIDER_ERROR: { title: '评分服务异常', hint: '本次评分未完成，可重试。' },
  PROVIDER_DOWN: { title: '评分服务暂不可用', hint: '本次评分未完成，可稍后重试。' },
  SERVER_BUSY: { title: '当前排队较多', hint: '请按提示的等待时间稍后重试。' },
  TIMEOUT: { title: '处理超时', hint: '在当前页面可直接重试本次提交；离开后请重新录音。' },
  INTERNAL_ERROR: { title: '服务开小差了', hint: '请重试；若持续失败请通过页面下方反馈告诉我们。' },
  VALIDATION_ERROR: { title: '请求有误', hint: '请检查输入后重试。' },
  CSRF_FAILED: { title: '请求来源校验失败', hint: '请刷新页面后重试。' },
}

const STATUS_COPY: Record<number, ErrorCopy> = {
  400: CODE_COPY.DECODE_FAILED!,
  401: CODE_COPY.AUTH_REQUIRED!,
  403: CODE_COPY.FORBIDDEN!,
  404: CODE_COPY.NOT_FOUND!,
  409: { title: '状态冲突', hint: '当前状态不支持此操作，请刷新页面后重试。' },
  413: CODE_COPY.FILE_TOO_LARGE!,
  429: CODE_COPY.RATE_LIMITED!,
  500: CODE_COPY.INTERNAL_ERROR!,
  502: CODE_COPY.PROVIDER_ERROR!,
  503: { title: '服务暂不可用', hint: '请稍后重试。' },
  504: CODE_COPY.TIMEOUT!,
}

/** 错误 → 文案；错误码优先，其次状态码，兜底通用错误 */
export function errorCopy(error: unknown): ErrorCopy {
  if (!(error instanceof ApiError)) {
    return { title: '出了点问题', hint: '请重试；若持续失败请通过页面下方反馈告诉我们。' }
  }
  const byCode = CODE_COPY[error.code]
  if (byCode) {
    if (error.retryAfterMs && error.retryAfterMs > 0) {
      const seconds = Math.max(1, Math.round(error.retryAfterMs / 1000))
      return { ...byCode, hint: `${byCode.hint}（约 ${seconds} 秒后可重试）` }
    }
    return byCode
  }
  return STATUS_COPY[error.status] ?? CODE_COPY.INTERNAL_ERROR!
}

/** requestId 展示（NFR-19 可追溯） */
export function requestIdOf(error: unknown): string | undefined {
  return error instanceof ApiError ? error.requestId : undefined
}

/** 页面级状态文案 + 错误映射（composable 形态，保持与文档命名一致） */
export function usePageCopy() {
  return {
    state: PAGE_STATE_COPY,
    errorCopy,
    requestIdOf,
  }
}
