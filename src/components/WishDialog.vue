<script setup lang="ts">
/** WishDialog：希望增加的音/字（FR-1501 / FR-304），提交带 searchQuery；429 显示等待时间 */
import { ref, watch } from 'vue'
import { QBtn, QCard, QCardActions, QCardSection, QDialog, QInput } from 'quasar'
import { errorCopy } from '@/copy/usePageCopy'
import { useWish } from '@/features/feedback'

const props = defineProps<{
  open: boolean
  searchQuery?: string
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const wish = useWish()
const content = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) {
      content.value = ''
      wish.submitted.value = false
      wish.error.value = null
      wish.waitSeconds.value = null
    }
  },
)

async function submit() {
  const text = content.value.trim()
  if (!text) return
  const ok = await wish.submit(text, props.searchQuery)
  if (ok) content.value = ''
}
</script>

<template>
  <QDialog :model-value="open" @update:model-value="(value: boolean) => !value && emit('close')">
    <QCard flat bordered class="wish-dialog" style="width: min(460px, 92vw)" role="dialog" aria-label="希望增加">
      <QCardSection>
        <h2>希望增加什么音或字？</h2>
        <p class="wish-hint">告诉我们你想学的内容，我们会优先考虑制作。</p>
        <QInput
          v-model="content"
          class="wish-input"
          outlined
          type="textarea"
          rows="3"
          placeholder="例如：希望增加「ang」的练习"
          :disable="wish.submitted.value"
        />
        <p v-if="wish.submitted.value" class="wish-ok">已收到你的建议，谢谢！</p>
        <p v-else-if="wish.error.value" class="wish-error">
          {{ errorCopy(wish.error.value).title }}
          <template v-if="wish.waitSeconds.value">（约 {{ wish.waitSeconds.value }} 秒后可再次提交）</template>
        </p>
      </QCardSection>
      <QCardActions align="right">
        <QBtn
          outline
          no-caps
          color="blue-grey-4"
          text-color="blue-grey-9"
          class="wish-close"
          label="关闭"
          @click="emit('close')"
        />
        <QBtn
          unelevated
          no-caps
          color="primary"
          label="提交"
          :disable="!content.trim() || wish.submitting.value || wish.submitted.value"
          @click="submit"
        />
      </QCardActions>
    </QCard>
  </QDialog>
</template>

<style scoped lang="sass">
.wish-dialog
  h2
    margin: 0 0 6px
    font-size: 18px

/* 原 .wish-btn 灰描边（#90a4ae）8px 圆角 44px 高 */
.wish-close
  border-radius: 8px
  min-height: 44px

.wish-hint
  font-size: 13px
  color: #90a4ae
  margin: 0 0 10px

.wish-ok
  color: #2e7d32
  font-size: 14px

.wish-error
  color: #c62828
  font-size: 14px
</style>
