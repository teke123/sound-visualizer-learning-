<script setup lang="ts">
/**
 * SyllableMatrix：音节表（§2.5）。
 * 行 = SYLLABLE_INITIAL_ORDER（21 声母按部位分组 + 零声母 Ø），
 * 列 = FINALS_COMBINING 按介音分组（组表头 colspan）。
 * 点亮口径（cellLevelFor）：音节关优先，其次声母关（Ø 行经 y/w 拼写关），
 * 最后韵母关——声母关 b 同时点亮 bo/bai/ban…，韵母关 a 点亮整列 ba/ma/Ø+a。
 */
import { computed } from 'vue'
import { QBtn } from 'quasar'
import type { LevelSummary } from '@/api'
import {
  FINALS_COMBINING,
  HU_LABELS,
  HU_ORDER,
  INITIAL_BY_KEY,
  SYLLABLES,
  SYLLABLE_INITIAL_ORDER,
  finalSortKey,
  type FinalInfo,
  type Hu,
  type SyllableCell,
} from '@/phonology/mandarin'
import { buildCoverage, cellLevelFor, matchesSyllableQuery, normalizeQuery } from './matching'

const props = withDefaults(
  defineProps<{
    levels: LevelSummary[]
    /** 列/行首 IPA 展示开关（单元格本身无 IPA） */
    showIpa?: boolean
    /** 代表字显隐（与「显示 IPA」并列的展示开关） */
    showChar?: boolean
    /** 可同时含声母与韵母键：行命中 = 声母键在集合或该行有列命中，列同理 */
    highlight?: string[] | null
    query?: string
  }>(),
  { showIpa: true, showChar: true, highlight: null, query: '' },
)

const emit = defineEmits<{
  (e: 'select', payload: { initial: string; final: string; cell: SyllableCell }): void
}>()

const query = computed(() => normalizeQuery(props.query ?? ''))
const hasQuery = computed(() => query.value.length > 0)
const highlightSet = computed(() => new Set(props.highlight ?? []))
const hasHighlight = computed(() => highlightSet.value.size > 0)

const coverage = computed(() => buildCoverage(props.levels))

/** 可拼合韵母列（按介音 × 韵尾行排序）与介音分组（静态） */
const ALL_COLUMNS: FinalInfo[] = [...FINALS_COMBINING].sort((a, b) => finalSortKey(a) - finalSortKey(b))
const COLUMN_GROUPS: Array<{ hu: Hu; columns: FinalInfo[] }> = HU_ORDER.map((hu) => ({
  hu,
  columns: ALL_COLUMNS.filter((c) => c.hu === hu),
})).filter((g) => g.columns.length > 0)

function cellEntry(initialKey: string, final: FinalInfo) {
  const cell = SYLLABLES[initialKey]?.[final.key]
  if (!cell) return null
  const level = cellLevelFor(coverage.value, initialKey, final)
  return { cell, level }
}

function isCellHit(initialKey: string, finalKey: string, cell: SyllableCell, level: LevelSummary | null): boolean {
  if (hasQuery.value && !matchesSyllableQuery(initialKey, finalKey, cell, query.value, level)) return false
  if (
    hasHighlight.value &&
    !highlightSet.value.has(initialKey) &&
    !highlightSet.value.has(finalKey)
  ) {
    return false
  }
  return true
}

const tableData = computed(() => {
  const columns = ALL_COLUMNS
  const groups = COLUMN_GROUPS
  let totalHits = 0
  const rows = SYLLABLE_INITIAL_ORDER.map((ik) => {
    const info = ik ? (INITIAL_BY_KEY.get(ik) ?? null) : null
    const cells = columns.map((col) => {
      const entry = cellEntry(ik, col)
      if (!entry) return null
      if (isCellHit(ik, col.key, entry.cell, entry.level)) totalHits += 1
      return {
        col,
        cell: entry.cell,
        level: entry.level,
        hl: highlightSet.value.has(ik) || highlightSet.value.has(col.key),
      }
    })
    return { key: ik, label: ik || 'Ø', ipa: info?.ipa ?? '', cells }
  })
  return { groups, columns, rows, totalHits }
})

const filterActive = computed(() => hasQuery.value || hasHighlight.value)
const showEmpty = computed(() => filterActive.value && tableData.value.totalHits === 0)

function cellClass(cell: { level: LevelSummary | null; hl: boolean }): {
  lit: boolean
  hl: boolean
} {
  return {
    lit: !!cell.level,
    hl: cell.hl && hasHighlight.value,
  }
}

