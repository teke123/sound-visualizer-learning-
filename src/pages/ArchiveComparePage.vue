<script setup lang="ts">
/** P10 /archive/compare?a=&b=：同关两条比较（仅已同意；404/422 → 不可见） */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ArchiveCompareView from '@/components/ArchiveCompareView.vue'
import PageState from '@/components/PageState.vue'
import { useContextStore } from '@/stores/context'

const route = useRoute()
const router = useRouter()
const contextStore = useContextStore()

const aId = computed(() => (typeof route.query.a === 'string' ? route.query.a : ''))
const bId = computed(() => (typeof route.query.b === 'string' ? route.query.b : ''))

const allowed = computed(() => contextStore.consentGranted)
</script>

<template>
  <div class="archive-compare-page">
    <PageState
      v-if="!allowed"
      state="forbidden"
      text="同关比较需要先登录并同意保存；比较仅限本人已存档记录。"
    />
    <PageState v-else-if="!aId || !bId" state="not-visible" text="缺少要比较的记录" />
    <ArchiveCompareView v-else :a-id="aId" :b-id="bId" @back="router.push('/archive')" />
  </div>
</template>

<style scoped lang="sass">
.archive-compare-page
  padding-bottom: 20px
</style>
