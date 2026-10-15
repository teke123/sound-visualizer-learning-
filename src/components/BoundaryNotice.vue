<script setup lang="ts">
/** BoundaryNotice：边界句常驻（首页与 P09） */
import { BOUNDARY_NOTE } from '@/copy/usePageCopy'
</script>

<template>
  <aside class="boundary-notice" role="note">
    <span aria-hidden="true">ℹ️</span>
    <span>{{ BOUNDARY_NOTE }}</span>
  </aside>
</template>

<style scoped lang="sass">
.boundary-notice
  display: flex
  align-items: center
  gap: 8px
  justify-content: center
  padding: 10px 14px
  background: #fff8e1
  border: 1px solid #ffe082
  border-radius: 8px
  color: #795548
  font-size: 13px
</style>
