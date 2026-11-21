<script setup lang="ts">
/**
 * PageHead：全站统一页头（渐变图标方块 + 标题 + 可选说明）。
 * 外观定义在 src/css/theme.sass 的 .vs-page-head。
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
  font-size: 17px
  font-weight: 800
  letter-spacing: -0.01em
  line-height: 1.4
  margin: 0
  color: var(--vs-ink)
</style>
