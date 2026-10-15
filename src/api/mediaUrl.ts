/**
 * 媒体与音频地址拼装（全项目唯一出口）。
 * 预览态媒体一律改写为 /api/preview/media 并附带 token（FD-12 / #21）。
 */

export interface MediaUrlOptions {
  previewToken?: string
}

function withToken(url: string, token?: string): string {
  if (!token) return url
  return `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`
}

/** 公开内容媒体（图片/动画/视频/字幕/模型）唯一读取入口 */
export function mediaUrl(mediaId: string, options: MediaUrlOptions = {}): string {
  if (options.previewToken) {
    return withToken(`/api/preview/media/${encodeURIComponent(mediaId)}`, options.previewToken)
  }
  return `/api/media/${encodeURIComponent(mediaId)}`
}

/** 本人录音音频文件（回放 / 并排播放） */
export function audioFileUrl(audioId: string): string {
  return `/api/audio/${encodeURIComponent(audioId)}/file`
}

/** 本人录音原始 F0 序列（JSON） */
export function audioF0Url(audioId: string): string {
  return `/api/audio/${encodeURIComponent(audioId)}/f0`
}

/** 本人录音原始共振峰（JSON） */
export function audioFormantsUrl(audioId: string): string {
  return `/api/audio/${encodeURIComponent(audioId)}/formants`
}

/** 本人录音共振峰散点图片 */
export function audioFormantsPngUrl(audioId: string): string {
  return `/api/audio/${encodeURIComponent(audioId)}/formants.png`
}
