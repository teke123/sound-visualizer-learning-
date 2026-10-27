<script setup lang="ts">
/**
 * InitialMatrix：辅音（声母）音素矩阵（发音方法行 × 发音部位列，§2.3）。
 * 现代语音学口径：6 方法行（塞音 → 边近音，阻碍递减）× 7 被动部位列（唇 → 软腭）；
 * 塞音/塞擦音格内「左不送气 · 右送气」并排（普通话无清浊对立，送气才是对立特征）；
 * ŋ 仅作韵尾、y/w/ɥ 为零声母拼写（半元音），均以角标注明。
 * 纯展示组件：已开放关（LevelSummary[]）点亮对应单元格。
 */
import { computed } from 'vue'
import { QBtn } from 'quasar'
import type { LevelSummary } from '@/api'
import {
  INITIAL_PLACE_EN,
  INITIAL_PLACES,
  INITIALS,
  MANNER_ROWS,
  type InitialInfo,
} from '@/phonology/mandarin'
import { buildCoverage, matchesInitialQuery, normalizeQuery } from './matching'

const props = withDefaults(
  defineProps<{
    /** 已开放关（用于点亮） */
    levels: LevelSummary[]
    showIpa?: boolean
    /** 代表字显隐（与「显示 IPA」并列的展示开关） */
    showChar?: boolean
    /** 易混组高亮的声母键集合 */
    highlight?: string[] | null
    /** 搜索命中（拼音/IPA/代表字命中则高亮） */
    query?: string
  }>(),
  { showIpa: true, showChar: true, highlight: null, query: '' },
)

const emit = defineEmits<{ (e: 'select', initial: InitialInfo): void }>()

const query = computed(() => normalizeQuery(props.query ?? ''))
const hasQuery = computed(() => query.value.length > 0)
const highlightSet = computed(() => new Set(props.highlight ?? []))
const hasHighlight = computed(() => highlightSet.value.size > 0)

const byInitial = computed(() => buildCoverage(props.levels).byInitial)

/** 单元格在当前 query/highlight 下是否「命中」（多条件同时生效时取交集） */
function isHit(info: InitialInfo): boolean {
  if (hasQuery.value && !matchesInitialQuery(info, query.value, byInitial.value.get(info.key))) return false
  if (hasHighlight.value && !highlightSet.value.has(info.key)) return false
  return true
}

/** 同格排序：不送气在左、送气在右（塞音/塞擦音行的对立呈现），其余按键序 */
function cellSort(a: InitialInfo, b: InitialInfo): number {
  const rank = (i: InitialInfo) =>
    i.aspiration === 'unaspirated' ? 0 : i.aspiration === 'aspirated' ? 1 : 2
  return rank(a) - rank(b) || a.key.localeCompare(b.key)
}

const tableData = computed(() =>
  MANNER_ROWS.map((row) => ({
    row,
    cells: INITIAL_PLACES.map((place) => ({
      place,
      items: INITIALS.filter((i) => i.place === place && i.rowKey === row.key)
        .sort(cellSort)
        .map((info) => ({
          info,
          level: byInitial.value.get(info.key) ?? null,
          hit: isHit(info),
        })),
    })),
  })),
)

/** 角标：零声母拼写（y/w/yu）或仅作韵尾（ŋ） */
function badge(info: InitialInfo): string {
  if (info.codaOnly) return '仅作韵尾 -ng'
  if (info.zeroSpelling === 'y') return '零声母 y'
  if (info.zeroSpelling === 'w') return '零声母 w'
  if (info.zeroSpelling === 'yu') return '零声母 yu'
  return ''
}

const filterActive = computed(() => hasQuery.value || hasHighlight.value)
const totalHits = computed(() => INITIALS.filter((i) => isHit(i)).length)
const showEmpty = computed(() => filterActive.value && totalHits.value === 0)

function itemClass(item: { level: LevelSummary | null; hit: boolean }): { lit: boolean; hl: boolean } {
  return {
    lit: !!item.level,
    hl: item.hit && (hasQuery.value || hasHighlight.value),
  }
}
</script>

