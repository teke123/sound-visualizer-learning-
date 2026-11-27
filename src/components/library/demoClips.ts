/**
 * 发音示范素材表与地址拼装。
 *
 * 素材先走静态目录，路径约定见《3D发音动画清单》：
 *   public/media/teacher/{音素}/{音素}_{视角}.mp4
 *   public/media/teacher/{音素}/{音素}_{视角}.jpg   （首帧封面，可选）
 *
 * 将来若改走后端媒体（/api/media/{id}），只改 teacherVideoUrl / teacherPosterUrl 两个函数，
 * 组件不用动。
 */

export interface DemoClip {
  /** 拼音键，同时是目录名（ü 直接写 ü） */
  key: string
  /** 音标 */
  ipa: string
  /** 分组：单韵母 / 声母 */
  group: 'vowel' | 'initial'
  /** 是否需要侧面机位（舌位类音必须） */
  side: boolean
}

export const DEMO_CLIPS: DemoClip[] = [
  { key: 'a', ipa: 'a', group: 'vowel', side: true },
  { key: 'o', ipa: 'o', group: 'vowel', side: true },
  { key: 'e', ipa: 'ɤ', group: 'vowel', side: true },
  { key: 'i', ipa: 'i', group: 'vowel', side: true },
  { key: 'u', ipa: 'u', group: 'vowel', side: true },
  { key: 'ü', ipa: 'y', group: 'vowel', side: true },
  { key: 'b', ipa: 'p', group: 'initial', side: false },
  { key: 'p', ipa: 'pʰ', group: 'initial', side: false },
  { key: 'm', ipa: 'm', group: 'initial', side: false },
  { key: 'f', ipa: 'f', group: 'initial', side: true },
  { key: 'd', ipa: 't', group: 'initial', side: true },
  { key: 't', ipa: 'tʰ', group: 'initial', side: true },
  { key: 'n', ipa: 'n', group: 'initial', side: true },
  { key: 'l', ipa: 'l', group: 'initial', side: true },
  { key: 'g', ipa: 'k', group: 'initial', side: true },
  { key: 'k', ipa: 'kʰ', group: 'initial', side: true },
  { key: 'h', ipa: 'x', group: 'initial', side: true },
  { key: 'j', ipa: 'tɕ', group: 'initial', side: true },
  { key: 'q', ipa: 'tɕʰ', group: 'initial', side: true },
  { key: 'x', ipa: 'ɕ', group: 'initial', side: true },
  { key: 'zh', ipa: 'ʈʂ', group: 'initial', side: true },
  { key: 'ch', ipa: 'ʈʂʰ', group: 'initial', side: true },
  { key: 'sh', ipa: 'ʂ', group: 'initial', side: true },
  { key: 'r', ipa: 'ɻ', group: 'initial', side: true },
  { key: 'z', ipa: 'ts', group: 'initial', side: true },
  { key: 'c', ipa: 'tsʰ', group: 'initial', side: true },
  { key: 's', ipa: 's', group: 'initial', side: true },
  { key: 'y', ipa: 'j', group: 'initial', side: false },
  { key: 'w', ipa: 'w', group: 'initial', side: false },
]


/** 每个音的一句发音要点（展示在示范旁边） */
export const TIPS: Record<string, string> = {
  'a': '下颌打开，气息冲开嘴，声音最响',
  'o': '双唇收圆，舌后缩，半开口',
  'e': '嘴角微展，舌后中高，半开口',
  'i': '嘴角拉开，舌前高，上下齿靠近',
  'u': '双唇收圆前突，舌后高',
  'ü': '唇形同 u，但舌位靠前',
  'b': '双唇紧闭后弹开，气流弱',
  'p': '同 b，弹开时强送气',
  'm': '双唇闭合，气流走鼻腔',
  'f': '上齿轻咬下唇，气流摩擦',
  'd': '舌尖抵上齿龈后弹开，气流弱',
  't': '同 d，弹开时强送气',
  'n': '舌尖抵齿龈，气流走鼻腔',
  'l': '舌尖抵齿龈，气流走舌两侧',
  'g': '舌根抵软腭后弹开，气流弱',
  'k': '同 g，弹开时强送气',
  'h': '舌根靠近软腭，气流摩擦',
  'j': '舌面前抵硬腭前部，放开摩擦',
  'q': '同 j，放开时强送气',
  'x': '舌面前接近硬腭，气流摩擦',
  'zh': '舌尖上卷抵硬腭前部，不送气',
  'ch': '同 zh，放开时强送气',
  'sh': '舌尖上卷接近硬腭，气流摩擦',
  'r': '部位同 sh，浊音、舌尖不颤',
  'z': '舌尖抵上齿龈，塞擦不送气',
  'c': '同 z，放开时强送气',
  's': '舌尖接近下齿背，气流摩擦',
  'y': '同 i 的起头：展唇、舌前高',
  'w': '同 u 的起头：圆唇前突',
}

export const CLIP_BY_KEY: ReadonlyMap<string, DemoClip> = new Map(
  DEMO_CLIPS.map((c) => [c.key, c]),
)

export type DemoView = 'front' | 'side'

/** 示范视频地址（阶段一：静态目录） */
export function teacherVideoUrl(key: string, view: DemoView): string {
  const k = encodeURIComponent(key)
  return `/media/teacher/${k}/${k}_${view}.mp4`
}

/** 首帧封面地址（可选；没有封面时视频会自己出首帧） */
export function teacherPosterUrl(key: string, view: DemoView): string {
  const k = encodeURIComponent(key)
  return `/media/teacher/${k}/${k}_${view}.jpg`
}

/** 该音需要展示的机位 */
export function viewsOf(clip: DemoClip): DemoView[] {
  return clip.side ? ['front', 'side'] : ['front']
}
