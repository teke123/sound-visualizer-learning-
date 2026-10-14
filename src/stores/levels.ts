/**
 * 关卡 store（重构占位）
 * ---------------------------------------------------------------------------
 * 意图：关卡 = CMS 已发布单元 + 分级开放规则：
 *  - 未发布 -> 未开放（不渲染检测入口、不出现分数）；
 *  - 已发布未开放检测(verified=false) -> 只学不测；
 *  - 已发布且开放检测 -> 才有「录音 -> 结果」闭环。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 关卡在大众端的可用状态 */
export type LevelAvailability = 'open' | 'learn_only' | 'unopened'

/** 关卡视图：内容服务数据 + 分级开放状态（字段随新契约定稿） */
export interface LevelView {
  code: string
  char: string
  availability: LevelAvailability
  /** 目标音（如 a / zh / mā），拼音展示用；由内容服务提供 */
  target?: string
  pinyin?: string
}

export const useLevelsStore = defineStore('levels', () => {
  const levels = ref<LevelView[]>([])
  const levelGroups = ref<Array<{ key: string; label: string; items: LevelView[] }>>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref('')

  async function fetchLevels(_force = false): Promise<void> {
    // TODO(重构): 从内容服务拉取关卡（CMS 已发布单元派生），维护 loading/error/loaded
  }
  return { levels, levelGroups, loading, loaded, error, fetchLevels }
})
