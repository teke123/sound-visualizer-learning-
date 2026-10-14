/**
 * 示范音播放（重构占位）
 * ---------------------------------------------------------------------------
 * 意图（播放优先级，恢复实现时保持）：
 *   1) CMS 已发布的正式示范音（unit.demoAudio）-> 播真实音频，不显示合成声明；
 *   2) 缺失 -> 回落浏览器语音合成（useSpeechDemo），标记 source='tts'，
 *      页面据此挂 TTS_DISCLAIMER。
 */
export type DemoSource = 'demo-audio' | 'tts'

export function useDemoPlayer() {
  // TODO(重构): 恢复 play(text, audioUrl?, slow?) / stop()，按上述优先级切换音源
  throw new Error('重构占位：示范音播放')
}
