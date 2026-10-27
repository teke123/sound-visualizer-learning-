<script setup lang="ts">
/**
 * SoundDetailPanel：选中音详情侧栏（§2.7）。
 * 三种选中源三选一非空：initial / final / tone / syllable。
 * 命中已开放关时拉取 LevelDetail（contentApi.level），
 * 展示范例试听（DemoPlayer）、构形（ArticulationFigure，限高 260px）与说明；
 * 未命中显示「暂无专属关卡 · 后续开放」。
 */
import { computed, ref, watch } from 'vue'
import { QBtn, QCard, QCardSection } from 'quasar'
import { contentApi, mediaUrl, type LevelDetail, type LevelSummary } from '@/api'
import DemoPlayer from '@/components/DemoPlayer.vue'
import ArticulationFigure from '@/renderers/ArticulationFigure.vue'
import {
  FINAL_BY_KEY,
  INITIAL_BY_KEY,
  finalLabels,
  initialLabels,
  syllableIpa,
  type FinalInfo,
  type InitialInfo,
  type SyllableCell,
  type ToneInfo,
} from '@/phonology/mandarin'
import { buildCoverage, cellLevelFor, toneLevelFor } from './matching'

const props = withDefaults(
  defineProps<{
    open: boolean
    initial?: InitialInfo | null
    final?: FinalInfo | null
    tone?: ToneInfo | null
    syllable?: { initial: string; final: string; cell: SyllableCell } | null
    levels: LevelSummary[]
  }>(),
  { initial: null, final: null, tone: null, syllable: null },
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'enterLevel', levelId: string): void
  (e: 'addCompare', levelId: string): void
}>()

const coverage = computed(() => buildCoverage(props.levels))

const head = computed(() => {
  if (props.initial) {
    const i = props.initial
    return { pinyin: i.key, ipa: i.ipa, char: i.char, labels: initialLabels(i) }
  }
  if (props.final) {
    const f = props.final
    return {
      pinyin: f.spelling ? `${f.key}(${f.spelling})` : f.key,
      ipa: f.ipa,
      char: f.char,
      labels: finalLabels(f),
    }
  }
  if (props.syllable) {
    const s = props.syllable
    const ini = s.initial ? (INITIAL_BY_KEY.get(s.initial) ?? null) : null
    const fin = FINAL_BY_KEY.get(s.final) ?? null
    return {
      pinyin: s.cell.pinyin,
      // 零声母直接韵母 IPA（不带 Ø）；舌尖 -i 按声母取 z̩/ʐ̩/ɻ̩（zh/ch/sh → ʐ̩，r → ɻ̩）
      ipa: syllableIpa(s.initial, fin),
      char: s.cell.char,
      labels: [...(ini ? initialLabels(ini) : ['零声母']), ...(fin ? finalLabels(fin) : [])],
    }
  }
  if (props.tone) {
    const t = props.tone
    return {
      pinyin: t.examplePinyin,
      ipa: t.ipa,
      char: t.example,
      labels: [t.name, t.shape, `五度调值 ${t.value}`],
    }
  }
  return null
})

/** 命中关卡：专属声母/韵母关优先，音节关兜底（声母/韵母坐标）；音节按拼合表同口径（音节关→声母关→韵母关）；声调按四声覆盖 */
const matchedLevel = computed<LevelSummary | null>(() => {
  const c = coverage.value
  if (props.initial) {
    return c.byInitial.get(props.initial.key) ?? c.anyInitial.get(props.initial.key) ?? null
  }
  if (props.final) {
    return c.byFinal.get(props.final.key) ?? c.anyFinal.get(props.final.key) ?? null
  }
  if (props.syllable) {
    const fin = FINAL_BY_KEY.get(props.syllable.final)
    return fin ? cellLevelFor(c, props.syllable.initial, fin) : null
  }
  if (props.tone) {
    return toneLevelFor(props.levels, props.tone.index) ?? null
  }
  return null
})

const detail = ref<LevelDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref<unknown>(null)
let fetchSeq = 0

