/**
 * 用户 store（重构占位）
 * ---------------------------------------------------------------------------
 * 意图：
 *  - 用户身份（重构时接真实账号体系，替换 default_user）；
 *  - 学习记录与进度的读取（进度为后端派生的只读数据，前端不维护、不覆写）；
 *  - addLearningRecord：录音 + 检测结果快照 multipart 落库，成功后刷新记录与进度。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  // TODO(重构): 按上述意图恢复会话/同意状态、进度与记录读取
  const userId = ref('default_user')
  const error = ref('')
  return { userId, error }
})
