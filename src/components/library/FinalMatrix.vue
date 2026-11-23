<script setup lang="ts">
/**
 * FinalMatrix：韵母表（韵尾类型行 × 介音类型列，§2.4）+ 内嵌元音舌位图（VowelChart，见组件注释）。
 * G-V-X 韵母结构：行 = 韵尾（-Ø / -i̯ / -u̯ / -n / -ŋ），列 = 介音（Ø- / j- / w- / ɥ-，对应传统四呼）。
 * 单元格含该 (韵尾行, 介音列) 的全部韵母小项（拼音 + IPA + 代表字 + 省写提示）。
 */
import { computed } from 'vue'
import { QBtn, QCard, QCardSection } from 'quasar'
import type { LevelSummary } from '@/api'
import {
  FINAL_CELLS,
  FINAL_ROWS,
  HU_LABELS,
  HU_ORDER,
  type Hu,
  type FinalInfo,
} from '@/phonology/mandarin'
import { buildCoverage, matchesFinalQuery, normalizeQuery } from './matching'
import VowelChart from './VowelChart.vue'

const props = withDefaults(
  defineProps<{
    levels: LevelSummary[]
    showIpa?: boolean
    /** 代表字显隐（与「显示 IPA」并列的展示开关） */
    showChar?: boolean
    /** 易混组高亮的韵母键集合 */
    highlight?: string[] | null
    query?: string
    /** 与外部选中韵母联动（舌位图高亮） */
    activeFinalKey?: string | null
  }>(),
  {
    showIpa: true,
    showChar: true,
    highlight: null,
    query: '',
    activeFinalKey: null,
  },
)

const emit = defineEmits<{
  (e: 'select', final: FinalInfo): void
  (e: 'selectVowel', finalKey: string): void
}>()

const query = computed(() => normalizeQuery(props.query ?? ''))
const hasQuery = computed(() => query.value.length > 0)
const highlightSet = computed(() => new Set(props.highlight ?? []))
const hasHighlight = computed(() => highlightSet.value.size > 0)

const byFinal = computed(() => buildCoverage(props.levels).byFinal)

function isHit(info: FinalInfo): boolean {
  const level = byFinal.value.get(info.key)
  if (hasQuery.value && !matchesFinalQuery(info, query.value, level)) return false
  if (hasHighlight.value && !highlightSet.value.has(info.key)) return false
  return true
}

/* ------------------------------ 韵母表 ------------------------------ */

/** (rowKey|hu) → 韵母条目（静态数据，保持 FINAL_CELLS 顺序） */
const GROUPED: ReadonlyMap<string, FinalInfo[]> = (() => {
  const map = new Map<string, FinalInfo[]>()
  for (const f of FINAL_CELLS) {
    const key = `${f.rowKey}|${f.hu}`
    const list = map.get(key) ?? []
    list.push(f)
    map.set(key, list)
  }
  return map
})()

interface FinalItem {
  info: FinalInfo
  level: LevelSummary | null
  hit: boolean
}

const tableData = computed(() => {
  const hus: Hu[] = [...HU_ORDER]
  const rows = FINAL_ROWS.map((row) => ({
    row,
    cells: hus.map((hu) => ({
      hu,
      items: (GROUPED.get(`${row.key}|${hu}`) ?? []).map((info) => ({
        info,
        level: byFinal.value.get(info.key) ?? null,
        hit: isHit(info),
      })),
    })),
  }))
  return { hus, rows }
})

const filterActive = computed(() => hasQuery.value || hasHighlight.value)
const totalHits = computed(() => FINAL_CELLS.filter((f) => isHit(f)).length)
const showEmpty = computed(() => filterActive.value && totalHits.value === 0)

function itemClass(item: FinalItem): { lit: boolean; hl: boolean; active: boolean } {
  return {
    lit: !!item.level,
    hl: item.hit && (hasQuery.value || hasHighlight.value),
    active: props.activeFinalKey === item.info.key,
  }
}

/* ----------------------------- 元音舌位图 ----------------------------- */

/** 舌位图命中键：搜索或易混组命中即点亮（不受四呼 / 结构筛选影响） */
const vowelHitKeys = computed(() => {
  const keys = new Set<string>()
  if (!hasQuery.value && !hasHighlight.value) return keys
  for (const f of FINAL_CELLS) {
    if (highlightSet.value.has(f.key)) keys.add(f.key)
    else if (hasQuery.value && matchesFinalQuery(f, query.value, byFinal.value.get(f.key))) {
      keys.add(f.key)
    }
  }
  return keys
})
</script>

