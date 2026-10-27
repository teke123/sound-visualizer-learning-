<script setup lang="ts">
/**
 * P06 发音库（§2 音系表格化重构）：四张音系表（辅音声母 / 韵母+舌位图 / 音节表 / 声调）
 * 现代语音学口径：部位/方法用 IPA 通行术语，韵母按介音 × 韵尾（G-V-X）组织，
 * 正词法拼写规则收拢到页内折叠区。
 * + 搜索 / 易混组高亮 + 详情侧栏（选中后才展开，表格让位）+ 比较托盘（任选两关或易混对一键比较）。
 * 工具页：不承载进度（进度呈现归 P03）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { QBadge, QBtn, QCheckbox, QExpansionItem, QInput, QTab, QTabPanel, QTabPanels, QTabs } from 'quasar'
import { useLevelsStore } from '@/stores/levels'
import { useComparePanel } from '@/features/compare'
import ComparePanel from '@/components/ComparePanel.vue'
import PageState from '@/components/PageState.vue'
import InitialMatrix from '@/components/library/InitialMatrix.vue'
import FinalMatrix from '@/components/library/FinalMatrix.vue'
import SyllableMatrix from '@/components/library/SyllableMatrix.vue'
import ToneTable from '@/components/library/ToneTable.vue'
import SoundDetailPanel from '@/components/library/SoundDetailPanel.vue'
import { buildCoverage } from '@/components/library/matching'
import {
  CONFUSABLE_GROUPS,
  FINAL_BY_KEY,
  INITIAL_BY_KEY,
  type FinalInfo,
  type InitialInfo,
  type SyllableCell,
  type ToneInfo,
} from '@/phonology/mandarin'

const router = useRouter()
const levelsStore = useLevelsStore()
const compare = useComparePanel()

type LibraryView = 'initials' | 'finals' | 'syllables' | 'tones'
const VIEWS: Array<{ key: LibraryView; label: string }> = [
  { key: 'initials', label: '声母表' },
  { key: 'finals', label: '韵母表' },
  { key: 'syllables', label: '音节表' },
  { key: 'tones', label: '声调表' },
]

const view = ref<LibraryView>('initials')
const showChar = ref(true)
const showIpa = ref(true)
const query = ref('')
const activeGroupKey = ref<string | null>(null)

/** QTabs / QTabPanels 的 model-value 回写（string|number → LibraryView） */
function onViewChange(name: string | number) {
  view.value = name as LibraryView
}

type Selection =
  | { kind: 'initial'; initial: InitialInfo }
  | { kind: 'final'; final: FinalInfo }
  | { kind: 'tone'; tone: ToneInfo }
  | { kind: 'syllable'; initial: string; final: string; cell: SyllableCell }

const selection = ref<Selection | null>(null)
const selectedLevels = ref<string[]>([])

const levels = computed(() => levelsStore.published)
const activeGroup = computed(() => CONFUSABLE_GROUPS.find((g) => g.key === activeGroupKey.value) ?? null)

/** 易混组高亮：按视图拆分为声母键 / 韵母键集合（音节表两者并用） */
const initialHighlight = computed(() =>
  activeGroup.value && activeGroup.value.initials.length > 0 ? activeGroup.value.initials : null,
)
const finalHighlight = computed(() =>
  activeGroup.value && activeGroup.value.finals.length > 0 ? activeGroup.value.finals : null,
)
const syllableHighlight = computed(() =>
  activeGroup.value ? [...activeGroup.value.initials, ...activeGroup.value.finals] : null,
)

function toggleGroup(key: string) {
  activeGroupKey.value = activeGroupKey.value === key ? null : key
  // 易混组只作用于对应表：激活时自动切到相关视图，避免点了个寂寞
  const group = CONFUSABLE_GROUPS.find((g) => g.key === activeGroupKey.value)
  if (!group) return
  if (group.initials.length > 0 && group.finals.length === 0 && view.value === 'finals') {
    view.value = 'initials'
  } else if (group.finals.length > 0 && group.initials.length === 0 && view.value === 'initials') {
    view.value = 'finals'
  }
}

