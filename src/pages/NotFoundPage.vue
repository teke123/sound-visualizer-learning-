<script setup lang="ts">
/** NotFound：其余路径统一 404 */
import { QBtn } from 'quasar'
</script>

<template>
  <div class="not-found">
    <h1>页面不存在</h1>
    <p>这个地址没有对应的内容。</p>
    <QBtn unelevated no-caps color="teal-1" text-color="teal-9" label="回首页" to="/" class="nf-btn" />
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

.nf-btn
  margin-top: 12px
</style>
