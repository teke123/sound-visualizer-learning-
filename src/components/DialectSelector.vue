<script setup lang="ts">
/**
 * DialectSelector：方言区/母语背景选择器（FR-107 / FD-06）。
 * 纯选填：'' 表示未填写；注册表单与 P11 账号页共用。
 */
import { DIALECT_OPTIONS } from '@/features/auth'

const model = defineModel<string>({ default: '' })
</script>

<template>
  <label class="dialect-field">
    <span class="dialect-label">
      方言区 / 母语背景
      <em>选填，帮助反馈更贴合你的口音背景</em>
    </span>
    <select v-model="model" class="dialect-select">
      <option value="">不填写</option>
      <option v-for="option in DIALECT_OPTIONS" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
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
  em
    font-style: normal
    font-size: 12px
    color: #90a4ae
    margin-left: 6px

.dialect-select
  min-height: 44px
  padding: 6px 12px
  border-radius: 8px
  border: 1px solid #cfd8dc
  background: #fff
  font-size: 15px
  color: #37474f
  &:focus
    outline: 2px solid #00897b
    outline-offset: 1px
</style>
