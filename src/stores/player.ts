/**
 * player store：全局唯一音频播放（示范、题干、回放、比较共用）。
 * 任意播放请求会停止上一个；≤2 秒开始播放或给出失败原因（NFR-02）。
 * 音频 preload="none"，点击后加载（§9）。
 */
import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'

const START_TIMEOUT_MS = 4000

export type PlayerState = 'idle' | 'loading' | 'playing' | 'paused' | 'ended' | 'error'

export interface PlayerSource {
  /** 播放源标识（如 mediaId / audioId / 本地 blob 标记），同一源再次点击视为暂停切换 */
  key: string
  url: string
  label?: string
}

export const usePlayerStore = defineStore('player', () => {
  const current = shallowRef<PlayerSource | null>(null)
  const state = ref<PlayerState>('idle')
  const errorMessage = ref<string | null>(null)

  let audio: HTMLAudioElement | null = null
  let loadingTimer: number | null = null

  const isCurrent = computed(
    () => (key: string) => current.value?.key === key && (state.value === 'playing' || state.value === 'loading'),
  )
  const playing = computed(() => state.value === 'playing')

  function ensureAudio(): HTMLAudioElement {
    if (!audio) {
      audio = new Audio()
      audio.preload = 'none'
      audio.addEventListener('playing', () => {
        clearLoadingTimer()
        state.value = 'playing'
      })
      audio.addEventListener('pause', () => {
        if (state.value === 'playing') state.value = 'paused'
      })
      audio.addEventListener('ended', () => {
        state.value = 'ended'
      })
      audio.addEventListener('error', () => {
        clearLoadingTimer()
        state.value = 'error'
        errorMessage.value = '音频加载失败，请稍后重试'
      })
    }
    return audio
  }

  function clearLoadingTimer() {
    if (loadingTimer !== null) window.clearTimeout(loadingTimer)
    loadingTimer = null
  }

  /** 播放：同一源再点 = 暂停；不同源先停上一个（iOS：播放在用户手势内发起） */
  async function play(source: PlayerSource): Promise<void> {
    const el = ensureAudio()
    if (current.value?.key === source.key && !el.paused) {
      el.pause()
      return
    }
    clearLoadingTimer()
    errorMessage.value = null
    current.value = source
    state.value = 'loading'
    el.src = source.url
    el.load()
    loadingTimer = window.setTimeout(() => {
      if (state.value === 'loading') {
        state.value = 'error'
        errorMessage.value = '音频开始播放超时，请检查网络后重试'
        el.pause()
      }
    }, START_TIMEOUT_MS)
    try {
      await el.play()
    } catch {
      clearLoadingTimer()
      if ((state.value as PlayerState) !== 'error') {
        state.value = 'error'
        errorMessage.value = '无法开始播放，请重试'
      }
    }
  }

  function stop() {
    if (!audio) return
    clearLoadingTimer()
    audio.pause()
    audio.removeAttribute('src')
    state.value = 'idle'
    current.value = null
    errorMessage.value = null
  }

  return { current, state, errorMessage, playing, isCurrent, play, stop }
})
