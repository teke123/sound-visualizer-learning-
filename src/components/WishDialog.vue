<script setup lang="ts">
/** WishDialog：希望增加的音/字（FR-1501 / FR-304），提交带 searchQuery；429 显示等待时间 */
import { ref, watch } from 'vue'
import { QDialog } from 'quasar'
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
    <div class="wish-dialog" role="dialog" aria-label="希望增加">
      <h2>希望增加什么音或字？</h2>
      <p class="wish-hint">告诉我们你想学的内容，我们会优先考虑制作。</p>
      <textarea
        v-model="content"
        class="wish-input"
        rows="3"
        placeholder="例如：希望增加「ang」的练习"
        :disabled="wish.submitted.value"
      ></textarea>
      <p v-if="wish.submitted.value" class="wish-ok">已收到你的建议，谢谢！</p>
      <p v-else-if="wish.error.value" class="wish-error">
        {{ errorCopy(wish.error.value).title }}
        <template v-if="wish.waitSeconds.value">（约 {{ wish.waitSeconds.value }} 秒后可再次提交）</template>
      </p>
      <div class="wish-actions">
        <button type="button" class="wish-btn" @click="emit('close')">关闭</button>
        <button
          type="button"
          class="wish-btn primary"
          :disabled="!content.trim() || wish.submitting.value || wish.submitted.value"
          @click="submit"
        >
          提交
        </button>
      </div>
    </div>
  </QDialog>
</template>

<style scoped lang="sass">
.wish-dialog
  background: #fff
  border-radius: 14px
  padding: 20px
  width: min(460px, 92vw)

  h2
    margin: 0 0 6px
    font-size: 18px

.wish-hint
  font-size: 13px
  color: #90a4ae
  margin: 0 0 10px

.wish-input
  width: 100%
  border: 1px solid #cfd8dc
  border-radius: 8px
  padding: 8px 12px
  font-size: 15px
  box-sizing: border-box
  resize: vertical

.wish-ok
  color: #2e7d32
  font-size: 14px

.wish-error
  color: #c62828
  font-size: 14px

.wish-actions
  display: flex
  justify-content: flex-end
  gap: 10px
  margin-top: 12px

.wish-btn
  min-height: 44px
  padding: 4px 20px
  border-radius: 8px
  border: 1px solid #90a4ae
  background: #fff
  cursor: pointer
  &.primary
    background: #00897b
    border-color: #00897b
    color: #fff
    font-weight: 600
  &:disabled
    opacity: 0.5
    cursor: default
</style>
