<script setup lang="ts">
import { ref, watch } from 'vue'
import { useDocumentVisibility } from '@vueuse/core'
import { DEFAULT_RETRY_AFTER_MS, detectionApi, type PronunciationAdviceResult } from '@/api'

const props = defineProps<{ recordingId: string; headingLevel: 'h2' | 'h3' }>()
const advice = ref<PronunciationAdviceResult>({ status: 'pending', items: [] })
const visibility = useDocumentVisibility()
const parts = { initial: '声母', final: '韵母', tone: '声调' }
const reasons = {
  poor_audio: '这次录音里听不清这个部位，可以在安静一点的地方再录一次。',
  insufficient_evidence: '这次录音还不足以判断具体偏差，可以再读一遍。',
  conflicting_evidence: '这次还无法可靠判断具体偏差，可以再录一次。',
}

watch(() => props.recordingId, () => {
  advice.value = { status: 'pending', items: [] }
}, { flush: 'sync' })

watch([() => props.recordingId, visibility], ([id, state], _, onCleanup) => {
  if (state !== 'visible' || advice.value.status !== 'pending') return
  const controller = new AbortController()
  let timer: number | undefined
  onCleanup(() => {
    controller.abort()
    window.clearTimeout(timer)
  })

  async function fetchAdvice() {
    try {
      const { data } = await detectionApi.getPronunciationAdvice(id, controller.signal)
      if (controller.signal.aborted) return
      advice.value = data
      if (data.status === 'pending') {
        timer = window.setTimeout(() => void fetchAdvice(), DEFAULT_RETRY_AFTER_MS)
      }
    } catch {
      if (!controller.signal.aborted) advice.value = { status: 'unavailable', items: [] }
    }
  }

  void fetchAdvice()
}, { immediate: true })
</script>

<template>
  <section class="advice-section" aria-label="本次发音建议">
    <component :is="headingLevel">本次发音建议</component>
    <p v-if="advice.status === 'pending'" class="advice-state">正在生成建议…</p>
    <div aria-live="polite">
      <p v-if="advice.status === 'unavailable'" class="advice-state">这次暂时无法生成发音建议。</p>
      <ul v-else-if="advice.status === 'ready'" class="advice-items">
        <li v-for="item in advice.items" :key="`${item.index}-${item.part}`">
          <strong>{{ item.text }}（{{ item.pinyin }}）· {{ parts[item.part] }}</strong>
          <template v-if="item.status === 'explained'">
            <p><b>偏误分析：</b>{{ item.analysis }}</p>
            <p><b>下次怎么做：</b>{{ item.nextAction }}</p>
          </template>
          <p v-else>{{ reasons[item.reasonCode] }}</p>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped lang="sass">
.advice-section
  padding: 12px 0
  border-block: 1px solid var(--vs-line, #e4e7eb)
  overflow-wrap: anywhere
  h2, h3
    margin: 0 0 10px
    font-weight: 900
    line-height: 1.5
    letter-spacing: 0
  h2
    font-size: 20px
  h3
    font-size: 17px

.advice-state, .advice-items p
  margin: 4px 0 0
  line-height: 1.65

.advice-items
  display: grid
  gap: 12px
  list-style: none
  margin: 0
  padding: 0
</style>
