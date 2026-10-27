<script setup lang="ts">
/**
 * ToneTable：声调表（§2.6）。行 = 四声，列 = 调型示意（SVG 五度折线）/ 调类 / 五度调值。
 */
import { computed } from 'vue'
import { TONES, type ToneInfo } from '@/phonology/mandarin'
import { normalizeQuery } from './matching'

const props = withDefaults(
  defineProps<{
    query?: string
  }>(),
  { query: '' },
)

const emit = defineEmits<{ (e: 'select', tone: ToneInfo): void }>()

const query = computed(() => normalizeQuery(props.query ?? ''))

function toneMatches(t: ToneInfo): boolean {
  if (!query.value) return true
  const texts = [t.name, t.value, t.ipa, t.shape, t.example, t.examplePinyin, String(t.index)]
  return texts.some((x) => x.toLowerCase().includes(query.value))
}

const rows = computed(() => TONES.filter(toneMatches))
const showEmpty = computed(() => rows.value.length === 0)

/** 五度调值 → SVG 折线坐标（d: 5=顶部 → 1=底部，横向按序展开） */
function contour(t: ToneInfo): string {
  const digits = [...t.value].map((ch) => Number(ch))
  const padX = 7
  const padY = 7
  const w = 46
  const h = 48
  const stepX = digits.length > 1 ? (w - 2 * padX) / (digits.length - 1) : 0
  return digits
    .map((d, i) => `${(padX + stepX * i).toFixed(1)},${(padY + ((h - 2 * padY) * (5 - d)) / 4).toFixed(1)}`)
    .join(' ')
}

/** 五度参考线（5..1） */
const REF_LINES = [5, 4, 3, 2, 1].map((d) => ({ d, y: 7 + (34 * (5 - d)) / 4 }))
</script>

<template>
  <div class="tt-table">
    <p v-if="showEmpty" class="tt-empty">没有符合条件的声调：换个关键词再试。</p>
    <div v-else class="tt-scroll">
      <table class="tt-rows">
        <thead>
          <tr>
            <th class="tt-head-shape">调型示意</th>
            <th>调类</th>
            <th>五度调值</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="tone in rows"
            :key="tone.index"
            class="tt-row"
            @click="emit('select', tone)"
          >
            <td class="tt-cell-shape">
              <svg viewBox="0 0 46 48" class="tt-svg" aria-hidden="true">
                <line
                  v-for="ref in REF_LINES"
                  :key="ref.d"
                  x1="7"
                  :y1="ref.y"
                  x2="39"
                  :y2="ref.y"
                  class="tt-ref"
                />
                <polyline :points="contour(tone)" class="tt-contour" />
              </svg>
            </td>
            <td class="tt-name">{{ tone.name }}</td>
            <td class="tt-value">{{ tone.value }} <span class="tt-ipa">[{{ tone.ipa }}]</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped lang="sass">
.tt-table
  display: flex
  flex-direction: column
  gap: 8px

.tt-empty
  color: #90a4ae
  font-size: 14px
  padding: 24px 8px
  margin: 0
  text-align: center

.tt-scroll
  overflow: auto
  border: 1px solid #eceff1
  border-radius: 12px
  background: #fff

.tt-rows
  border-collapse: separate
  border-spacing: 0
  width: 100%

  thead th
    position: sticky
    top: 0
    z-index: 2
    background: #e6f2f0
    color: #37474f
    font-size: 13px
    font-weight: 600
    text-align: left
    padding: 10px 12px
    border-bottom: 1px solid #cfe5e2

  tbody td
    padding: 10px 12px
    border-bottom: 1px solid #f2f6f6
    vertical-align: middle

.tt-row
  cursor: pointer
  &:hover
    background: #f5faf9

.tt-head-shape
  width: 72px

.tt-cell-shape
  width: 72px

.tt-svg
  width: 46px
  height: 48px
  display: block

.tt-ref
  stroke: #eceff1
  stroke-width: 1

.tt-contour
  fill: none
  stroke: #0288d1
  stroke-width: 3
  stroke-linecap: round
  stroke-linejoin: round

.tt-name
  font-size: 15px
  font-weight: 600
  color: #263238
  white-space: nowrap

.tt-value
  font-size: 16px
  font-weight: 700
  color: #01579b
  font-variant-numeric: tabular-nums

.tt-ipa
  font-size: 13px
  font-weight: 400
  color: #546e7a
  font-family: var(--font-ipa)
</style>
