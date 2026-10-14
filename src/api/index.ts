/**
 * API 层（重构占位骨架）
 * ---------------------------------------------------------------------------
 * 意图：
 *  - request()：统一网络封装（baseURL 经环境变量注入 / FormData 边界 / 错误口径），
 *    全项目只允许这一条网络层；错误口径必须保留后端中文 message，不得压成「服务器错误」；
 *  - 发音单元内容只走 CMS（/api/admin/units/*，管理端）与 /api/units（大众端只读）。
 *
 * 端点意图登记（重构时按组恢复）：
 *  - 学习档案：GET/DELETE 学习记录、POST /learning-records（multipart 录音+检测结果快照）、录音流；
 *  - 进度：GET /users/:id/progress（只读派生，无覆写入口）；
 *  - 后台：/admin/feedback（反馈处理）；
 *  - 媒体：/media/upload、/media/:id/file；
 *  - 分析：/api/asr/diagnose（诊断）、/api/audio/features（声学特征）——契约重构后接入。
 */

// 意图：重构后经 import.meta.env.VITE_API_BASE 注入，不再硬编码 localhost
export const API_BASE_URL = '/api'

export class ApiNotImplementedError extends Error {
  constructor(intent: string) {
    super(`重构占位（未实现）：${intent}`)
  }
}

// CMS 发音单元（唯一的内容管理入口；大众端只读列表将来也挂在本组）
export const unitsApi = {
  /** 管理端：按状态列出单元（draft/published/unpublished，SRS 附录 C 三态） */
  async list(_status = ''): Promise<never> {
    throw new ApiNotImplementedError('CMS 单元列表')
  },
  /** 管理端：单元详情（含治理字段：发布状态 / 检测开关 / 版本） */
  async getById(_id: string): Promise<never> {
    throw new ApiNotImplementedError('CMS 单元详情')
  },
  /** 管理端：录入单元（录入即草稿） */
  async create(_data: unknown): Promise<never> {
    throw new ApiNotImplementedError('CMS 录入单元')
  },
  /** 管理端：编辑单元（仅草稿/已下架） */
  async update(_id: string, _data: unknown): Promise<never> {
    throw new ApiNotImplementedError('CMS 编辑单元')
  },
  /** 管理端：删除单元（核心单元受保护） */
  async delete(_id: string): Promise<never> {
    throw new ApiNotImplementedError('CMS 删除单元')
  },
}

// 页面反馈（PageFeedback 组件依赖；后端 POST /api/feedback 为 501 占位）
export const feedbackApi = {
  async submit(_payload: {
    userId: string
    type: string
    page: string
    unitId?: string
    rating?: string
    message?: string
  }): Promise<never> {
    throw new ApiNotImplementedError('提交页面反馈')
  },
}