/** 列首韵母 IPA：舌尖 -i 列一键两音，标为成音节辅音 z̩/ʐ̩ */
function colIpa(col: FinalInfo): string {
  return col.key === '-i' ? 'z̩/ʐ̩' : col.ipa
}
</script>

<template>
  <div class="sm-matrix">
    <p v-if="showEmpty" class="sm-empty">没有符合条件的音节：换个关键词，或清除筛选再试。</p>
    <div v-else class="sm-scroll">
      <table class="sm-table">
        <thead>
          <tr class="sm-hu-row">
            <th class="sm-corner" rowspan="2">声母 ＼ 韵母</th>
            <th v-for="g in tableData.groups" :key="g.hu" :colspan="g.columns.length" class="sm-hu-head">
              {{ HU_LABELS[g.hu] }}
            </th>
          </tr>
          <tr class="sm-col-row">
            <th v-for="col in tableData.columns" :key="col.key" class="sm-col-head">
              {{ col.key }}
              <span v-if="showIpa" class="sm-col-ipa">[{{ colIpa(col) }}]</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in tableData.rows" :key="row.key || 'zero'">
            <th class="sm-rowhead">
              <span class="sm-row-pinyin">{{ row.label }}</span>
              <span v-if="showIpa && row.ipa" class="sm-row-ipa">[{{ row.ipa }}]</span>
            </th>
            <td v-for="(cell, idx) in row.cells" :key="tableData.columns[idx]?.key ?? `empty-${idx}`">
              <QBtn
                v-if="cell"
                flat
                no-caps
                class="sm-cell"
                :class="cellClass(cell)"
                @click="emit('select', { initial: row.key, final: cell.col.key, cell: cell.cell })"
              >
                <span class="sm-pinyin">{{ cell.cell.pinyin }}</span>
                <span v-if="showChar" class="sm-char">{{ cell.cell.char }}</span>
              </QBtn>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped lang="sass">
.sm-matrix
  display: flex
  flex-direction: column
  gap: 8px

.sm-empty
  color: #90a4ae
  font-size: 14px
  padding: 24px 8px
  margin: 0
  text-align: center

.sm-scroll
  overflow: auto
  border: 1px solid #eceff1
  border-radius: 12px
  background: #fff

.sm-table
  border-collapse: separate
  border-spacing: 0
  width: max-content

  .sm-hu-row th
    position: sticky
    top: 0
    z-index: 2
    background: #dcedec
    color: #37474f
    font-size: 12px
    font-weight: 600
    padding: 6px 6px
    height: 30px
    white-space: nowrap
    border-bottom: 1px solid #cfe5e2
    border-right: 1px solid #f2f7f6

  .sm-col-row th
    position: sticky
    top: 30px
    z-index: 2
    background: #e6f2f0
    color: #546e7a
    font-size: 12px
    font-weight: 600
    padding: 5px 4px
    height: 30px
    white-space: nowrap
    border-bottom: 1px solid #cfe5e2
    border-right: 1px solid #f2f7f6

  .sm-corner
    position: sticky
    left: 0
    z-index: 4
    min-width: 96px

  .sm-rowhead
    position: sticky
    left: 0
    z-index: 1
    background: #fff
    text-align: center
    padding: 4px 8px
    border-right: 1px solid #eceff1
    border-bottom: 1px solid #f2f6f6
    white-space: nowrap

  td
    padding: 3px
    border-bottom: 1px solid #f2f6f6
    border-right: 1px solid #f6f9f9

.sm-row-pinyin
  display: block
  font-size: 15px
  font-weight: 700
  color: #263238
  font-family: var(--font-ipa)

.sm-row-ipa
  display: block
  font-size: 10px
  color: #90a4ae
  font-family: var(--font-ipa)

.sm-col-ipa
  display: block
  font-size: 9px
  font-weight: 400
  color: #90a4ae
  font-family: var(--font-ipa)

.sm-cell
  display: flex
  flex-direction: column
  align-items: center
  gap: 1px
  min-height: 44px
  min-width: 62px
  padding: 4px 6px
  border: 1.5px solid #e1e8e7
  border-radius: 10px
  background: #fff
  &:hover
    border-color: #4db6ac
  &.lit
    border-color: #00897b
    background: #e0f2f1
  &.hl
    border-color: #0288d1
    box-shadow: 0 0 0 2px rgba(2, 136, 209, 0.22)

.sm-pinyin
  font-size: 14px
  font-weight: 600
  color: #263238
  line-height: 1.15
  font-family: var(--font-ipa)

.sm-char
  font-size: 11px
  color: #546e7a
</style>
