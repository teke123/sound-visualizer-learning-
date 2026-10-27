<script setup lang="ts">
/** RegisterForm：注册（FR-107）：用户名 3–32 唯一、密码 ≥8、可选填方言区/母语背景与性别；
 * 注册即代表同意服务条款、不自动登录；USERNAME_TAKEN 表单内错误 */
import { ref } from 'vue'
import { QBtn, QInput } from 'quasar'
import { ApiError } from '@/api'
import { errorCopy } from '@/copy/usePageCopy'
import { useAuth, validatePassword, validateUsername } from '@/features/auth'
import DialectSelector from './DialectSelector.vue'
import GenderSelector from './GenderSelector.vue'

const props = defineProps<{
  redirect?: string | null
}>()

const emit = defineEmits<{ (e: 'success', redirect: string | null): void }>()

const auth = useAuth()
const username = ref('')
const password = ref('')
const password2 = ref('')
const dialect = ref('')
const gender = ref('')
const usernameError = ref<string | null>(null)
const passwordError = ref<string | null>(null)
const password2Error = ref<string | null>(null)
const registered = ref(false)

async function submit() {
  usernameError.value = validateUsername(username.value)
  passwordError.value = validatePassword(password.value)
  password2Error.value = password.value === password2.value ? null : '两次输入的密码不一致'
  if (usernameError.value || passwordError.value || password2Error.value) return
  const ok = await auth.register({
    username: username.value,
    password: password.value,
    dialectBackground: dialect.value || null,
    gender: gender.value || null,
  })
  if (ok) registered.value = true
}

const usernameTaken = () => auth.error.value instanceof ApiError && auth.error.value.code === 'USERNAME_TAKEN'
</script>

<template>
  <form class="auth-form" @submit.prevent="submit" novalidate>
    <h2>注册</h2>
    <p class="auth-note">注册即代表同意服务条款。账号只用于保存你的学习进度与录音；不收集邮箱或手机号，也不提供密码找回。注册不会自动登录。</p>

    <div v-if="registered" class="register-ok">
      <p>✅ 注册成功。现在去登录吧。</p>
      <RouterLink
        class="register-login-link"
        :to="redirect ? `/account/login?redirect=${encodeURIComponent(redirect)}` : '/account/login'"
      >
        去登录
      </RouterLink>
    </div>

    <template v-else>
      <QInput
        v-model="username"
        class="auth-field"
        outlined
        label="用户名"
        autocomplete="username"
        placeholder="3–32 位字母、数字、下划线或中文"
        :error="!!usernameError || usernameTaken()"
        :error-message="usernameError ?? (usernameTaken() ? errorCopy(auth.error.value).title : '')"
      />
      <QInput
        v-model="password"
        class="auth-field"
        outlined
        type="password"
        label="密码"
        autocomplete="new-password"
        placeholder="至少 8 位"
        :error="!!passwordError"
        :error-message="passwordError ?? ''"
      />
      <QInput
        v-model="password2"
        class="auth-field"
        outlined
        type="password"
        label="再输入一次密码"
        autocomplete="new-password"
        :error="!!password2Error"
        :error-message="password2Error ?? ''"
      />
      <DialectSelector v-model="dialect" />
      <GenderSelector v-model="gender" />

      <p v-if="auth.error.value && !usernameTaken()" class="form-error">{{ errorCopy(auth.error.value).title }}</p>

      <QBtn
        type="submit"
        class="auth-submit"
        unelevated
        no-caps
        color="primary"
        :label="auth.busy.value ? '注册中…' : '注册'"
        :disable="auth.busy.value"
      />
      <p class="auth-alt">
        已有账号？
        <RouterLink :to="redirect ? `/account/login?redirect=${encodeURIComponent(redirect)}` : '/account/login'">
          去登录
        </RouterLink>
      </p>
    </template>
  </form>
</template>

<style scoped lang="sass">
@use './auth-shared'

.auth-form
  max-width: 380px
  margin: 0 auto

  h2
    margin: 0 0 6px

.register-ok
  background: #e8f5e9
  border: 1px solid #a5d6a7
  border-radius: 10px
  padding: 16px
  text-align: center
  display: flex
  flex-direction: column
  gap: 10px
  p
    margin: 0
    color: #1b5e20

.register-login-link
  color: #00897b
  font-weight: 700
</style>