function selectInitial(initial: InitialInfo) {
  selection.value = { kind: 'initial', initial }
}
function selectFinal(final: FinalInfo) {
  selection.value = { kind: 'final', final }
}
function selectTone(tone: ToneInfo) {
  selection.value = { kind: 'tone', tone }
}
function selectSyllable(payload: { initial: string; final: string; cell: SyllableCell }) {
  selection.value = { kind: 'syllable', ...payload }
}
/** 元音舌位图点击 → 选中对应韵母并打开详情 */
function selectVowel(finalKey: string) {
  const final = FINAL_BY_KEY.get(finalKey)
  if (final) selection.value = { kind: 'final', final }
}
function closeDetail() {
  selection.value = null
}

const detailProps = computed(() => {
  const s = selection.value
  return {
    initial: s?.kind === 'initial' ? s.initial : null,
    final: s?.kind === 'final' ? s.final : null,
    tone: s?.kind === 'tone' ? s.tone : null,
    syllable:
      s?.kind === 'syllable' ? { initial: s.initial, final: s.final, cell: s.cell } : null,
  }
})
const detailOpen = computed(() => selection.value !== null)
const activeFinalKey = computed(() => (selection.value?.kind === 'final' ? selection.value.final.key : null))

function enterLevel(levelId: string) {
  void router.push(`/learn/${levelId}`)
}

/* ------------------------------ 比较托盘 ------------------------------ */

function addCompare(levelId: string) {
  if (selectedLevels.value.includes(levelId)) return
  selectedLevels.value = [...selectedLevels.value.slice(-1), levelId]
}
function removeCompare(levelId: string) {
  selectedLevels.value = selectedLevels.value.filter((id) => id !== levelId)
}
function runCompare() {
  const a = selectedLevels.value[0]
  const b = selectedLevels.value[1]
  if (!a || !b) return
  void compare.open(a, b)
}
function comparePair(aId: string, bId: string) {
  void compare.open(aId, bId)
}
function trayLabel(levelId: string): string {
  const level = levelsStore.byId.get(levelId)
  return level ? `${level.title}（${level.targetSound}）` : levelId
}

/** 易混组一键比较：pair 双方都有专属已开放关才可点，否则置灰「未开放」 */
const pairButtons = computed(() => {
  const group = activeGroup.value
  if (!group) return []
  const cov = buildCoverage(levels.value)
  return group.pairs.map(([a, b]) => {
    const levelA = cov.byInitial.get(a) ?? cov.byFinal.get(a) ?? null
    const levelB = cov.byInitial.get(b) ?? cov.byFinal.get(b) ?? null
    return { a, b, levelA, levelB, ready: levelA !== null && levelB !== null }
  })
})

function pairLabel(key: string): string {
  const info = INITIAL_BY_KEY.get(key) ?? FINAL_BY_KEY.get(key)
  return info ? `${key}「${info.char}」` : key
}

const compareOpen = computed(() => compare.pair.value !== null)

onMounted(() => {
  if (!levelsStore.loaded) void levelsStore.refresh()
})
</script>

