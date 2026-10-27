/**
 * 现代汉语（普通话）音系数据模块：发音库四张表、关卡语音学定位与
 * 易混组过滤的统一数据源（docs/发音库与关卡页重构方案_修订版.md §5.2）。
 *
 * 数据按现代语音学通用框架组织（《汉语拼音方案》拼写 + IPA 严式标音）：
 * - 辅音（声母）：6 发音方法行 × 7 被动发音部位列，21 个起始辅音
 *   + 仅作韵尾的 ŋ + 零声母拼写 y/w/ɥ（半元音）；
 * - 元音/韵母：介音类型（Ø-/j-/w-/ɥ-，对应传统四呼）× 韵尾类型（-Ø/-i̯/-u̯/-n/-ŋ），
 *   38 键（舌尖 -i 一键两音 z̩/ʐ̩，共 39 个音位条目）；
 * - 音节表：合法普通话音节拼写映射（《汉语拼音方案》省写规则已应用）；
 * - 声调、元音舌位（含音位变体分组）、易混组；以及关卡 → 音系单元格的自动匹配函数
 *   （关卡填写 phonology 段时优先消费，否则按 layer/targetSound/pinyin 兜底，§5.1）。
 */
import type { LevelPhonology } from '@/api'

/* ------------------------------ 辅音矩阵 ------------------------------ */

export type Aspiration = 'aspirated' | 'unaspirated' | 'none'
export type Voicing = 'voiceless' | 'voiced'

/** 发音部位（列，被动部位命名，按口腔前 → 后排序） */
export const INITIAL_PLACES = [
  '双唇',
  '唇齿',
  '齿龈',
  '卷舌',
  '龈腭',
  '硬腭',
  '软腭',
] as const

/** 发音部位英文（表头副标） */
export const INITIAL_PLACE_EN: Record<string, string> = {
  双唇: 'Bilabial',
  唇齿: 'Labiodental',
  齿龈: 'Alveolar',
  卷舌: 'Retroflex',
  龈腭: 'Alveolo-palatal',
  硬腭: 'Palatal',
  软腭: 'Velar',
}

/** 发音方法（行，按气流阻碍程度由大到小排列；传统「舌尖前/舌尖中」并入齿龈、「舌面」定名龈腭、「舌根」定名软腭） */
export interface MannerRow {
  key: string
  label: string
  en: string
}

export const MANNER_ROWS: MannerRow[] = [
  { key: 'stop', label: '塞音', en: 'Plosive' },
  { key: 'affricate', label: '塞擦音', en: 'Affricate' },
  { key: 'fricative', label: '擦音', en: 'Fricative' },
  { key: 'nasal', label: '鼻音', en: 'Nasal' },
  { key: 'approximant', label: '近音', en: 'Approximant' },
  { key: 'lateral', label: '边近音', en: 'Lateral' },
]

export interface InitialInfo {
  /** 拼音键（zh/ch/sh 为双字母；y/w/ɥ 为零声母拼写条目） */
  key: string
  ipa: string
  /** 代表字 */
  char: string
  place: string
  rowKey: string
  manner: string
  voicing: Voicing
  aspiration: Aspiration
  /** 零声母拼写（y = j- 介音拼写，w = w- 介音拼写，yu = ɥ- 介音拼写） */
  zeroSpelling?: 'y' | 'w' | 'yu'
  /** 仅作韵尾，不作音节起始（软腭鼻音 ŋ） */
  codaOnly?: boolean
}

export const INITIALS: InitialInfo[] = [
  // 塞音（清；格内左不送气、右送气）
  { key: 'b', ipa: 'p', char: '波', place: '双唇', rowKey: 'stop', manner: '塞音', voicing: 'voiceless', aspiration: 'unaspirated' },
  { key: 'p', ipa: 'pʰ', char: '坡', place: '双唇', rowKey: 'stop', manner: '塞音', voicing: 'voiceless', aspiration: 'aspirated' },
  { key: 'd', ipa: 't', char: '得', place: '齿龈', rowKey: 'stop', manner: '塞音', voicing: 'voiceless', aspiration: 'unaspirated' },
  { key: 't', ipa: 'tʰ', char: '特', place: '齿龈', rowKey: 'stop', manner: '塞音', voicing: 'voiceless', aspiration: 'aspirated' },
  { key: 'g', ipa: 'k', char: '哥', place: '软腭', rowKey: 'stop', manner: '塞音', voicing: 'voiceless', aspiration: 'unaspirated' },
  { key: 'k', ipa: 'kʰ', char: '科', place: '软腭', rowKey: 'stop', manner: '塞音', voicing: 'voiceless', aspiration: 'aspirated' },
  // 塞擦音（清；格内左不送气、右送气）
  { key: 'z', ipa: 'ts', char: '资', place: '齿龈', rowKey: 'affricate', manner: '塞擦音', voicing: 'voiceless', aspiration: 'unaspirated' },
  { key: 'c', ipa: 'tsʰ', char: '雌', place: '齿龈', rowKey: 'affricate', manner: '塞擦音', voicing: 'voiceless', aspiration: 'aspirated' },
  { key: 'zh', ipa: 'ʈʂ', char: '知', place: '卷舌', rowKey: 'affricate', manner: '塞擦音', voicing: 'voiceless', aspiration: 'unaspirated' },
  { key: 'ch', ipa: 'ʈʂʰ', char: '痴', place: '卷舌', rowKey: 'affricate', manner: '塞擦音', voicing: 'voiceless', aspiration: 'aspirated' },
  { key: 'j', ipa: 'tɕ', char: '基', place: '龈腭', rowKey: 'affricate', manner: '塞擦音', voicing: 'voiceless', aspiration: 'unaspirated' },
  { key: 'q', ipa: 'tɕʰ', char: '欺', place: '龈腭', rowKey: 'affricate', manner: '塞擦音', voicing: 'voiceless', aspiration: 'aspirated' },
  // 擦音（清）
  { key: 'f', ipa: 'f', char: '佛', place: '唇齿', rowKey: 'fricative', manner: '擦音', voicing: 'voiceless', aspiration: 'none' },
  { key: 's', ipa: 's', char: '思', place: '齿龈', rowKey: 'fricative', manner: '擦音', voicing: 'voiceless', aspiration: 'none' },
  { key: 'sh', ipa: 'ʂ', char: '诗', place: '卷舌', rowKey: 'fricative', manner: '擦音', voicing: 'voiceless', aspiration: 'none' },
  { key: 'x', ipa: 'ɕ', char: '希', place: '龈腭', rowKey: 'fricative', manner: '擦音', voicing: 'voiceless', aspiration: 'none' },
  { key: 'h', ipa: 'x', char: '喝', place: '软腭', rowKey: 'fricative', manner: '擦音', voicing: 'voiceless', aspiration: 'none' },
  // 鼻音（浊）
  { key: 'm', ipa: 'm', char: '摸', place: '双唇', rowKey: 'nasal', manner: '鼻音', voicing: 'voiced', aspiration: 'none' },
  { key: 'n', ipa: 'n', char: '呐', place: '齿龈', rowKey: 'nasal', manner: '鼻音', voicing: 'voiced', aspiration: 'none' },
  { key: 'ŋ', ipa: 'ŋ', char: '昂', place: '软腭', rowKey: 'nasal', manner: '鼻音', voicing: 'voiced', aspiration: 'none', codaOnly: true },
  // 近音（浊；y/w/ɥ 为零声母拼写）
  { key: 'r', ipa: 'ɻ', char: '日', place: '卷舌', rowKey: 'approximant', manner: '近音', voicing: 'voiced', aspiration: 'none' },
  { key: 'y', ipa: 'j', char: '衣', place: '硬腭', rowKey: 'approximant', manner: '近音', voicing: 'voiced', aspiration: 'none', zeroSpelling: 'y' },
  { key: 'ɥ', ipa: 'ɥ', char: '迂', place: '硬腭', rowKey: 'approximant', manner: '近音', voicing: 'voiced', aspiration: 'none', zeroSpelling: 'yu' },
  { key: 'w', ipa: 'w', char: '乌', place: '软腭', rowKey: 'approximant', manner: '近音', voicing: 'voiced', aspiration: 'none', zeroSpelling: 'w' },
  // 边近音（浊）
  { key: 'l', ipa: 'l', char: '勒', place: '齿龈', rowKey: 'lateral', manner: '边近音', voicing: 'voiced', aspiration: 'none' },
]