watch(
  () => matchedLevel.value?.id ?? null,
  async (levelId) => {
    const seq = ++fetchSeq
    detail.value = null
    detailError.value = null
    detailLoading.value = false
    if (!levelId) return
    detailLoading.value = true
    try {
      const res = await contentApi.level(levelId)
      if (seq !== fetchSeq) return
      detail.value = res.data
    } catch (err) {
      if (seq !== fetchSeq) return
      detailError.value = err
    } finally {
      if (seq === fetchSeq) detailLoading.value = false
    }
  },
  { immediate: true },
)
</script>

<template>
  <QCard v-if="open && head" flat bordered class="sdp" aria-label="选中音详情">
    <QCardSection class="sdp-body">
      <header class="sdp-head">
        <div class="sdp-title">
          <span class="sdp-pinyin">{{ head.pinyin }}</span>
          <span class="sdp-ipa">[{{ head.ipa }}]</span>
        </div>
        <QBtn flat round class="sdp-close" aria-label="关闭详情" @click="emit('close')">✕</QBtn>
      </header>
      <p class="sdp-char">代表字「{{ head.char }}」</p>
      <div class="sdp-labels">
        <span v-for="label in head.labels" :key="label" class="sdp-label">{{ label }}</span>
      </div>

      <section class="sdp-level">
        <template v-if="matchedLevel">
          <p class="sdp-level-name">{{ matchedLevel.id }} · {{ matchedLevel.title }}</p>
          <p v-if="detailLoading" class="sdp-hint">正在加载关卡内容…</p>
          <p v-else-if="detailError" class="sdp-hint error">关卡内容加载失败，稍后再试。</p>
          <template v-else-if="detail">
            <DemoPlayer :items="detail.demos ?? []" :media-resolver="mediaUrl" />
            <div class="sdp-figure">
              <ArticulationFigure :articulation="detail.articulation" :media-resolver="mediaUrl" />
            </div>
          </template>
          <div class="sdp-actions">
            <QBtn
              unelevated
              no-caps
              rounded
              color="primary"
              class="sdp-btn"
              @click="emit('enterLevel', matchedLevel.id)"
            >
              进入关卡训练
            </QBtn>
            <QBtn
              outline
              no-caps
              rounded
              color="primary"
              text-color="teal-9"
              class="sdp-btn"
              @click="emit('addCompare', matchedLevel.id)"
            >
              加入比较
            </QBtn>
          </div>
        </template>
        <p v-else class="sdp-none">暂无专属关卡 · 后续开放</p>
      </section>
    </QCardSection>
  </QCard>
</template>

<style scoped lang="sass">
.sdp
  width: 100%

.sdp-body
  display: flex
  flex-direction: column
  gap: 10px

.sdp-head
  display: flex
  justify-content: space-between
  align-items: flex-start
  gap: 8px

.sdp-title
  display: flex
  align-items: baseline
  gap: 8px
  flex-wrap: wrap

.sdp-pinyin
  font-size: 26px
  font-weight: 700
  color: #00695c
  font-family: var(--font-ipa)

.sdp-ipa
  font-size: 15px
  color: #78909c
  font-family: var(--font-ipa)

.sdp-close
  min-width: 44px
  min-height: 44px
  font-size: 16px
  color: #78909c

.sdp-char
  margin: 0
  font-size: 16px
  color: #37474f

.sdp-labels
  display: flex
  flex-wrap: wrap
  gap: 6px

.sdp-label
  font-size: 12px
  color: #4527a0
  background: #ede7f6
  border-radius: 999px
  padding: 2px 10px

.sdp-level
  display: flex
  flex-direction: column
  gap: 10px

.sdp-level-name
  margin: 0
  font-size: 13px
  font-weight: 600
  color: #00695c

.sdp-hint
  margin: 0
  font-size: 13px
  color: #90a4ae
  &.error
    color: #c62828

.sdp-figure
  max-height: 260px
  overflow: auto

.sdp-actions
  display: flex
  flex-wrap: wrap
  gap: 8px

.sdp-btn
  flex: 1 1 auto
  min-height: 44px

.sdp-none
  margin: 0
  padding: 18px 0
  text-align: center
  color: #b0bec5
  font-size: 14px
</style>
