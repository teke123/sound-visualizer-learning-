<script setup lang="ts">
import type { AssessmentResult } from '@/api'

const props = defineProps<{ evidence: NonNullable<AssessmentResult['pronunciationEvidence']> }>()

function download(kind: 'measurements' | 'llm_input') {
  const value = kind === 'measurements' ? props.evidence.measurements : {
    ...props.evidence.llm_input,
    measurements: props.evidence.measurements,
    images: props.evidence.images,
  }
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${kind}.json`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>

<template>
  <details class="evidence">
    <summary>查看发音分析图像与数据</summary>
    <p v-if="evidence.status === 'unavailable'">分析状态：{{ evidence.reason }}</p>
    <template v-else>
      <div class="downloads">
        <button type="button" @click="download('measurements')">下载测量数据</button>
        <button type="button" @click="download('llm_input')">下载 AI 发音建议材料</button>
      </div>
      <figure v-for="image in evidence.images" :key="image.name">
        <img :src="image.data_url" :alt="image.name" loading="lazy" />
        <a :href="image.data_url" :download="image.name">下载图像</a>
      </figure>
    </template>
  </details>
</template>

<style scoped>
.evidence { padding: 16px; border: 1px solid #d6dfe3; border-radius: 8px; }
summary { cursor: pointer; font-weight: 600; }
.downloads { display: flex; gap: 12px; flex-wrap: wrap; }
button { padding: 8px 12px; cursor: pointer; }
figure { margin: 16px 0; }
img { display: block; width: 100%; background: white; }
p { line-height: 1.7; }
</style>