export const INITIAL_BY_KEY: ReadonlyMap<string, InitialInfo> = new Map(INITIALS.map((i) => [i.key, i]))

/* ------------------------------ 韵母矩阵 ------------------------------ */

/** 介音类型（键值与后端 phonology.hu 契约一致；对应传统四呼） */
export type Hu = 'kaikou' | 'qichi' | 'hekou' | 'cuokou'
export type FinalStructure = 'special' | 'simple' | 'compound' | 'front_nasal' | 'back_nasal'

/** 介音类型标签（列：G-V-X 韵母结构的介音维度，括注传统四呼对应） */
export const HU_LABELS: Record<Hu, string> = {
  kaikou: 'Ø- 无介音',
  qichi: 'j- 硬腭介音',
  hekou: 'w- 唇软腭介音',
  cuokou: 'ɥ- 唇硬腭介音',
}

export const HU_ORDER: Hu[] = ['kaikou', 'qichi', 'hekou', 'cuokou']

/** 韵尾类型行（FinalMatrix 行序；G-V-X 韵母结构的韵尾维度，替代传统前/中/后响与前后鼻） */
export interface FinalRow {
  key: string
  label: string
  /** 韵尾标记（行首显示） */
  coda: string
}

export const FINAL_ROWS: FinalRow[] = [
  { key: 'open_mono', label: '开音节 · 单元音', coda: '-Ø' },
  { key: 'rising', label: '开音节 · 后响双元音', coda: 'G+V' },
  { key: 'i_coda', label: '前滑音韵尾', coda: '-i̯' },
  { key: 'u_coda', label: '后滑音韵尾', coda: '-u̯' },
  { key: 'n_coda', label: '齿龈鼻音韵尾', coda: '-n' },
  { key: 'ng_coda', label: '软腭鼻音韵尾', coda: '-ŋ' },
]

export interface FinalInfo {
  /** 拼音键（舌尖 -i 一键两音：apicalVariant 区分 z̩/ʐ̩） */
  key: string
  ipa: string
  char: string
  hu: Hu
  rowKey: string
  structure: FinalStructure
  /** 书写省写提示，如 iou → iu */
  spelling?: string
  /** 舌尖 -i 的两读：front = z̩（z/c/s 后）、back = ʐ̩（zh/ch/sh/r 后） */
  apicalVariant?: 'front' | 'back'
  /** 是否能与其他声母相拼（ê/er 仅自成音节） */
  combineable: boolean
}

export const FINAL_CELLS: FinalInfo[] = [
  // Ø- 无介音（开口呼）
  { key: '-i', ipa: 'z̩', char: '资', hu: 'kaikou', rowKey: 'open_mono', structure: 'special', apicalVariant: 'front', combineable: true },
  { key: '-i', ipa: 'ʐ̩', char: '知', hu: 'kaikou', rowKey: 'open_mono', structure: 'special', apicalVariant: 'back', combineable: true },
  { key: 'a', ipa: 'ä', char: '啊', hu: 'kaikou', rowKey: 'open_mono', structure: 'simple', combineable: true },
  { key: 'o', ipa: 'o', char: '喔', hu: 'kaikou', rowKey: 'open_mono', structure: 'simple', combineable: true },
  { key: 'e', ipa: 'ɤ', char: '鹅', hu: 'kaikou', rowKey: 'open_mono', structure: 'simple', combineable: true },
  { key: 'ê', ipa: 'ɛ', char: '欸', hu: 'kaikou', rowKey: 'open_mono', structure: 'simple', combineable: false },
  { key: 'er', ipa: 'ɚ', char: '儿', hu: 'kaikou', rowKey: 'open_mono', structure: 'special', combineable: false },
  { key: 'ai', ipa: 'ai̯', char: '哀', hu: 'kaikou', rowKey: 'i_coda', structure: 'compound', combineable: true },
  { key: 'ei', ipa: 'ei̯', char: '诶', hu: 'kaikou', rowKey: 'i_coda', structure: 'compound', combineable: true },
  { key: 'ao', ipa: 'ɑu̯', char: '熬', hu: 'kaikou', rowKey: 'u_coda', structure: 'compound', combineable: true },
  { key: 'ou', ipa: 'ou̯', char: '欧', hu: 'kaikou', rowKey: 'u_coda', structure: 'compound', combineable: true },
  { key: 'an', ipa: 'an', char: '安', hu: 'kaikou', rowKey: 'n_coda', structure: 'front_nasal', combineable: true },
  { key: 'en', ipa: 'ən', char: '恩', hu: 'kaikou', rowKey: 'n_coda', structure: 'front_nasal', combineable: true },
  { key: 'ang', ipa: 'ɑŋ', char: '昂', hu: 'kaikou', rowKey: 'ng_coda', structure: 'back_nasal', combineable: true },
  { key: 'eng', ipa: 'əŋ', char: '鞥', hu: 'kaikou', rowKey: 'ng_coda', structure: 'back_nasal', combineable: true },
  // j- 硬腭介音（齐齿呼）
  { key: 'i', ipa: 'i', char: '衣', hu: 'qichi', rowKey: 'open_mono', structure: 'simple', combineable: true },
  { key: 'ia', ipa: 'jä', char: '呀', hu: 'qichi', rowKey: 'rising', structure: 'compound', combineable: true },
  { key: 'ie', ipa: 'jɛ', char: '耶', hu: 'qichi', rowKey: 'rising', structure: 'compound', combineable: true },
  { key: 'iao', ipa: 'jɑu̯', char: '腰', hu: 'qichi', rowKey: 'u_coda', structure: 'compound', combineable: true },
  { key: 'iou', ipa: 'jou̯', char: '忧', hu: 'qichi', rowKey: 'u_coda', structure: 'compound', spelling: 'iu', combineable: true },
  { key: 'ian', ipa: 'jɛn', char: '烟', hu: 'qichi', rowKey: 'n_coda', structure: 'front_nasal', combineable: true },
  { key: 'in', ipa: 'in', char: '因', hu: 'qichi', rowKey: 'n_coda', structure: 'front_nasal', combineable: true },
  { key: 'iang', ipa: 'jɑŋ', char: '央', hu: 'qichi', rowKey: 'ng_coda', structure: 'back_nasal', combineable: true },
  { key: 'ing', ipa: 'iŋ', char: '英', hu: 'qichi', rowKey: 'ng_coda', structure: 'back_nasal', combineable: true },
  // w- 唇软腭介音（合口呼）
  { key: 'u', ipa: 'u', char: '乌', hu: 'hekou', rowKey: 'open_mono', structure: 'simple', combineable: true },
  { key: 'ua', ipa: 'wä', char: '蛙', hu: 'hekou', rowKey: 'rising', structure: 'compound', combineable: true },
  { key: 'uo', ipa: 'wo', char: '窝', hu: 'hekou', rowKey: 'rising', structure: 'compound', combineable: true },
  { key: 'uai', ipa: 'wai̯', char: '歪', hu: 'hekou', rowKey: 'i_coda', structure: 'compound', combineable: true },
  { key: 'uei', ipa: 'wei̯', char: '威', hu: 'hekou', rowKey: 'i_coda', structure: 'compound', spelling: 'ui', combineable: true },
  { key: 'uan', ipa: 'wan', char: '弯', hu: 'hekou', rowKey: 'n_coda', structure: 'front_nasal', combineable: true },
  { key: 'uen', ipa: 'wən', char: '温', hu: 'hekou', rowKey: 'n_coda', structure: 'front_nasal', spelling: 'un', combineable: true },
  { key: 'uang', ipa: 'wɑŋ', char: '汪', hu: 'hekou', rowKey: 'ng_coda', structure: 'back_nasal', combineable: true },
  { key: 'ueng', ipa: 'wəŋ', char: '翁', hu: 'hekou', rowKey: 'ng_coda', structure: 'back_nasal', combineable: true },
  { key: 'ong', ipa: 'ʊŋ', char: '轰', hu: 'hekou', rowKey: 'ng_coda', structure: 'back_nasal', combineable: true },
  // ɥ- 唇硬腭介音（撮口呼）
  { key: 'ü', ipa: 'y', char: '迂', hu: 'cuokou', rowKey: 'open_mono', structure: 'simple', combineable: true },
  { key: 'üe', ipa: 'ɥɛ', char: '约', hu: 'cuokou', rowKey: 'rising', structure: 'compound', combineable: true },
  { key: 'üan', ipa: 'ɥɛn', char: '冤', hu: 'cuokou', rowKey: 'n_coda', structure: 'front_nasal', combineable: true },
  { key: 'ün', ipa: 'yn', char: '晕', hu: 'cuokou', rowKey: 'n_coda', structure: 'front_nasal', combineable: true },
  { key: 'iong', ipa: 'jʊŋ', char: '雍', hu: 'cuokou', rowKey: 'ng_coda', structure: 'back_nasal', combineable: true },
]

