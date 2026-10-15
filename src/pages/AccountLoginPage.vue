<script setup lang="ts">
/**
 * P11 /account/login（FD-08）：登录后回跳 redirect（只接受站内路径）；
 * 未处理同意的账号登录成功后立即弹出 ConsentDialog（FD-07）；
 * 已有同意账号登录触发的转存以提示呈现（§6.6）。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { TransferResult } from '@/api'
import LoginForm from '@/components/LoginForm.vue'
import ConsentDialog from '@/components/ConsentDialog.vue'
import { useConsent } from '@/features/consent'
import { sanitizeRedirect } from '@/utils'

const route = useRoute()
const router = useRouter()
const consent = useConsent()

const redirect = computed(() =>
  sanitizeRedirect(typeof route.query.redirect === 'string' ? route.query.redirect : null),
)

function onSuccess(payload: { redirect: string | null; needConsent: boolean; transfer?: TransferResult }) {
  if (payload.needConsent) void consent.openDialog()
  else if (payload.transfer) consent.showTransfer(payload.transfer)
  void router.push(payload.redirect ?? '/account')
}
</script>

<template>
  <div class="login-page">
    <LoginForm :redirect="redirect" @success="onSuccess" />
    <ConsentDialog />
  </div>
</template>

<style scoped lang="sass">
.login-page
  padding: 20px 0 40px
</style>
