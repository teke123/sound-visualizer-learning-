/**
 * 浏览器语音合成示意（重构占位）
 * ---------------------------------------------------------------------------
 * 意图：在 CMS 正式示范音缺失时，用浏览器 TTS 播示意音；
 * 页面必须挂 TTS_DISCLAIMER，绝不让合成音冒充正式授权示范音。
 * （具体实现待重构恢复。）
 */
export const TTS_DISCLAIMER = '系统语音合成示意，非正式授权示范音。正式示范将以授权发布的录音替换。'

export function useSpeechDemo() {
  // TODO(重构): 恢复 speak/stop（lang=zh-CN、normal/slow 两档语速）
  throw new Error('重构占位：浏览器 TTS 示范音')
}
