<script setup lang="ts">
/** NotFound：其余路径统一 404（decision-map-frontend 路由表） */
</script>

<template>
  <div class="not-found">
    <h1>页面不存在</h1>
    <p>这个地址没有对应的内容。</p>
    <RouterLink to="/" class="nf-link">回首页</RouterLink>
  </div>
</template>

<style scoped lang="sass">
.not-found
  text-align: center
  padding: 60px 0
  h1
    font-size: 24px
    margin: 0 0 8px
  p
    color: #78909c

.nf-link
  display: inline-block
  margin-top: 12px
  min-height: 44px
  line-height: 44px
  padding: 0 24px
  border-radius: 999px
  background: #e0f2f1
  color: #00695c
  font-weight: 600
  text-decoration: none
</style>
