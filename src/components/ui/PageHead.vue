<script setup lang="ts">
/**
 * PageHead：全站统一页头（渐变图标方块 + 标题 + 一句说明）。
 * 外观定义在 src/css/theme.sass 的 .vs-page-head，页面只需给标题、说明与图标名。
 */
import AppIcon from './AppIcon.vue'

withDefaults(
  defineProps<{
    title: string
    desc?: string
    icon?: string
    /** 标题层级：页面主标题默认 h1，嵌入区块用 h2 */
    as?: 'h1' | 'h2'
  }>(),
  { icon: 'wave', as: 'h1' },
)
</script>

<template>
  <header class="vs-page-head">
    <span class="vs-mark"><AppIcon :name="icon" size="sm" /></span>
    <div class="head-text">
      <component :is="as">{{ title }}</component>
      <p v-if="desc">{{ desc }}</p>
    </div>
  </header>
</template>

<style scoped lang="sass">
.vs-page-head h1,
.vs-page-head h2
  font-family: var(--vs-font-display)
  font-size: 32px
  font-weight: 600
  letter-spacing: -0.02em
  line-height: 1.26
  margin: 0

@media (max-width: 900px)
  .vs-page-head h1,
  .vs-page-head h2
    font-size: 24px
</style>
