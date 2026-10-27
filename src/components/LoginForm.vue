<script setup lang="ts">
/** LoginForm：登录（FR-107 / FR-102）：注册/登录即代表同意服务条款；表单内错误（INVALID_CREDENTIALS） */
import { ref } from 'vue'
import { QBtn, QInput } from 'quasar'
import { errorCopy } from '@/copy/usePageCopy'
import { useAuth, validatePassword, validateUsername } from '@/features/auth'

const props = defineProps<{
  /** 登录成功后的回跳目标（站内路径，调用方已 sanitize） */
  redirect?: string | null
}>()

const emit = defineEmits<{
  (e: 'success', payload: { redirect: string | null }): void
}>()

const auth = useAuth()
const username = ref('')
const password = ref('')
const usernameError = ref<string | null>(null)
const passwordError = ref<string | null>(null)

async function submit() {
  usernameError.value = validateUsername(username.value)
  passwordError.value = validatePassword(password.value)
  if (usernameError.value || passwordError.value) return
  const ok = await auth.login({ username: username.value, password: password.value })
  if (ok) emit('success', { redirect: props.redirect ?? null })
}
</script>

<template>
  <form class="auth-form" @submit.prevent="submit" novalidate>
    <h2>登录</h2>
    <p class="auth-note">登录即代表同意服务条款；本站不提供密码找回，忘记密码只能重新注册。</p>

    <QInput
      v-model="username"
      class="auth-field"
      outlined
      label="用户名"
      autocomplete="username"
      placeholder="3–32 位字母、数字、下划线或中文"
      :error="!!usernameError"
      :error-message="usernameError ?? ''"
    />
    <QInput
      v-model="password"
      class="auth-field"
      outlined
      type="password"
      label="密码"
      autocomplete="current-password"
      placeholder="至少 8 位"
      :error="!!passwordError"
      :error-message="passwordError ?? ''"
    />

    <p v-if="auth.error.value" class="form-error">{{ errorCopy(auth.error.value).title }}</p>

    <QBtn
      type="submit"
      class="auth-submit"
      unelevated
      no-caps
      color="primary"
      :label="auth.busy.value ? '登录中…' : '登录'"
      :disable="auth.busy.value"
    />
    <p class="auth-alt">
      还没有账号？
      <RouterLink :to="redirect ? `/account/register?redirect=${encodeURIComponent(redirect)}` : '/account/register'">
        去注册
      </RouterLink>
    </p>
  </form>
</template>

<style scoped lang="sass">
@use './auth-shared'

.auth-form
  max-width: 380px
  margin: 0 auto

  h2
    margin: 0 0 6px
</style>
