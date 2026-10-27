/**
 * 发音库矩阵组件共用工具（P06 §2）：关卡 → 音系覆盖索引、搜索匹配、声调关匹配。
 * 纯函数模块：由各表格组件传入 LevelSummary[] 构建，不依赖 store / 路由。
 */
import type { LevelSummary } from '@/api'
import {
  matchLevel,
  stripToneMarks,
  type FinalInfo,
  type InitialInfo,
  type SyllableCell,
} from '@/phonology/mandarin'

/** 关卡 → 音系覆盖索引（matchLevel 结果按声母/韵母/音节归类，同键取最早开放关） */
export interface LevelCoverage {
  /** 专属声母关（kind='initial'）：声母键 → 关卡 */
  byInitial: Map<string, LevelSummary>
  /** 专属韵母关（kind='final'）：韵母键 → 关卡 */
  byFinal: Map<string, LevelSummary>
  /** 音节关（kind='syllable'）：`${声母键}|${韵母键}` → 关卡（零声母声母键为 ''） */
  bySyllable: Map<string, LevelSummary>
  /** 任一匹配含该声母键（含音节关兜底）：声母键 → 关卡 */
  anyInitial: Map<string, LevelSummary>
  /** 任一匹配含该韵母键（含音节关兜底）：韵母键 → 关卡 */
  anyFinal: Map<string, LevelSummary>
}

/** 音节坐标键（与 bySyllable 对齐；零声母 initialKey = ''） */
export function syllableKey(initialKey: string, finalKey: string): string {
  return `${initialKey}|${finalKey}`
}

export function buildCoverage(levels: LevelSummary[]): LevelCoverage {
  const coverage: LevelCoverage = {
    byInitial: new Map(),
    byFinal: new Map(),
    bySyllable: new Map(),
    anyInitial: new Map(),
    anyFinal: new Map(),
  }
  for (const level of levels) {
    const m = matchLevel({
      layer: level.layer,
      targetSound: level.targetSound,
      pinyin: level.pinyin,
      phonology: level.phonology,
    })
    if (m.initial) {
      if (!coverage.anyInitial.has(m.initial.key)) coverage.anyInitial.set(m.initial.key, level)
      if (m.kind === 'initial' && !coverage.byInitial.has(m.initial.key)) {
        coverage.byInitial.set(m.initial.key, level)
      }
    }
    if (m.final) {
      if (!coverage.anyFinal.has(m.final.key)) coverage.anyFinal.set(m.final.key, level)
      if (m.kind === 'final' && !coverage.byFinal.has(m.final.key)) {
        coverage.byFinal.set(m.final.key, level)
      }
    }
    if (m.kind === 'syllable' && m.final) {
      const key = syllableKey(m.initial?.key ?? '', m.final.key)
      if (!coverage.bySyllable.has(key)) coverage.bySyllable.set(key, level)
    }
  }
  return coverage
}

/** 搜索词归一：去首尾空白 + 小写 + 去声调符号 + v → ü */
export function normalizeQuery(raw: string): string {
  return stripToneMarks(raw.trim().toLowerCase())
}

function haystack(level?: LevelSummary | null): string {
  if (!level) return ''
  return `${level.title} ${level.targetSound} ${level.pinyin}`.toLowerCase()
}

function contains(text: string, q: string): boolean {
  return text.toLowerCase().includes(q)
}

/** 声母搜索命中：拼音键 / IPA / 代表字 / 覆盖关卡标题 */
export function matchesInitialQuery(info: InitialInfo, q: string, level?: LevelSummary | null): boolean {
  if (!q) return true
  if (contains(info.key, q) || contains(info.ipa, q) || contains(info.char, q)) return true
  return contains(haystack(level), q)
}

/** 韵母搜索命中：拼音键 / 省写 / IPA / 代表字 / 覆盖关卡标题 */
export function matchesFinalQuery(info: FinalInfo, q: string, level?: LevelSummary | null): boolean {
  if (!q) return true
  if (contains(info.key, q) || contains(info.ipa, q) || contains(info.char, q)) return true
  if (info.spelling && contains(info.spelling, q)) return true
  return contains(haystack(level), q)
}

/** 音节搜索命中：拼写 / 代表字 / 声母键 / 韵母键 / 覆盖关卡标题 */
export function matchesSyllableQuery(
  initialKey: string,
  finalKey: string,
  cell: SyllableCell,
  q: string,
  level?: LevelSummary | null,
): boolean {
  if (!q) return true
  if (contains(cell.pinyin, q) || contains(cell.char, q)) return true
  if (contains(initialKey, q) || contains(finalKey, q)) return true
  return contains(haystack(level), q)
}

/**
 * 声调关匹配（§2.6）：音节关/声调关按声调覆盖匹配——
 * 关卡声调必须明确（拼音标调或 phonology.tones）：
 * 如 L30「mā」只算阴平，L31–L33 分别覆盖阳平/上声/去声；
 * 未标调也未写 tones 的关卡不参与声调表匹配。
 */
export function toneLevelFor(levels: LevelSummary[], toneIndex: number): LevelSummary | undefined {
  for (const level of levels) {
    const m = matchLevel({
      layer: level.layer,
      targetSound: level.targetSound,
      pinyin: level.pinyin,
      phonology: level.phonology,
    })
    if (m.kind !== 'syllable' && m.kind !== 'tone') continue
    if (m.tones.includes(toneIndex)) return level
  }
  return undefined
}

/**
 * 音节表单元格覆盖关卡（§2.5 点亮口径）：
 * 音节关优先；否则声母关（Ø 行经 y/w 零声母拼写关：齐齿/撮口归 y、合口归 w）；
 * 最后韵母关（单韵母关点亮整列，如 a 关同时点亮 ba/ma/Ø+a）。
 */
export function cellLevelFor(
  cov: LevelCoverage,
  initialKey: string,
  final: FinalInfo,
): LevelSummary | null {
  const bySyll = cov.bySyllable.get(syllableKey(initialKey, final.key))
  if (bySyll) return bySyll
  if (initialKey === '') {
    const spell =
      final.hu === 'qichi' || final.hu === 'cuokou' ? 'y' : final.hu === 'hekou' ? 'w' : null
    const viaSpell = spell ? cov.byInitial.get(spell) : null
    if (viaSpell) return viaSpell
  } else {
    const viaInitial = cov.byInitial.get(initialKey)
    if (viaInitial) return viaInitial
  }
  return cov.byFinal.get(final.key) ?? null
}
