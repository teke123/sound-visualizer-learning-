<script setup lang="ts">
/** NotFound：其余路径统一 404 */
import AppIcon from '@/components/ui/AppIcon.vue'
</script>

<template>
  <div class="not-found">
    <span class="nf-mark"><AppIcon name="search" size="lg" /></span>
    <h1>页面不存在</h1>
    <p>这个地址没有对应的内容。回到首页，或从发音地图重新找一关。</p>
    <RouterLink to="/" class="vs-btn">回首页</RouterLink>
  </div>
</template>

<style scoped lang="sass">
.not-found
  text-align: center
  padding: 72px 24px
  display: flex
  flex-direction: column
  align-items: center
  gap: 10px
  h1
    font-size: 24px
    font-weight: 900
    margin: 0
  p
    color: var(--vs-sub)
    font-size: 14px
    margin: 0 0 8px

.nf-mark
  width: 56px
  height: 56px
  border-radius: 8px
  display: flex
  align-items: center
  justify-content: center
  background: var(--vs-soft)
  color: var(--vs-brand)
  margin-bottom: 4px
</style>