/** 音节表的韵母列（可拼合韵母，按介音 × 韵尾行排序） */
export const FINALS_COMBINING: FinalInfo[] = FINAL_CELLS.filter(
  (f) => f.combineable && f.apicalVariant !== 'back',
)

const FINAL_ROW_ORDER = new Map(FINAL_ROWS.map((r, idx) => [r.key, idx]))
export function finalSortKey(f: FinalInfo): number {
  return (HU_ORDER.indexOf(f.hu) << 4) | (FINAL_ROW_ORDER.get(f.rowKey) ?? 0)
}

/** 按拼音键取韵母（舌尖 -i 取 z̩ 条目） */
export const FINAL_BY_KEY: ReadonlyMap<string, FinalInfo> = new Map(
  FINAL_CELLS.filter((f) => f.apicalVariant !== 'back').map((f) => [f.key, f]),
)

/* ---------------------------- 元音舌位四边形 ---------------------------- */

/**
 * 舌位坐标：从 docs/ 下的北京话元音图（Beijing_Mandarin_monophthongs_chart.svg 与
 * diphthongs part 1/2）逐一量取归一化——frontness 1 = 最前（左）→ 0 = 最后（右），
 * height 0 = 最高（闭）→ 1 = 最低（开）。
 */
export interface VowelPoint {
  frontness: number
  height: number
}

export interface VowelPosition extends VowelPoint {
  /** 关联韵母键（与韵母表联动选中）；null = 仅作舌位参考（央元音 ə 无独立韵母） */
  finalKey: string | null
  label: string
  ipa: string
  rounded: boolean
  /** 所属音位（虚线框分组显示条件变体；null = 独立音位） */
  phoneme: string | null
  /** 变体出处说明（舌位图悬停提示） */
  note?: string
}

/**
 * 单元音舌位点（严式标音，含条件变体）：
 * [a ä ɑ] 同属 /a/ 音位的条件变体；[ɤ e o ə] 为 /ə/ 系的互补分布变体；
 * [ɛ]（ê）兼作 ie/üe/ian 的韵腹。舌尖成音节辅音 z̩/ʐ̩ 与卷舌元音 ɚ
 * 不落在舌面元音梯形内，由韵母表条目承载。
 */
export const VOWEL_POSITIONS: VowelPosition[] = [
  { finalKey: 'i', label: 'i', ipa: 'i', frontness: 0.93, height: 0.086, rounded: false, phoneme: null },
  { finalKey: 'ü', label: 'y', ipa: 'y', frontness: 0.824, height: 0.097, rounded: true, phoneme: null },
  { finalKey: 'u', label: 'u', ipa: 'u', frontness: 0.068, height: 0.09, rounded: true, phoneme: null },
  { finalKey: 'e', label: 'ɤ', ipa: 'ɤ', frontness: 0.092, height: 0.235, rounded: false, phoneme: '/ə/', note: 'e 单念（鹅）' },
  { finalKey: 'o', label: 'o', ipa: 'o', frontness: 0.1, height: 0.42, rounded: true, phoneme: '/ə/', note: 'o 单念与 uo 的韵腹' },
  { finalKey: 'ei', label: 'e', ipa: 'e', frontness: 0.9, height: 0.42, rounded: false, phoneme: '/ə/', note: 'ei / uei 的韵腹' },
  { finalKey: null, label: 'ə', ipa: 'ə', frontness: 0.512, height: 0.518, rounded: false, phoneme: '/ə/', note: '央元音：en / eng 等的韵腹' },
  { finalKey: 'ê', label: 'ɛ', ipa: 'ɛ', frontness: 0.85, height: 0.6, rounded: false, phoneme: null, note: 'ê 单念；ie / üe / ian 的韵腹' },
  { finalKey: 'ai', label: 'a', ipa: 'a', frontness: 0.88, height: 0.93, rounded: false, phoneme: '/a/', note: 'ai / an 的韵腹（前 a）' },
  { finalKey: 'a', label: 'ä', ipa: 'ä', frontness: 0.651, height: 0.916, rounded: false, phoneme: '/a/', note: 'a 单念（央低）' },
  { finalKey: 'ao', label: 'ɑ', ipa: 'ɑ', frontness: 0.15, height: 0.93, rounded: false, phoneme: '/a/', note: 'ao / ang 的韵腹（后 ɑ）' },
]

