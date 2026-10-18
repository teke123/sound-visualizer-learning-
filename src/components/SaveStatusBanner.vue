<script setup lang="ts">
/** SaveStatusBanner：保存状态横幅（P09）：本次录音与检测结果自动保存到声音档案（FR-1008） */
</script>

<template>
  <aside class="save-banner" aria-label="保存状态">
    <p class="banner-title">✅ 已自动保存到声音档案</p>
    <p class="banner-sub">可在「声音档案」中回看、删除，或与之前的记录比较。</p>
    <RouterLink to="/archive" class="banner-link">去档案看看 →</RouterLink>
  </aside>
</template>

<style scoped lang="sass">
.save-banner
  background: #e8f5e9
  border: 1px solid #a5d6a7
  border-radius: 10px
  padding: 12px 16px

.banner-title
  margin: 0
  font-weight: 700
  font-size: 14px

.banner-sub
  margin: 4px 0 0
  font-size: 13px
  color: #37474f

.banner-link
  color: #2e7d32
  font-size: 14px
  font-weight: 600
</style>