<template>
  <div class="library-page">
    <header class="lib-head">
      <h1>发音库</h1>
      <QInput
        v-model="query"
        type="search"
        outlined
        rounded
        placeholder="搜拼音 / IPA / 代表字 / 关卡"
        aria-label="搜索发音库"
        class="lib-search"
      />
    </header>

    <div class="lib-controls">
      <QTabs
        :model-value="view"
        no-caps
        active-color="primary"
        indicator-color="primary"
        @update:model-value="onViewChange"
      >
        <QTab v-for="v in VIEWS" :key="v.key" :name="v.key" :label="v.label" no-caps />
      </QTabs>
      <div class="lib-filters">
        <QCheckbox v-model="showChar" label="显示汉字" class="lib-check" />
        <QCheckbox v-model="showIpa" label="显示 IPA" class="lib-check" />
      </div>
      <div class="lib-groups">
        <span class="groups-label">易混组</span>
        <QBtn
          v-for="g in CONFUSABLE_GROUPS"
          :key="g.key"
          no-caps
          :color="activeGroupKey === g.key ? 'teal-1' : 'blue-grey-4'"
          :text-color="activeGroupKey === g.key ? 'teal-9' : 'blue-grey-9'"
          :unelevated="activeGroupKey === g.key"
          :outline="activeGroupKey !== g.key"
          :title="g.hint"
          :aria-pressed="activeGroupKey === g.key"
          @click="toggleGroup(g.key)"
        >
          {{ g.name }}
        </QBtn>
      </div>
    </div>

    <PageState v-if="levelsStore.loading && !levelsStore.loaded" state="loading" />
    <PageState
      v-else-if="levelsStore.error && levelsStore.levels.length === 0"
      state="error"
      :error="levelsStore.error"
      @retry="levelsStore.refresh()"
    />
    <div v-else class="lib-main">
      <div class="lib-table-zone">
        <QTabPanels :model-value="view" animated @update:model-value="onViewChange">
          <QTabPanel name="initials" class="q-pa-none">
            <InitialMatrix
              :levels="levels"
              :show-ipa="showIpa"
              :show-char="showChar"
              :highlight="initialHighlight"
              :query="query"
              @select="selectInitial"
            />
          </QTabPanel>
          <QTabPanel name="finals" class="q-pa-none">
            <FinalMatrix
              :levels="levels"
              :show-ipa="showIpa"
              :show-char="showChar"
              :highlight="finalHighlight"
              :query="query"
              :active-final-key="activeFinalKey"
              @select="selectFinal"
              @select-vowel="selectVowel"
            />
          </QTabPanel>
          <QTabPanel name="syllables" class="q-pa-none">
            <SyllableMatrix
              :levels="levels"
              :show-ipa="showIpa"
              :show-char="showChar"
              :highlight="syllableHighlight"
              :query="query"
              @select="selectSyllable"
            />
          </QTabPanel>
          <QTabPanel name="tones" class="q-pa-none">
            <ToneTable :query="query" @select="selectTone" />
          </QTabPanel>
        </QTabPanels>
      </div>
      <div v-if="detailOpen" class="lib-side">
        <SoundDetailPanel
          :open="detailOpen"
          :initial="detailProps.initial"
          :final="detailProps.final"
          :tone="detailProps.tone"
          :syllable="detailProps.syllable"
          :levels="levels"
          @close="closeDetail"
          @enter-level="enterLevel"
          @add-compare="addCompare"
        />
      </div>
    </div>

    <!-- 正词法说明：拼音拼写规则与语音学分类解耦（严式 IPA 与拼写的映射收拢于此） -->
    <QExpansionItem class="lib-ortho" label="拼音正词法与拼写规则" header-class="lib-ortho-header">
      <ul class="lib-ortho-list">
        <li>y / w 隔音改写：零声母 i / u 系韵母前加 y / w（衣 yi、乌 wu、呀 ya、挖 wa）；ü 系改 y 并省两点（鱼 yu、月 yue、元 yuan、云 yun）。</li>
        <li>省写：iou / uei / uen 与声母相拼时省作 iu / ui / un（六 liu、贵 gui、温 wen → 论 lun）。</li>
        <li>ü 省两点：j / q / x 后 ü 省分音符（居 ju、缺 que、军 jun）。</li>
        <li>本页 IPA 为严式标音：介音记 [j / w / ɥ]，双元音韵尾加不成音节号 ◌̯（如 [ai̯]）；-i 为成音节辅音 [z̩ / ʐ̩]；r 主标卷舌近音 [ɻ]。</li>
      </ul>
    </QExpansionItem>

    <section
      v-if="selectedLevels.length > 0 || pairButtons.length > 0"
      class="lib-tray"
      aria-label="比较托盘"
    >
      <div v-if="selectedLevels.length > 0" class="tray-items">
        <template v-for="(id, idx) in selectedLevels" :key="id">
          <span v-if="idx === 1" class="tray-vs">vs</span>
          <span class="tray-item">
            {{ trayLabel(id) }}
            <QBtn
              flat
              round
              dense
              color="secondary"
              icon="close"
              :aria-label="`移除 ${trayLabel(id)}`"
              @click="removeCompare(id)"
            />
          </span>
        </template>
        <QBtn
          unelevated
          no-caps
          color="primary"
          label="并排比较"
          :disable="selectedLevels.length !== 2"
          @click="runCompare"
        />
      </div>
      <div v-if="pairButtons.length > 0" class="tray-pairs">
        <span class="pairs-label">{{ activeGroup?.name }} · 一键比较</span>
        <QBtn
          v-for="p in pairButtons"
          :key="`${p.a}-${p.b}`"
          outline
          no-caps
          :color="p.ready ? 'blue-grey-4' : 'blue-grey-3'"
          :text-color="p.ready ? 'blue-grey-9' : 'blue-grey-6'"
          :disable="!p.ready"
          :title="p.ready ? `${p.levelA?.title} vs ${p.levelB?.title}` : '该对立组尚未开放关卡'"
          @click="p.ready && p.levelA && p.levelB && comparePair(p.levelA.id, p.levelB.id)"
        >
          {{ pairLabel(p.a) }} vs {{ pairLabel(p.b) }}
          <QBadge v-if="!p.ready" class="pair-off" outline color="blue-grey-4" label="未开放" />
        </QBtn>
      </div>
    </section>

    <ComparePanel
      :open="compareOpen"
      :detail-a="compare.detailA.value"
      :detail-b="compare.detailB.value"
      :loading="compare.loading.value"
      :error="compare.error.value"
      @close="compare.close()"
    />
  </div>