/** 复元音滑动：from = 起始舌位，to = 滑动终点（箭头），labelAt = 标签摆放位 */
export interface VowelGlide {
  finalKey: string
  label: string
  ipa: string
  from: VowelPoint
  to: VowelPoint
  labelAt: VowelPoint
}

/**
 * 升双元音（介音起头）：ia ie üe ua uo，
 * 另含 uo 的央化变体 [wə]（与 uo 同关联韵母键）。
 */
export const VOWEL_GLIDES_RISING: VowelGlide[] = [
  { finalKey: 'ia', label: 'ia', ipa: 'jä', from: { frontness: 0.879, height: 0.057 }, to: { frontness: 0.54, height: 0.81 }, labelAt: { frontness: 0.8, height: 0.827 } },
  { finalKey: 'ie', label: 'ie', ipa: 'jɛ', from: { frontness: 0.93, height: 0.043 }, to: { frontness: 0.81, height: 0.431 }, labelAt: { frontness: 0.96, height: 0.485 } },
  { finalKey: 'üe', label: 'üe', ipa: 'ɥɛ', from: { frontness: 0.83, height: 0.039 }, to: { frontness: 0.719, height: 0.412 }, labelAt: { frontness: 0.743, height: 0.195 } },
  { finalKey: 'ua', label: 'ua', ipa: 'wä', from: { frontness: 0.154, height: 0.107 }, to: { frontness: 0.513, height: 0.819 }, labelAt: { frontness: 0.327, height: 0.622 } },
  { finalKey: 'uo', label: 'uo', ipa: 'wo', from: { frontness: 0.098, height: 0.118 }, to: { frontness: 0.472, height: 0.495 }, labelAt: { frontness: 0.155, height: 0.424 } },
  { finalKey: 'uo', label: 'uo', ipa: 'wə', from: { frontness: 0.088, height: 0.103 }, to: { frontness: 0.188, height: 0.387 }, labelAt: { frontness: 0.384, height: 0.293 } },
]

/** 降双元音（韵腹在前）：ai ei ao ou iu（iou，音位上 i 为韵腹、u 为韵尾） */
export const VOWEL_GLIDES_FALLING: VowelGlide[] = [
  { finalKey: 'ai', label: 'ai', ipa: 'ai̯', from: { frontness: 0.58, height: 0.791 }, to: { frontness: 0.94, height: 0.236 }, labelAt: { frontness: 0.79, height: 0.849 } },
  { finalKey: 'ei', label: 'ei', ipa: 'ei̯', from: { frontness: 0.806, height: 0.371 }, to: { frontness: 0.918, height: 0.135 }, labelAt: { frontness: 0.794, height: 0.433 } },
  { finalKey: 'ao', label: 'ao', ipa: 'ɑu̯', from: { frontness: 0.479, height: 0.703 }, to: { frontness: 0.153, height: 0.227 }, labelAt: { frontness: 0.449, height: 0.762 } },
  { finalKey: 'ou', label: 'ou', ipa: 'ou̯', from: { frontness: 0.16, height: 0.424 }, to: { frontness: 0.062, height: 0.136 }, labelAt: { frontness: 0.175, height: 0.521 } },
  { finalKey: 'iou', label: 'iu', ipa: 'jou̯', from: { frontness: 0.895, height: 0.074 }, to: { frontness: 0.153, height: 0.122 }, labelAt: { frontness: 0.764, height: 0.186 } },
]

/* -------------------------------- 音节表 -------------------------------- */

export interface SyllableCell {
  /** 《汉语拼音方案》拼写（省写规则已应用，如 ju、liu、wei） */
  pinyin: string
  char: string
}

function cells(map: Record<string, string>): Record<string, SyllableCell> {
  const out: Record<string, SyllableCell> = {}
  for (const [finalKey, spec] of Object.entries(map)) {
    const spaceAt = spec.indexOf(' ')
    if (spaceAt <= 0) continue
    out[finalKey] = { pinyin: spec.slice(0, spaceAt), char: spec.slice(spaceAt + 1) }
  }
  return out
}

/**
 * 合法普通话音节表（不含声调；约 400 个基本音节）。
 * 行键 = 声母键（'' = 零声母 Ø），列键 = 韵母键。
 */