<template>
  <div class="fm-matrix">
    <p v-if="showEmpty" class="fm-empty">没有符合条件的韵母：换个关键词，或清除筛选再试。</p>
    <div v-else class="fm-body">
      <div class="fm-table-zone">
        <div class="fm-scroll">
          <table class="fm-table">
            <thead>
              <tr>
                <th class="fm-corner">韵尾 ＼ 介音</th>
                <th v-for="hu in tableData.hus" :key="hu">{{ HU_LABELS[hu] }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="def in tableData.rows" :key="def.row.key">
                <th class="fm-rowhead">
                  {{ def.row.label }}
                  <span class="fm-coda">{{ def.row.coda }}</span>
                </th>
                <td v-for="entry in def.cells" :key="entry.hu">
                  <div v-if="entry.items.length > 0" class="fm-items">
                    <QBtn
                      v-for="item in entry.items"
                      :key="`${item.info.key}-${item.info.apicalVariant ?? item.info.ipa}`"
                      flat
                      no-caps
                      class="fm-item"
                      :class="itemClass(item)"
                      @click="emit('select', item.info)"
                    >
                      <span class="fm-pinyin">{{ item.info.key }}<span v-if="item.info.spelling" class="fm-spell">({{ item.info.spelling }})</span></span>
                      <span v-if="showIpa" class="fm-ipa">[{{ item.info.ipa }}]</span>
                      <span v-if="showChar" class="fm-char">{{ item.info.char }}</span>
                    </QBtn>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <QCard flat bordered class="fm-vowel" aria-label="元音舌位图">
        <QCardSection class="fm-vowel-body">
          <VowelChart
            :active-key="activeFinalKey"
            :hit-keys="vowelHitKeys"
            @select-vowel="emit('selectVowel', $event)"
          />
        </QCardSection>
      </QCard>
    </div>
  </div>
</template>

<style scoped lang="sass">
.fm-matrix
  display: flex
  flex-direction: column
  gap: 8px

.fm-empty
  color: var(--vs-mute)
  font-size: 14px
  padding: 24px 8px
  margin: 0
  text-align: center

.fm-body
  display: flex
  gap: 16px
  align-items: flex-start
  flex-wrap: wrap

.fm-table-zone
  flex: 1 1 620px
  min-width: 0

.fm-scroll
  overflow: auto
  border: 1px solid var(--vs-line)
  border-radius: 12px
  background: var(--vs-card)

.fm-table
  border-collapse: separate
  border-spacing: 0
  width: max-content
  min-width: 100%

  thead th
    position: sticky
    top: 0
    z-index: 2
    background: var(--vs-soft-2)
    color: var(--vs-ink)
    font-size: 13px
    font-weight: 600
    padding: 9px 10px
    white-space: nowrap
    border-bottom: 1px solid var(--vs-line)
    border-right: 1px solid var(--vs-soft-2)

  .fm-corner
    position: sticky
    left: 0
    z-index: 3
    min-width: 128px

  .fm-rowhead
    position: sticky
    left: 0
    z-index: 1
    background: var(--vs-card)
    text-align: left
    font-size: 13px
    font-weight: 500
    color: var(--vs-sub)
    white-space: nowrap
    padding: 8px 10px
    border-right: 1px solid var(--vs-line)
    font-family: var(--font-ipa)

  .fm-coda
    display: inline-block
    margin-left: 6px
    font-size: 11px
    font-weight: 600
    color: var(--vs-coffee)
    background: var(--vs-soft)
    border-radius: 999px
    padding: 1px 8px
    font-family: var(--font-ipa)

  td
    padding: 5px
    border-bottom: 1px solid var(--vs-soft-2)
    border-right: 1px solid var(--vs-card)
    vertical-align: top
    min-width: 96px

.fm-items
  display: flex
  flex-wrap: wrap
  gap: 6px

.fm-item
  display: flex
  flex-direction: column
  align-items: center
  gap: 2px
  min-height: 44px
  padding: 5px 10px
  border: 1.5px solid var(--vs-line2)
  border-radius: 8px
  background: var(--vs-card)
  &:hover
    border-color: var(--vs-sand)
  &.lit
    border-color: var(--vs-line-strong)
  &.hl
    border-color: var(--vs-brand)
    box-shadow: 0 0 0 3px rgba(var(--vs-brand-rgb), 0.18)
  &.active
    border-color: var(--vs-coffee)
    box-shadow: 0 0 0 3px rgba(74, 51, 35, 0.16)

.fm-pinyin
  font-size: 16px
  font-weight: 700
  color: var(--vs-ink)
  line-height: 1.1
  font-family: var(--font-ipa)

.fm-spell
  font-size: 11px
  font-weight: 400
  color: var(--vs-mute)

.fm-ipa
  font-size: 11px
  color: var(--vs-mute)
  font-family: var(--font-ipa)

.fm-char
  font-size: 12px
  color: var(--vs-sub)

/* ------------------------------ 元音舌位图 ------------------------------ */

.fm-vowel
  flex: 0 1 400px
  min-width: 320px

.fm-vowel-body
  padding: 12px 14px
</style>
