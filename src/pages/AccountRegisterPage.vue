<script setup lang="ts">
/** P11 /account/register（FD-08）：注册不自动登录；成功后带 redirect 去登录 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import RegisterForm from '@/components/RegisterForm.vue'
import { sanitizeRedirect } from '@/utils'

const route = useRoute()
const redirect = computed(() =>
  sanitizeRedirect(typeof route.query.redirect === 'string' ? route.query.redirect : null),
)
</script>

<template>
  <div class="register-page">
    <RegisterForm :redirect="redirect" />
  </div>
</template>

<style scoped lang="sass">
.register-page
  padding: 20px 0 40px
</style>