export const SYLLABLES: Readonly<Record<string, Readonly<Record<string, SyllableCell>>>> = {
  b: cells({
    a: 'ba 巴', o: 'bo 波', ai: 'bai 白', ei: 'bei 杯', ao: 'bao 包', an: 'ban 板',
    en: 'ben 本', ang: 'bang 帮', eng: 'beng 泵', i: 'bi 比', ie: 'bie 别',
    iao: 'biao 标', ian: 'bian 边', in: 'bin 宾', ing: 'bing 冰', u: 'bu 不',
  }),
  p: cells({
    a: 'pa 怕', o: 'po 坡', ai: 'pai 拍', ei: 'pei 胚', ao: 'pao 抛', ou: 'pou 剖',
    an: 'pan 盘', en: 'pen 盆', ang: 'pang 旁', eng: 'peng 朋', i: 'pi 皮',
    ie: 'pie 撇', iao: 'piao 票', ian: 'pian 片', in: 'pin 品', ing: 'ping 平', u: 'pu 普',
  }),
  m: cells({
    a: 'ma 妈', o: 'mo 摸', ei: 'mei 妹', ao: 'mao 猫', ou: 'mou 某', an: 'man 慢',
    en: 'men 门', ang: 'mang 忙', eng: 'meng 梦', i: 'mi 米', ie: 'mie 灭',
    iao: 'miao 苗', iou: 'miu 谬', ian: 'mian 面', in: 'min 民', ing: 'ming 明', u: 'mu 木',
  }),
  f: cells({
    a: 'fa 发', o: 'fo 佛', ei: 'fei 飞', ou: 'fou 否', an: 'fan 翻', en: 'fen 分',
    ang: 'fang 方', eng: 'feng 风', u: 'fu 服',
  }),
  d: cells({
    a: 'da 大', e: 'de 得', ai: 'dai 带', ei: 'dei 得', ao: 'dao 刀', ou: 'dou 都',
    an: 'dan 但', ang: 'dang 当', eng: 'deng 等', i: 'di 地', ie: 'die 爹',
    iao: 'diao 刁', iou: 'diu 丢', ian: 'dian 点', ing: 'ding 定', u: 'du 读',
    uo: 'duo 多', uei: 'dui 对', uan: 'duan 端', uen: 'dun 吨', ong: 'dong 东',
  }),
  t: cells({
    a: 'ta 他', e: 'te 特', ai: 'tai 太', ao: 'tao 掏', ou: 'tou 偷', an: 'tan 谈',
    ang: 'tang 汤', eng: 'teng 疼', i: 'ti 题', ie: 'tie 铁', iao: 'tiao 条',
    ian: 'tian 天', ing: 'ting 听', u: 'tu 图', uo: 'tuo 拖', uei: 'tui 推',
    uan: 'tuan 团', uen: 'tun 吞', ong: 'tong 通',
  }),
  n: cells({
    a: 'na 那', e: 'ne 讷', ai: 'nai 奶', ao: 'nao 闹', an: 'nan 南', en: 'nen 嫩',
    ang: 'nang 囊', eng: 'neng 能', ei: 'nei 内', i: 'ni 你', ie: 'nie 捏',
    iao: 'niao 鸟', iou: 'niu 牛', ian: 'nian 年', in: 'nin 您', iang: 'niang 娘',
    ing: 'ning 宁', u: 'nu 怒', uo: 'nuo 挪', uan: 'nuan 暖', ü: 'nü 女',
    üe: 'nüe 虐', ong: 'nong 农',
  }),
  l: cells({
    a: 'la 拉', e: 'le 乐', ai: 'lai 来', ei: 'lei 类', ao: 'lao 老', ou: 'lou 楼',
    an: 'lan 蓝', ang: 'lang 狼', eng: 'leng 冷', i: 'li 力', ia: 'lia 俩',
    ie: 'lie 列', iao: 'liao 料', iou: 'liu 六', ian: 'lian 连', in: 'lin 林',
    iang: 'liang 两', ing: 'ling 零', u: 'lu 路', uo: 'luo 落', uan: 'luan 乱',
    uen: 'lun 论', ü: 'lü 吕', üe: 'lüe 略', ong: 'long 龙',
  }),
  g: cells({
    a: 'ga 嘎', e: 'ge 哥', ai: 'gai 该', ao: 'gao 高', ou: 'gou 沟', an: 'gan 干',
    en: 'gen 根', ang: 'gang 刚', eng: 'geng 更', u: 'gu 古', ua: 'gua 瓜',
    uo: 'guo 国', uai: 'guai 怪', uei: 'gui 贵', uan: 'guan 关', uen: 'gun 滚',
    uang: 'guang 光', ong: 'gong 工',
  }),
  k: cells({
    a: 'ka 卡', e: 'ke 科', ai: 'kai 开', ao: 'kao 考', ou: 'kou 口', an: 'kan 看',
    en: 'ken 肯', ang: 'kang 康', eng: 'keng 坑', u: 'ku 哭', ua: 'kua 夸',
    uo: 'kuo 阔', uai: 'kuai 快', uei: 'kui 亏', uan: 'kuan 宽', uen: 'kun 困',
    uang: 'kuang 筐', ong: 'kong 空',
  }),
  h: cells({
    a: 'ha 哈', e: 'he 喝', ai: 'hai 海', ao: 'hao 好', ou: 'hou 后', an: 'han 汗',
    en: 'hen 很', ang: 'hang 航', eng: 'heng 横', u: 'hu 湖', ua: 'hua 花',
    uo: 'huo 火', uai: 'huai 坏', uei: 'hui 会', uan: 'huan 换', uen: 'hun 婚',
    uang: 'huang 黄', ong: 'hong 红',
  }),
  j: cells({
    i: 'ji 机', ia: 'jia 家', ie: 'jie 街', iao: 'jiao 叫', iou: 'jiu 九',
    ian: 'jian 见', in: 'jin 金', iang: 'jiang 江', ing: 'jing 京',
    ü: 'ju 居', üe: 'jue 觉', üan: 'juan 卷', ün: 'jun 军', iong: 'jiong 窘',
  }),
  q: cells({
    i: 'qi 七', ia: 'qia 恰', ie: 'qie 切', iao: 'qiao 桥', iou: 'qiu 秋',
    ian: 'qian 千', in: 'qin 琴', iang: 'qiang 强', ing: 'qing 青',
    ü: 'qu 区', üe: 'que 缺', üan: 'quan 圈', ün: 'qun 群', iong: 'qiong 穷',
  }),
  x: cells({
    i: 'xi 西', ia: 'xia 下', ie: 'xie 些', iao: 'xiao 小', iou: 'xiu 修',
    ian: 'xian 先', in: 'xin 新', iang: 'xiang 想', ing: 'xing 星',
    ü: 'xu 需', üe: 'xue 学', üan: 'xuan 选', ün: 'xun 寻', iong: 'xiong 兄',
  }),
  zh: cells({
    '-i': 'zhi 知', a: 'zha 渣', e: 'zhe 这', ai: 'zhai 摘', ao: 'zhao 找',
    ou: 'zhou 周', an: 'zhan 站', en: 'zhen 真', ang: 'zhang 张', eng: 'zheng 正',
    u: 'zhu 主', ua: 'zhua 抓', uo: 'zhuo 桌', uei: 'zhui 追', uan: 'zhuan 转',
    uen: 'zhun 准', uang: 'zhuang 装', ong: 'zhong 中',
  }),
  ch: cells({
    '-i': 'chi 痴', a: 'cha 茶', e: 'che 车', ai: 'chai 差', ao: 'chao 超',
    ou: 'chou 抽', an: 'chan 产', en: 'chen 陈', ang: 'chang 长', eng: 'cheng 成',
    u: 'chu 出', uo: 'chuo 戳', uei: 'chui 吹', uan: 'chuan 船', uen: 'chun 春',
    uang: 'chuang 床', ong: 'chong 冲',
  }),
  sh: cells({
    '-i': 'shi 诗', a: 'sha 沙', e: 'she 奢', ai: 'shai 晒', ao: 'shao 烧',
    ou: 'shou 手', an: 'shan 山', en: 'shen 深', ang: 'shang 上', eng: 'sheng 生',
    u: 'shu 书', ua: 'shua 刷', uo: 'shuo 说', uei: 'shui 水', uan: 'shuan 栓',
    uen: 'shun 顺', uang: 'shuang 双',
  }),
  r: cells({
    '-i': 'ri 日', e: 're 热', ao: 'rao 绕', ou: 'rou 肉', an: 'ran 然',
    en: 'ren 人', ang: 'rang 让', eng: 'reng 扔', u: 'ru 如', uo: 'ruo 若',
    uei: 'rui 瑞', uan: 'ruan 软', uen: 'run 润', ong: 'rong 容',
  }),
  z: cells({
    '-i': 'zi 资', a: 'za 杂', e: 'ze 则', ai: 'zai 再', ao: 'zao 早', ou: 'zou 走',
    an: 'zan 赞', en: 'zen 怎', ang: 'zang 脏', eng: 'zeng 增', u: 'zu 组',
    uo: 'zuo 作', uei: 'zui 最', uan: 'zuan 钻', uen: 'zun 尊', ong: 'zong 总',
  }),
  c: cells({
    '-i': 'ci 雌', a: 'ca 擦', e: 'ce 册', ai: 'cai 菜', ao: 'cao 草', ou: 'cou 凑',
    an: 'can 餐', en: 'cen 参', ang: 'cang 仓', eng: 'ceng 层', u: 'cu 醋',
    uo: 'cuo 错', uei: 'cui 脆', uan: 'cuan 窜', uen: 'cun 村', ong: 'cong 从',
  }),
  s: cells({
    '-i': 'si 思', a: 'sa 撒', e: 'se 色', ai: 'sai 赛', ao: 'sao 扫', ou: 'sou 搜',
    an: 'san 三', en: 'sen 森', ang: 'sang 桑', eng: 'seng 僧', u: 'su 素',
    uo: 'suo 所', uei: 'sui 岁', uan: 'suan 算', uen: 'sun 孙', ong: 'song 送',
  }),
  // 零声母 Ø
  '': cells({
    a: 'a 啊', o: 'o 哦', e: 'e 鹅', ai: 'ai 爱', ei: 'ei 诶', ao: 'ao 熬',
    ou: 'ou 欧', an: 'an 安', en: 'en 恩', ang: 'ang 昂', eng: 'eng 鞥',
    i: 'yi 衣', ia: 'ya 呀', ie: 'ye 夜', iao: 'yao 要', iou: 'you 有',
    ian: 'yan 烟', in: 'yin 音', iang: 'yang 央', ing: 'ying 英',
    u: 'wu 五', ua: 'wa 挖', uo: 'wo 我', uai: 'wai 外', uei: 'wei 位',
    uan: 'wan 万', uen: 'wen 问', uang: 'wang 王', ueng: 'weng 翁',
    ü: 'yu 鱼', üe: 'yue 月', üan: 'yuan 元', ün: 'yun 云', iong: 'yong 用',
  }),
}

