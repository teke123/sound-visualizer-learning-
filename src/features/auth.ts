/**
 * 账号流程：注册、登录、退出、注销（FR-102–108）。
 * 注册 / 登录即默认同意服务条款；登录响应携带替换后的 context；
 * 退出 / 注销按身份切换表清除本地数据。
 */
import { ref } from 'vue'
import { identityApi } from '@/api'
import { useContextStore } from '@/stores/context'
import { useProgressStore } from '@/stores/progress'
import { useRecorderStore } from '@/stores/recorder'

export const USERNAME_PATTERN = /^[\w\u4e00-\u9fa5]{3,32}$/
export const PASSWORD_MIN_LENGTH = 8

/** 方言区/母语背景选项（FR-107）：代码与后端 DIALECT_CODES 对齐，用于
 * 针对性提示（FR-1007）与后续分组统计；纯选填 */
export const DIALECT_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'mandarin_north', label: '北方官话' },
  { value: 'mandarin_southwest', label: '西南官话（川渝）' },
  { value: 'wu', label: '吴语' },
  { value: 'yue', label: '粤语' },
  { value: 'min', label: '闽语' },
  { value: 'xiang', label: '湘语' },
  { value: 'gan', label: '赣语' },
  { value: 'hakka', label: '客家话' },
  { value: 'english', label: '英语（母语）' },
  { value: 'japanese', label: '日语（母语）' },
  { value: 'korean', label: '韩语（母语）' },
  { value: 'other', label: '其他' },
]

export function dialectLabel(code?: string | null): string {
  return DIALECT_OPTIONS.find((option) => option.value === code)?.label ?? code ?? ''
}

/** 性别选项（FR-107）：代码与后端 GENDER_CODES 对齐，用于音高参考与
 * 后续分组统计；纯选填 */
export const GENDER_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'male', label: '男' },
  { value: 'female', label: '女' },
  { value: 'other', label: '其他 / 不便透露' },
]

export function genderLabel(code?: string | null): string {
  return GENDER_OPTIONS.find((option) => option.value === code)?.label ?? code ?? ''
}

export function validateUsername(username: string): string | null {
  if (!USERNAME_PATTERN.test(username)) {
    return '用户名需 3–32 个字符，可用字母、数字、下划线或中文'
  }
  return null
}

export function validatePassword(password: string): string | null {
  if (password.length < PASSWORD_MIN_LENGTH) return '密码至少 8 位'
  return null
}

export function useAuth() {
  const contextStore = useContextStore()
  const progressStore = useProgressStore()
  const recorder = useRecorderStore()

  const busy = ref(false)
  const error = ref<unknown>(null)

  async function register(payload: {
    username: string
    password: string
    dialectBackground?: string | null
    gender?: string | null
  }): Promise<boolean> {
    busy.value = true
    error.value = null
    try {
      // 注册不自动登录（后端契约）
      await identityApi.register(payload)
      return true
    } catch (err) {
      error.value = err
      return false
    } finally {
      busy.value = false
    }
  }

  /** 设置/修改方言区背景与性别（FR-107）：全量覆盖，成功后刷新 context 使其随身份下发 */
  async function updateProfile(payload: {
    dialectBackground: string | null
    gender: string | null
  }): Promise<boolean> {
    busy.value = true
    error.value = null
    try {
      await identityApi.updateProfile(payload)
      await contextStore.refresh()
      return true
    } catch (err) {
      error.value = err
      return false
    } finally {
      busy.value = false
    }
  }

  /** 登录：成功后用响应 context 替换并拉取全量（标定 / 进度） */
  async function login(payload: { username: string; password: string }): Promise<boolean> {
    busy.value = true
    error.value = null
    try {
      const res = await identityApi.login(payload)
      // 登录成功：清除上一账号内存状态，替换 context。
      // 后端 login 响应只携带部分身份字段（authenticated/accountId/username），
      // 先合并避免 context 出现空洞，再拉取全量。
      progressStore.onLogout()
      recorder.release()
      contextStore.apply({ ...contextStore.context, ...res.data.context })
      await contextStore.refresh()
      progressStore.onIdentityEstablished()
      return true
    } catch (err) {
      error.value = err
      return false
    } finally {
      busy.value = false
    }
  }

  /** 退出：清除账号内存状态；重新拉 context */
  async function logout(): Promise<void> {
    busy.value = true
    try {
      await identityApi.logout()
    } catch {
      // 会话已失效也按退出处理
    } finally {
      busy.value = false
    }
    recorder.release()
    progressStore.onLogout()
    await contextStore.refresh()
  }

  /** 注销：清空该账号全部数据；全部会话失效；注销后回到首页 */
  async function deleteAccount(password: string): Promise<boolean> {
    busy.value = true
    error.value = null
    try {
      await identityApi.deleteAccount({ password })
      return true
    } catch (err) {
      error.value = err
      return false
    } finally {
      busy.value = false
    }
  }

  function finishAccountDeletion() {
    recorder.release()
    progressStore.onAccountErased()
    void contextStore.refresh()
  }

  return { busy, error, register, updateProfile, login, logout, deleteAccount, finishAccountDeletion }
}
