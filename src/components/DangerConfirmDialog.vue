<script setup lang="ts">
/** DangerConfirmDialog：删除 / 清空 / 撤回 / 注销二次确认；注销要求输入密码（NFR 防错反馈） */
import { ref, watch } from 'vue'
import { QDialog } from 'quasar'

const props = defineProps<{
  open: boolean
  title: string
  /** 说明将删除的范围等后果 */
  message: string
  confirmLabel?: string
  /** 注销等场景要求输入密码 */
  requirePassword?: boolean
  busy?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  (e: 'confirm', password?: string): void
  (e: 'cancel'): void
}>()

const password = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) password.value = ''
  },
)

function confirm() {
  emit('confirm', props.requirePassword ? password.value : undefined)
}
</script>

<template>
  <QDialog :model-value="open" persistent @update:model-value="(value: boolean) => !value && emit('cancel')">
    <div class="danger-dialog" role="alertdialog" :aria-label="title">
      <h2>{{ title }}</h2>
      <p class="danger-message">{{ message }}</p>
      <div v-if="requirePassword" class="danger-password">
        <label for="danger-password">请输入当前密码确认</label>
        <input id="danger-password" v-model="password" type="password" autocomplete="current-password" />
      </div>
      <p v-if="error" class="danger-error">{{ error }}</p>
      <div class="danger-actions">
        <button type="button" class="danger-btn" @click="emit('cancel')">再想想</button>
        <button
          type="button"
          class="danger-btn danger"
          :disabled="busy || (requirePassword && !password)"
          @click="confirm"
        >
          {{ confirmLabel ?? '确认执行' }}
        </button>
      </div>
    </div>
  </QDialog>
</template>

<style scoped lang="sass">
.danger-dialog
  background: #fff
  border-radius: 14px
  padding: 20px
  width: min(460px, 92vw)

  h2
    margin: 0 0 8px
    font-size: 18px
    color: #b71c1c

.danger-message
  font-size: 14px
  color: #455a64
  line-height: 1.8
  white-space: pre-line

.danger-password
  margin-top: 12px
  display: flex
  flex-direction: column
  gap: 6px
  label
    font-size: 13px
    color: #78909c
  input
    min-height: 44px
    border: 1px solid #cfd8dc
    border-radius: 8px
    padding: 6px 12px
    font-size: 15px

.danger-error
  color: #c62828
  font-size: 13px

.danger-actions
  display: flex
  justify-content: flex-end
  gap: 10px
  margin-top: 16px

.danger-btn
  min-height: 44px
  padding: 6px 20px
  border-radius: 8px
  border: 1px solid #90a4ae
  background: #fff
  cursor: pointer
  &.danger
    background: #c62828
    border-color: #c62828
    color: #fff
    font-weight: 600
  &:disabled
    opacity: 0.5
    cursor: default
</style>