<template>
  <div class="im-matrix">
    <p v-if="showEmpty" class="im-empty">没有符合条件的辅音：换个关键词，或清除筛选再试。</p>
    <div v-else class="im-scroll">
      <table class="im-table">
        <thead>
          <tr>
            <th class="im-corner">发音方法 ＼ 发音部位</th>
            <th v-for="place in INITIAL_PLACES" :key="place">
              {{ place }}
              <span class="im-place-en">{{ INITIAL_PLACE_EN[place] }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="def in tableData" :key="def.row.key">
            <th class="im-rowhead">
              {{ def.row.label }}
              <span class="im-manner-en">{{ def.row.en }}</span>
            </th>
            <td v-for="entry in def.cells" :key="entry.place">
              <div v-if="entry.items.length > 0" class="im-cells">
                <QBtn
                  v-for="item in entry.items"
                  :key="item.info.key"
                  flat
                  no-caps
                  class="im-cell"
                  :class="itemClass(item)"
                  @click="emit('select', item.info)"
                >
                  <span class="im-pinyin">{{ item.info.key }}</span>
                  <span v-if="showIpa" class="im-ipa">[{{ item.info.ipa }}]</span>
                  <span v-if="showChar" class="im-char">{{ item.info.char }}</span>
                  <span v-if="badge(item.info)" class="im-badge">{{ badge(item.info) }}</span>
                </QBtn>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="im-legend">
        塞音 / 塞擦音格内「左不送气 · 右送气」；ŋ 不作音节起始、仅出现在 -ng 韵尾。
      </p>
    </div>
  </div>
</template>

<style scoped lang="sass">
.im-matrix
  display: flex
  flex-direction: column
  gap: 8px

.im-empty
  color: #90a4ae
  font-size: 14px
  padding: 24px 8px
  margin: 0
  text-align: center

.im-scroll
  overflow: auto
  border: 1px solid #eceff1
  border-radius: 12px
  background: #fff

.im-table
  border-collapse: separate
  border-spacing: 0
  width: max-content
  min-width: 100%

  thead th
    position: sticky
    top: 0
    z-index: 2
    background: #e6f2f0
    color: #37474f
    font-size: 13px
    font-weight: 600
    padding: 9px 8px
    white-space: nowrap
    border-bottom: 1px solid #cfe5e2
    border-right: 1px solid #f2f7f6

  .im-corner
    position: sticky
    left: 0
    z-index: 3
    min-width: 168px

  .im-rowhead
    position: sticky
    left: 0
    z-index: 1
    background: #fff
    text-align: left
    font-size: 13px
    font-weight: 500
    color: #546e7a
    white-space: nowrap
    padding: 8px 10px
    border-right: 1px solid #eceff1

  td
    padding: 4px
    border-bottom: 1px solid #f2f6f6
    border-right: 1px solid #f6f9f9
    vertical-align: top

.im-place-en
  display: block
  font-size: 10px
  font-weight: 400
  color: #90a4ae

.im-manner-en
  display: block
  font-size: 10px
  font-weight: 400
  color: #90a4ae

.im-cells
  display: flex
  gap: 4px
  flex-wrap: wrap

.im-cell
  display: flex
  flex-direction: column
  align-items: center
  gap: 2px
  min-height: 44px
  min-width: 64px
  padding: 6px 8px
  border: 1.5px solid #cfd8dc
  border-radius: 12px
  background: #fff
  &:hover
    border-color: #4db6ac
  &.lit
    border-color: #00897b
    background: #e0f2f1
  &.hl
    border-color: #0288d1
    box-shadow: 0 0 0 3px rgba(2, 136, 209, 0.22)

.im-pinyin
  font-size: 18px
  font-weight: 700
  color: #263238
  line-height: 1.1
  font-family: var(--font-ipa)

.im-ipa
  font-size: 11px
  color: #78909c
  font-family: var(--font-ipa)

.im-char
  font-size: 12px
  color: #546e7a

.im-badge
  font-size: 10px
  line-height: 1.2
  color: #4527a0
  background: #ede7f6
  border-radius: 999px
  padding: 1px 8px

.im-legend
  margin: 0
  padding: 8px 12px
  font-size: 12px
  color: #90a4ae
  border-top: 1px solid #f2f6f6
</style>
