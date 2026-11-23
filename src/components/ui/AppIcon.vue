<script setup lang="ts">
/**
 * AppIcon：引用 App.vue 中注入一次的 Lucide 图标 sprite。
 * 全站统一 2px 描边、圆角端点，尺寸走 theme.sass 的 .vs-ico / .vs-ico--sm / .vs-ico--lg。
 */
withDefaults(
  defineProps<{
    /** sprite 名称（不含 vs-i- 前缀），见 App.vue 的 symbol 列表 */
    name: string
    size?: 'sm' | 'md' | 'lg'
    /** 有语义时提供；纯装饰默认对读屏隐藏 */
    label?: string
  }>(),
  { size: 'md' },
)
</script>

<template>
  <svg
    class="vs-ico"
    :class="size === 'sm' ? 'vs-ico--sm' : size === 'lg' ? 'vs-ico--lg' : ''"
    :role="label ? 'img' : undefined"
    :aria-label="label"
    :aria-hidden="label ? undefined : 'true'"
    focusable="false"
  >
    <use :href="`#vs-i-${name}`" />
  </svg>
</template>
