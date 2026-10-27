/**
 * levels store 关卡详情缓存与加载策略（§6.9）：
 * 默认缓存优先（比较面板 / 结果页专业说明复用），force 强制刷新（关卡页先缓存展示随后刷新），
 * 失败不破坏已有缓存。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { LevelDetail } from '@/api'

const { levelMock } = vi.hoisted(() => ({ levelMock: vi.fn() }))

vi.mock('@/api', () => ({
  contentApi: {
    levels: vi.fn(),
    level: levelMock,
  },
}))

import { useLevelsStore } from '../levels'

const detail = (id: string, title: string) => ({ id, title }) as LevelDetail

describe('levels store：关卡详情缓存与加载', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    levelMock.mockReset()
  })

  it('默认缓存优先：首次请求网络并写入缓存，二次命中不再请求', async () => {
    levelMock.mockResolvedValueOnce({ data: detail('L01', '第一关') })
    const store = useLevelsStore()

    const first = await store.loadLevelDetail('L01')
    expect(levelMock).toHaveBeenCalledTimes(1)
    expect(store.getCachedDetail('L01')).toBe(first)

    const second = await store.loadLevelDetail('L01')
    expect(levelMock).toHaveBeenCalledTimes(1)
    expect(second).toBe(first)
  })

  it('force = true：绕过缓存请求网络并覆盖缓存（关卡页进入刷新）', async () => {
    const store = useLevelsStore()
    const stale = detail('L02', '旧标题')
    store.setCachedDetail('L02', stale)
    const fresh = detail('L02', '新标题')
    levelMock.mockResolvedValueOnce({ data: fresh })

    const got = await store.loadLevelDetail('L02', { force: true })
    expect(got).toBe(fresh)
    expect(store.getCachedDetail('L02')).toBe(fresh)
  })

  it('force 请求失败：向上抛错且不破坏已有缓存（关卡页 404 → 不可见态）', async () => {
    const store = useLevelsStore()
    store.setCachedDetail('L03', detail('L03', '缓存标题'))
    levelMock.mockRejectedValueOnce(new Error('网络错误'))

    await expect(store.loadLevelDetail('L03', { force: true })).rejects.toThrow('网络错误')
    expect(store.getCachedDetail('L03')?.title).toBe('缓存标题')
  })

  it('未缓存时 getCachedDetail 返回 undefined（不发请求）', () => {
    const store = useLevelsStore()
    expect(store.getCachedDetail('L404')).toBeUndefined()
    expect(levelMock).not.toHaveBeenCalled()
  })
})
