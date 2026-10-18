/** outbox 单测：入队去重、乐观合并视图、身份切换与清除（§6.5） */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { LearningEvent } from '@/api'
import { useOutboxStore } from '../outbox'

/** node 环境下的 localStorage stub（同键覆盖语义） */
function stubLocalStorage() {
  const map = new Map<string, string>()
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => map.set(key, value),
    removeItem: (key: string) => map.delete(key),
    clear: () => map.clear(),
    key: (index: number) => [...map.keys()][index] ?? null,
    get length() {
      return map.size
    },
    __map: map,
  }
}

function quizEvent(eventId: string, levelId = 'L01', questionId = 'q1'): LearningEvent {
  return { eventId, levelId, kind: 'listen_quiz', detail: { questionId, choiceIndex: 0 } }
}

function practiceEvent(eventId: string, levelId = 'L01', stepId = 's1'): LearningEvent {
  return { eventId, levelId, kind: 'practice_done', detail: { stepId } }
}

describe('outbox store', () => {
  let storage: ReturnType<typeof stubLocalStorage>

  beforeEach(() => {
    storage = stubLocalStorage()
    vi.stubGlobal('localStorage', storage)
    vi.stubGlobal('window', { localStorage: storage })
    setActivePinia(createPinia())
  })

  it('按 eventId 去重：同一事件不重复入队（重试沿用同一 eventId）', () => {
    const outbox = useOutboxStore()
    outbox.bind('a1')
    outbox.enqueue(quizEvent('e1'))
    outbox.enqueue(quizEvent('e1'))
    expect(outbox.events).toHaveLength(1)
    expect(outbox.pendingCount).toBe(1)
  })

  it('乐观合并视图：listen_quiz → quizPassed，practice_done → practiceDone', () => {
    const outbox = useOutboxStore()
    outbox.bind('a1')
    outbox.enqueue(quizEvent('e1', 'L01', 'q1'))
    outbox.enqueue(practiceEvent('e2', 'L01', 's1'))
    const overlay = outbox.overlay.get('L01')!
    expect(overlay.quizPassed.has('q1')).toBe(true)
    expect(overlay.practiceDone.has('s1')).toBe(true)
  })

  it('身份切换重新加载对应账号队列；clear 清除并落盘删除', () => {
    const outbox = useOutboxStore()
    outbox.bind('a1')
    outbox.enqueue(quizEvent('e1'))
    expect(localStorage.getItem('vv.outbox.a1')).toBeTruthy()

    outbox.bind('a2')
    expect(outbox.events).toHaveLength(0)

    outbox.bind('a1')
    expect(outbox.events.map((e) => e.eventId)).toEqual(['e1'])

    outbox.clear()
    expect(outbox.events).toHaveLength(0)
    expect(localStorage.getItem('vv.outbox.a1')).toBeNull()
  })
})
