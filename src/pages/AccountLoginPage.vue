<script setup lang="ts">
/** P11 /account/login：登录后回跳 redirect（只接受站内路径） */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LoginForm from '@/components/LoginForm.vue'
import { sanitizeRedirect } from '@/utils'

const route = useRoute()
const router = useRouter()

const redirect = computed(() =>
  sanitizeRedirect(typeof route.query.redirect === 'string' ? route.query.redirect : null),
)

function onSuccess(payload: { redirect: string | null }) {
  void router.push(payload.redirect ?? '/account')
}
</script>

<template>
  <div class="login-page">
    <LoginForm :redirect="redirect" @success="onSuccess" />
  </div>
</template>

<style scoped lang="sass">
.login-page
  padding: 20px 0 40px
</style>