/** 音节表的声母行序：按发音部位分组，零声母 Ø 在最后 */
export const SYLLABLE_INITIAL_ORDER: string[] = [
  'b', 'p', 'm', 'f',
  'z', 'c', 's',
  'd', 't', 'n', 'l',
  'zh', 'ch', 'sh', 'r',
  'j', 'q', 'x',
  'g', 'k', 'h',
  '',
]

export function syllableOf(initialKey: string, finalKey: string): SyllableCell | undefined {
  return SYLLABLES[initialKey]?.[finalKey]
}

/* --------------------------------- 声调 --------------------------------- */

export interface ToneInfo {
  index: 1 | 2 | 3 | 4
  name: string
  /** 五度调值 */
  value: string
  /** IPA 调号 */
  ipa: string
  shape: string
  example: string
  examplePinyin: string
}

export const TONES: ToneInfo[] = [
  { index: 1, name: '阴平（第一声）', value: '55', ipa: '˥', shape: '高平调', example: '妈', examplePinyin: 'mā' },
  { index: 2, name: '阳平（第二声）', value: '35', ipa: '˧˥', shape: '中升调', example: '麻', examplePinyin: 'má' },
  { index: 3, name: '上声（第三声）', value: '214', ipa: '˨˩˦', shape: '降升调', example: '马', examplePinyin: 'mǎ' },
  { index: 4, name: '去声（第四声）', value: '51', ipa: '˥˩', shape: '全降调', example: '骂', examplePinyin: 'mà' },
]

export const TONE_BY_INDEX: ReadonlyMap<number, ToneInfo> = new Map(TONES.map((t) => [t.index, t]))

/* ------------------------------- 易混组 -------------------------------- */

export interface ConfusableGroup {
  key: string
  name: string
  hint: string
  /** 涉及的声母键（用于声母表/音节表高亮） */
  initials: string[]
  /** 涉及的韵母键（用于韵母表/音节表高亮） */
  finals: string[]
  /** 对立键对（声母或韵母，供一键并排比较/高亮） */
  pairs: Array<[string, string]>
}

export const CONFUSABLE_GROUPS: ConfusableGroup[] = [
  {
    key: 'aspiration',
    name: '送气对立',
    hint: '不送气 ↔ 送气：只差一口气，意思全变（如“爸”bà ↔ “怕”pà）。',
    initials: ['b', 'p', 'd', 't', 'g', 'k', 'z', 'c', 'zh', 'ch', 'j', 'q'],
    finals: [],
    pairs: [['b', 'p'], ['d', 't'], ['g', 'k'], ['z', 'c'], ['zh', 'ch'], ['j', 'q']],
  },
  {
    key: 'flat-retroflex',
    name: '平翘舌',
    hint: '齿龈 z/c/s ↔ 卷舌 zh/ch/sh：舌尖平伸还是上翘抵硬腭前部。',
    initials: ['z', 'c', 's', 'zh', 'ch', 'sh'],
    finals: [],
    pairs: [['z', 'zh'], ['c', 'ch'], ['s', 'sh']],
  },
  {
    key: 'n-l',
    name: 'n / l',
    hint: '鼻音 n 气流从鼻腔出 ↔ 边音 l 气流从舌两侧出。',
    initials: ['n', 'l'],
    finals: [],
    pairs: [['n', 'l']],
  },
  {
    key: 'nasal-finals',
    name: '前后鼻',
    hint: '韵尾 -n（舌尖抵上龈，前鼻音） ↔ -ng（舌根抵软腭，后鼻音）。',
    initials: [],
    finals: ['an', 'ang', 'en', 'eng', 'in', 'ing', 'ian', 'iang', 'uan', 'uang', 'ün', 'iong'],
    pairs: [['an', 'ang'], ['en', 'eng'], ['in', 'ing'], ['ian', 'iang'], ['uan', 'uang'], ['ün', 'iong']],
  },
  {
    key: 'u-ü',
    name: 'u / ü',
    hint: 'u 圆唇后元音 ↔ ü 圆唇前元音：嘴角撮起程度与舌位前后不同。',
    initials: [],
    finals: ['u', 'ü', 'uo', 'üe', 'uan', 'üan', 'uen', 'ün'],
    pairs: [['u', 'ü'], ['uo', 'üe'], ['uan', 'üan'], ['uen', 'ün']],
  },
]

/* ------------------------------ 拼音解析 ------------------------------- */

const TONE_MARKS = new Map<string, number>([
  ['\u0304', 1], ['\u0301', 2], ['\u030C', 3], ['\u0300', 4],
])

/** 去声调符号（保留 ü 的分音符），v 视为 ü */
export function stripToneMarks(pinyin: string): string {
  return pinyin
    .normalize('NFD')
    .replace(/[\u0304\u0301\u030C\u0300]/g, '')
    .replace(/v/g, 'ü')
    .normalize('NFC')
}

/** 单音节拼音的声调号（1–4；轻声/无标记为 0；多音节取全部声调用 toneNumbersOf） */
export function toneNumberOf(pinyin: string): number {
  const marks = [...pinyin.normalize('NFD')].filter((ch) => TONE_MARKS.has(ch))
  return marks.length > 0 ? (TONE_MARKS.get(marks[0]!) ?? 0) : 0
}

/** 取拼音串里出现的全部声调号（按出现顺序） */
export function toneNumbersOf(pinyin: string): number[] {
  const out: number[] = []
  for (const ch of pinyin.normalize('NFD')) {
    const tone = TONE_MARKS.get(ch)
    if (tone && out[out.length - 1] !== tone) out.push(tone)
  }
  return out
}