</template>

<style scoped lang="sass">
.library-page
  display: flex
  flex-direction: column
  gap: 18px

.lib-head
  display: flex
  justify-content: space-between
  align-items: center
  gap: 12px
  flex-wrap: wrap
  h1
    margin: 0
    font-size: 24px

.lib-search
  width: min(340px, 100%)

.lib-controls
  display: flex
  flex-direction: column
  gap: 10px

.lib-filters
  display: flex
  align-items: center
  gap: 16px
  flex-wrap: wrap

.lib-check
  // QCheckbox 行高对齐筛选项
  min-height: 44px

.lib-groups
  display: flex
  align-items: center
  gap: 8px
  flex-wrap: wrap

.groups-label
  font-size: 13px
  color: #78909c

.lib-main
  display: flex
  gap: 16px
  align-items: flex-start

// 正词法折叠区：折叠交互由 QExpansionItem 提供，容器保持卡片外观
.lib-ortho
  border: 1px solid #eceff1
  border-radius: 12px
  background: #fff
  overflow: hidden

// QExpansionItem 的 header 是其内部元素，需 :deep() 才能命中
.lib-ortho :deep(.lib-ortho-header)
  font-size: 14px
  color: #546e7a

.lib-ortho-list
  margin: 0 16px 12px
  padding-left: 20px
  display: flex
  flex-direction: column
  gap: 6px
  li
    font-size: 13px
    color: #607d8b
    line-height: 1.6
    font-family: var(--font-ipa)

.lib-table-zone
  flex: 1 1 640px
  min-width: 0

.lib-side
  flex: 0 0 320px
  width: 320px
  position: sticky
  top: 16px

@media (max-width: 1080px)
  .lib-main
    flex-direction: column
  .lib-side
    position: static
    width: 100%
    flex: 1 1 auto

.lib-tray
  border: 1px solid #eceff1
  border-radius: 12px
  background: #fff
  padding: 12px 14px
  display: flex
  flex-direction: column
  gap: 10px

.tray-items
  display: flex
  align-items: center
  gap: 10px
  flex-wrap: wrap

.tray-item
  display: inline-flex
  align-items: center
  gap: 6px
  background: #e0f2f1
  color: #00695c
  border-radius: 999px
  padding: 4px 6px 4px 14px
  font-size: 14px
  max-width: 100%

.tray-vs
  color: #90a4ae
  font-size: 13px

.tray-pairs
  display: flex
  align-items: center
  gap: 8px
  flex-wrap: wrap

.pairs-label
  font-size: 13px
  color: #78909c

.pair-off
  margin-left: 8px
  font-size: 11px
</style>
