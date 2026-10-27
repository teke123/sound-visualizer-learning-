<script setup lang="ts">
/** DangerConfirmDialog：删除 / 清空 / 撤回 / 注销二次确认；注销要求输入密码（NFR 防错反馈） */
import { ref, watch } from 'vue'
import { QBtn, QCard, QCardActions, QCardSection, QDialog, QInput } from 'quasar'

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
    <QCard
      flat
      bordered
      class="danger-dialog"
      style="width: min(460px, 92vw)"
      role="alertdialog"
      :aria-label="title"
    >
      <QCardSection>
        <h2>{{ title }}</h2>
        <p class="danger-message">{{ message }}</p>
        <QInput
          v-if="requirePassword"
          v-model="password"
          class="danger-password"
          outlined
          type="password"
          label="请输入当前密码确认"
          autocomplete="current-password"
          :error="!!error"
          :error-message="error || ''"
        />
        <p v-if="error && !requirePassword" class="danger-error">{{ error }}</p>
      </QCardSection>
      <QCardActions align="right">
        <QBtn
          outline
          no-caps
          color="blue-grey-4"
          text-color="blue-grey-9"
          class="danger-cancel"
          label="再想想"
          @click="emit('cancel')"
        />
        <QBtn
          unelevated
          no-caps
          color="negative"
          :label="confirmLabel ?? '确认执行'"
          :disable="busy || (requirePassword && !password)"
          @click="confirm"
        />
      </QCardActions>
    </QCard>
  </QDialog>
</template>

<style scoped lang="sass">
.danger-dialog
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

/* 原 .danger-btn 灰描边（#90a4ae）8px 圆角 44px 高 */
.danger-cancel
  border-radius: 8px
  min-height: 44px

.danger-error
  color: #c62828
  font-size: 13px
</style>