/** 零声母 y/w 拼写 → 韵母键 */
const Y_SPELLINGS: Record<string, string> = {
  yi: 'i', ya: 'ia', yo: 'io', ye: 'ie', yao: 'iao', you: 'iou', yan: 'ian',
  yin: 'in', yang: 'iang', ying: 'ing', yu: 'ü', yue: 'üe', yuan: 'üan', yun: 'ün',
  yong: 'iong',
}

/** 零声母 w 拼写 → 韵母键 */
const W_SPELLINGS: Record<string, string> = {
  wu: 'u', wa: 'ua', wo: 'uo', wai: 'uai', wei: 'uei', wan: 'uan',
  wen: 'uen', wang: 'uang', weng: 'ueng',
}

/** j/q/x 后的省写还原：u 系拼写实际是 ü 系韵母 */
const JQX_U_RESTORE: Record<string, string> = {
  u: 'ü', ue: 'üe', uan: 'üan', un: 'ün',
}

/** 声母后的整体省写还原：iou→iu、uei→ui、uen→un（《汉语拼音方案》） */
const SPELLING_RESTORE: Record<string, string> = {
  iu: 'iou', ui: 'uei', un: 'uen',
}

/**
 * 单音节拼音（无声调或有声调）拆分为 { 声母键, 韵母键 }。
 * 声母键 '' = 零声母；舌尖 -i 在 z/c/s 与 zh/ch/sh/r 后返回 '-i'。
 * 解析失败返回 null。
 */
export function splitPinyinSyllable(raw: string): { initial: string; final: string } | null {
  const py = stripToneMarks(raw.trim().toLowerCase())
  if (!py) return null
  // 零声母拼写
  if (py.startsWith('y')) {
    const final = Y_SPELLINGS[py] ?? (py.length > 1 ? `i${py.slice(1)}` : null)
    return final ? { initial: '', final } : null
  }
  if (py.startsWith('w')) {
    const final = W_SPELLINGS[py] ?? (py.length > 1 ? `u${py.slice(1)}` : null)
    return final ? { initial: '', final } : null
  }
  // 双字母声母优先
  const twoLetter = py.slice(0, 2)
  const oneLetter = py.slice(0, 1)
  let initial = ''
  let rest = py
  if (['zh', 'ch', 'sh'].includes(twoLetter)) {
    initial = twoLetter
    rest = py.slice(2)
  } else if (INITIAL_BY_KEY.has(oneLetter) && !FINAL_BY_KEY.has(py)) {
    initial = oneLetter
    rest = py.slice(1)
  } else if (FINAL_BY_KEY.has(py) || py === 'ê' || py === 'er') {
    // 整体就是韵母（零声母开口呼：a / ai / ang / er …）
    return { initial: '', final: py }
  }
  if (!initial) return null
  // j/q/x 后还原 ü 系省写；其余声母后还原 iou/uei/uen 省写
  if (['j', 'q', 'x'].includes(initial)) {
    rest = JQX_U_RESTORE[rest] ?? rest
  }
  rest = SPELLING_RESTORE[rest] ?? rest
  // 平翘舌声母后的 i 是成音节辅音 z̩/ʐ̩，与舌面 i 区分
  if (['z', 'c', 's', 'zh', 'ch', 'sh', 'r'].includes(initial) && rest === 'i') {
    rest = '-i'
  }
  if (!FINAL_BY_KEY.has(rest)) return null
  return { initial, final: rest }
}

/* --------------------------- 关卡 → 音系匹配 --------------------------- */

export interface LevelLike {
  layer: 'vowel' | 'initial' | 'syllable' | string
  targetSound?: string | null
  pinyin?: string | null
  /** 后端 phonology 段（§5.1）：填写时优先生效，缺省按 layer/targetSound/pinyin 兜底 */
  phonology?: LevelPhonology | null
}

export interface PhonologyMatch {
  /** 关卡类型：声母 / 韵母 / 音节 / 声调；解析失败为 null */
  kind: 'initial' | 'final' | 'syllable' | 'tone' | null
  initial: InitialInfo | null
  final: FinalInfo | null
  /** 国际音标（声母或韵母或音节） */
  ipa: string
  /** 语音学特征标签（如「卷舌 · 塞擦音 · 清 · 不送气」） */
  labels: string[]
  /** 关卡拼音中的声调序列 */
  tones: number[]
}

export function initialLabels(info: InitialInfo): string[] {
  if (info.zeroSpelling) {
    const spellings: Record<NonNullable<InitialInfo['zeroSpelling']>, string> = {
      y: '零声母拼写 y（j- 介音，i 系）',
      w: '零声母拼写 w（w- 介音，u 系）',
      yu: '零声母拼写 yu（ɥ- 介音，ü 系）',
    }
    return [spellings[info.zeroSpelling]]
  }
  const labels = [info.place, info.manner, info.voicing === 'voiceless' ? '清' : '浊']
  if (info.aspiration === 'aspirated') labels.push('送气')
  else if (info.aspiration === 'unaspirated') labels.push('不送气')
  if (info.codaOnly) labels.push('仅作韵尾 -ng')
  return labels
}

export function finalLabels(info: FinalInfo): string[] {
  const row = FINAL_ROWS.find((r) => r.key === info.rowKey)
  return [HU_LABELS[info.hu], row?.label ?? '']
}

/** 后端 phonology.finalStructure 枚举 → 结构标签（structure 级，不细分前/后/中响） */
const STRUCTURE_LABELS: Record<FinalStructure, string> = {
  simple: '单韵母',
  special: '单韵母',
  compound: '复韵母',
  front_nasal: '前鼻音韵母',
  back_nasal: '后鼻音韵母',
}

/** 平翘舌声母集合：其后 i 为成音节辅音（z/c/s → z̩，zh/ch/sh/r → ʐ̩） */
const SIBILANTS = new Set(['z', 'c', 's', 'zh', 'ch', 'sh', 'r'])

/**
 * 音节 IPA 组合：零声母不带任何符号（直接韵母 IPA，如 [ai̯]）；
 * 舌尖 -i 为成音节辅音——zh/ch/sh 后为 [ʐ̩]、z/c/s 后为 [z̩]，
 * r 后整个音节即卷舌近音的成音节形式 [ɻ̩]（不再叠加声母符号）。
 */
export function syllableIpa(initialKey: string | null | undefined, final: FinalInfo | null | undefined): string {
  if (!final) return initialKey ? (INITIAL_BY_KEY.get(initialKey)?.ipa ?? '') : ''
  const initial = initialKey ? INITIAL_BY_KEY.get(initialKey) : undefined
  if (final.key === '-i') {
    if (initialKey === 'r') return 'ɻ̩'
    if (['zh', 'ch', 'sh'].includes(initialKey ?? '')) return (initial?.ipa ?? '') + 'ʐ̩'
  }
  return (initial?.ipa ?? '') + final.ipa
}

