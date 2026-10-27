<script setup lang="ts">
/**
 * DialectSelector：方言区/母语背景选择器（FR-107 / FD-06）。
 * 纯选填：'' 表示未填写；注册表单与 P11 账号页共用。
 */
import { QSelect } from 'quasar'
import { DIALECT_OPTIONS } from '@/features/auth'

const model = defineModel<string>({ default: '' })

/** QSelect 选项：首项「不填写」对应 ''（未填写语义与原 <option value=""> 一致） */
const options: ReadonlyArray<{ label: string; value: string }> = [
  { label: '不填写', value: '' },
  ...DIALECT_OPTIONS,
]
</script>

<template>
  <label class="dialect-field">
    <span class="dialect-label">方言区 / 母语背景</span>
    <QSelect v-model="model" class="dialect-select" outlined emit-value map-options :options="options" />
  </label>
</template>

<style scoped lang="sass">
.dialect-field
  display: flex
  flex-direction: column
  gap: 6px

.dialect-label
  font-size: 14px
  color: #37474f
</style>
