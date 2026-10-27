<script setup lang="ts">
/**
 * GenderSelector：性别选择器（FR-107）。
 * 纯选填：'' 表示未填写；注册表单与 P11 账号页共用。
 */
import { QSelect } from 'quasar'
import { GENDER_OPTIONS } from '@/features/auth'

const model = defineModel<string>({ default: '' })

/** QSelect 选项：首项「不填写」对应 ''（未填写语义与原 <option value=""> 一致） */
const options: ReadonlyArray<{ label: string; value: string }> = [
  { label: '不填写', value: '' },
  ...GENDER_OPTIONS,
]
</script>

<template>
  <label class="gender-field">
    <span class="gender-label">性别</span>
    <QSelect v-model="model" class="gender-select" outlined emit-value map-options :options="options" />
  </label>
</template>

<style scoped lang="sass">
.gender-field
  display: flex
  flex-direction: column
  gap: 6px

.gender-label
  font-size: 14px
  color: #37474f
</style>