/** 声母或韵母键 → IPA（兼容后端 phonology.initial/final 字段） */
export function ipaOfSound(kind: 'initial' | 'final', key: string): string {
  if (kind === 'initial') return INITIAL_BY_KEY.get(key)?.ipa ?? ''
  return FINAL_BY_KEY.get(key)?.ipa ?? ''
}

/** phonology 段 → 音系匹配（§5.1 主路径；键未知时尽量用段内特征拼标签） */
function matchPhonology(phono: LevelPhonology, pinyin: string): PhonologyMatch | null {
  const initial =
    phono.initial != null && phono.initial !== '' ? (INITIAL_BY_KEY.get(phono.initial) ?? null) : null
  const final = phono.final != null ? (FINAL_BY_KEY.get(phono.final) ?? null) : null
  const kind =
    phono.kind ?? (initial && final ? 'syllable' : initial ? 'initial' : final ? 'final' : null)
  if (!kind) return null
  const tones = phono.tones ?? toneNumbersOf(pinyin)

  if (kind === 'tone') {
    return { kind, initial: null, final: null, ipa: phono.ipa ?? '', labels: [], tones }
  }
  // 无声韵定位、无 IPA、也无声调覆盖 → 无可消费信息，回落兜底猜测
  if (!initial && !final && !phono.ipa && !(phono.tones && phono.tones.length > 0)) return null

  // 特征覆盖：段内字段优先，落到音系表条目上再生成标签
  const mergedInitial: InitialInfo | null = initial
    ? {
        ...initial,
        place: phono.place ?? initial.place,
        manner: phono.manner ?? initial.manner,
        aspiration: phono.aspiration ?? initial.aspiration,
        voicing: phono.voicing ?? initial.voicing,
      }
    : null
  let finalTagLabels: string[] = []
  if (final) {
    const hu = phono.hu ?? final.hu
    const structure = phono.finalStructure ?? final.structure
    finalTagLabels =
      phono.hu || phono.finalStructure
        ? [HU_LABELS[hu], STRUCTURE_LABELS[structure]]
        : finalLabels(final)
  }

  if (kind === 'initial') {
    return {
      kind,
      initial: mergedInitial,
      final: null,
      ipa: phono.ipa ?? mergedInitial?.ipa ?? '',
      labels: mergedInitial
        ? initialLabels(mergedInitial)
        : [phono.place, phono.manner].filter((x): x is string => x != null),
      tones,
    }
  }
  if (kind === 'final') {
    return {
      kind,
      initial: null,
      final,
      ipa: phono.ipa ?? final?.ipa ?? '',
      labels: final ? finalTagLabels : [phono.hu ? HU_LABELS[phono.hu] : '', phono.finalStructure ? STRUCTURE_LABELS[phono.finalStructure] : ''].filter(Boolean),
      tones,
    }
  }
  // syllable
  return {
    kind,
    initial: mergedInitial,
    final,
    ipa: phono.ipa || syllableIpa(phono.initial ?? '', final),
    labels: [
      ...(mergedInitial ? initialLabels(mergedInitial) : phono.initial === '' ? ['零声母'] : []),
      ...finalTagLabels,
    ],
    tones,
  }
}

/**
 * 关卡 → 音系单元格自动匹配（§5.1）：
 * 0. 关卡填写 phonology 段时优先消费（声母/韵母键、IPA、特征、声调全覆盖）；
 * 1. targetSound 直接命中声母/韵母键（声母关 b、韵母关 a）；
 * 2. syllable 关 targetSound 直接用带调拼音（如 "mā"，与地图展示一致），
 *    旧式 "m+a" 加号写法仍兼容拆分；
 * 3. 否则按 pinyin 拆分（含零声母拼写还原）。
 */
export function matchLevel(level: LevelLike): PhonologyMatch {
  const target = (level.targetSound ?? '').trim()
  const pinyin = (level.pinyin ?? '').trim()

  if (level.phonology) {
    const matched = matchPhonology(level.phonology, pinyin)
    if (matched) return matched
  }

  if (level.layer === 'initial' && INITIAL_BY_KEY.has(target)) {
    const initial = INITIAL_BY_KEY.get(target)!
    return {
      kind: 'initial',
      initial,
      final: null,
      ipa: initial.ipa,
      labels: initialLabels(initial),
      tones: toneNumbersOf(pinyin),
    }
  }

  if (level.layer === 'vowel' && FINAL_BY_KEY.has(target)) {
    const final = FINAL_BY_KEY.get(target)!
    return {
      kind: 'final',
      initial: null,
      final,
      ipa: final.ipa,
      labels: finalLabels(final),
      tones: toneNumbersOf(pinyin),
    }
  }

  // syllable 关：targetSound 带调拼音（"mā"，splitPinyinSyllable 内去调拆分）或旧式 "m+a"
  const plusSplit = /^(\w*)\+([^+]+)$/.exec(target)
  const firstSyllable = pinyin.split(/\s+/)[0] ?? ''
  let split: { initial: string; final: string } | null = null
  if (plusSplit) {
    const initialKey = plusSplit[1] ?? ''
    const finalKey = stripToneMarks(plusSplit[2] ?? '')
    if ((initialKey === '' || INITIAL_BY_KEY.has(initialKey)) && FINAL_BY_KEY.has(finalKey)) {
      split = { initial: initialKey, final: finalKey }
    }
  }
  if (!split) split = splitPinyinSyllable(firstSyllable || target)
  // 平翘舌声母后的 i 是舌尖元音（与 splitPinyinSyllable 同口径，兼容 "zh+i" 写法）
  if (split && SIBILANTS.has(split.initial) && split.final === 'i') {
    split = { ...split, final: '-i' }
  }

  if (split && INITIAL_BY_KEY.has(split.initial) && FINAL_BY_KEY.has(split.final)) {
    const initial = split.initial ? INITIAL_BY_KEY.get(split.initial)! : null
    const final = FINAL_BY_KEY.get(split.final)!
    // 舌尖 -i 修正：仅平翘舌声母后成立
    const validApical = split.final !== '-i' || ['z', 'c', 's', 'zh', 'ch', 'sh', 'r'].includes(split.initial)
    if (validApical) {
      return {
        kind: 'syllable',
        initial,
        final,
        ipa: syllableIpa(split.initial, final),
        labels: [...(initial ? initialLabels(initial) : []), ...finalLabels(final)],
        tones: toneNumbersOf(pinyin),
      }
    }
  }

  // 兜底：pinyin 拆出声母/韵母任一可用
  if (split && INITIAL_BY_KEY.has(split.initial) && !FINAL_BY_KEY.has(split.final)) {
    const initial = INITIAL_BY_KEY.get(split.initial)!
    return { kind: 'initial', initial, final: null, ipa: initial.ipa, labels: initialLabels(initial), tones: toneNumbersOf(pinyin) }
  }
  if (split && FINAL_BY_KEY.has(split.final)) {
    const final = FINAL_BY_KEY.get(split.final)!
    return { kind: 'final', initial: null, final, ipa: final.ipa, labels: finalLabels(final), tones: toneNumbersOf(pinyin) }
  }

  return { kind: null, initial: null, final: null, ipa: '', labels: [], tones: [] }
}
