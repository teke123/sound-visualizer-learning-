<script setup lang="ts">
/**
 * P11 账号页（FR-106 / FR-102–108）：
 * 未登录 → 注册 / 登录入口与说明；已登录 → 退出、重新标定、
 * 清空档案入口、注销（密码确认 + 二次确认）。
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useContextStore } from '@/stores/context'
import { useAuth } from '@/features/auth'
import { useCalibration } from '@/features/calibration'
import { errorCopy } from '@/copy/usePageCopy'
import CalibrationPanel from '@/components/CalibrationPanel.vue'
import DangerConfirmDialog from '@/components/DangerConfirmDialog.vue'

const router = useRouter()
const route = useRoute()
const contextStore = useContextStore()
const auth = useAuth()

const deleteOpen = ref(false)
const clearArchiveOpen = ref(false)
const recalibrateOpen = ref(false)

// FR-1006：结果页「去标定」直达 #calibration 锚点时自动打开标定面板
watch(
  () => route.hash,
  (hash) => {
    if (hash === '#calibration' && contextStore.isAuthenticated) recalibrateOpen.value = true
  },
  { immediate: true },
)

const calibration = useCalibration()

const authenticated = computed(() => contextStore.isAuthenticated)

async function logout() {
  await auth.logout()
  await router.push('/')
}

/** 注销：密码确认 + 全会话失效（FR-108） */
async function confirmDeleteAccount(password?: string) {
  const ok = await auth.deleteAccount(password ?? '')
  if (ok) {
    deleteOpen.value = false
    auth.finishAccountDeletion()
    await router.push('/')
  }
}

/** 清空档案：跳转 P10（删除范围与注销不同） */
function openClearArchive() {
  void router.push('/archive')
}
</script>

<template>
  <div class="account-page">
    <h1>账号</h1>

    <!-- 未登录 -->
    <section v-if="!authenticated" class="guest-panel">
      <p class="guest-note">注册并登录后使用：学习进度与录音结果自动保存到你的账号。注册 / 登录即代表同意服务条款。</p>
      <div class="guest-actions">
        <RouterLink to="/account/login" class="acc-btn primary">登录</RouterLink>
        <RouterLink to="/account/register" class="acc-btn">注册</RouterLink>
      </div>
      <ul class="guest-facts">
        <li>用户名 + 密码即可，不收集邮箱或手机号</li>
        <li>不提供密码找回：忘记密码只能重新注册</li>
      </ul>
    </section>

    <!-- 已登录 -->
    <section v-else class="profile-card">
      <h2>{{ contextStore.context.username }}</h2>
      <p class="cal-status">
        音域：{{ contextStore.context.calibration.status === 'personal' ? '已标定（个人音域）' : '未标定（可在录音前标定，也可跳过）' }}
      </p>

      <div class="profile-actions">
        <button type="button" class="acc-btn" @click="recalibrateOpen = true">重新标定音域</button>
        <button type="button" class="acc-btn" @click="openClearArchive">删除录音 / 清空档案</button>
        <button type="button" class="acc-btn" @click="logout">退出登录</button>
        <button type="button" class="acc-btn danger" @click="deleteOpen = true">注销账号</button>
      </div>
    </section>

    <!-- 注销确认（输入密码 + 二次确认） -->
    <DangerConfirmDialog
      :open="deleteOpen"
      title="注销账号？"
      message="将删除该账号的全部录音档案、学习进度与音域数据，并删除账号、失效全部登录会话；用户名不再可用。此操作不可恢复。"
      confirm-label="确认注销"
      require-password
      :busy="auth.busy.value"
      :error="auth.error.value ? errorCopy(auth.error.value).title : null"
      @confirm="confirmDeleteAccount"
      @cancel="deleteOpen = false"
    />

    <DangerConfirmDialog
      :open="clearArchiveOpen"
      title="清空全部档案？"
      message="只删除已存档录音与结果；学习进度与音域保留。"
      confirm-label="去档案页操作"
      @confirm="clearArchiveOpen = false; openClearArchive()"
      @cancel="clearArchiveOpen = false"
    />

    <!-- 重新标定（P11 主动打开；FR-1006） -->
    <CalibrationPanel :open="recalibrateOpen" @done="recalibrateOpen = false" @cancel="recalibrateOpen = false" />
  </div>
</template>

<style scoped lang="sass">
.account-page
  max-width: 640px
  margin: 0 auto
  display: flex
  flex-direction: column
  gap: 20px

  h1
    margin: 0
    font-size: 24px

.guest-panel
  background: #fff
  border: 1px solid #eceff1
  border-radius: 14px
  padding: 20px

.guest-note
  color: #546e7a
  font-size: 14px
  margin: 0 0 14px

.guest-actions
  display: flex
  gap: 10px

.guest-facts
  margin: 16px 0 0
  padding-left: 18px
  color: #90a4ae
  font-size: 13px
  line-height: 1.9

.profile-card
  background: #fff
  border: 1px solid #eceff1
  border-radius: 14px
  padding: 20px
  h2
    margin: 0 0 6px
    font-size: 20px

.cal-status
  margin: 4px 0
  font-size: 14px
  color: #546e7a

.profile-actions
  display: flex
  flex-wrap: wrap
  gap: 10px
  margin-top: 14px

.acc-btn
  min-height: 44px
  padding: 4px 18px
  border-radius: 999px
  border: 1px solid #90a4ae
  background: #fff
  color: #37474f
  cursor: pointer
  font-size: 14px
  text-decoration: none
  display: inline-flex
  align-items: center
  &.primary
    background: #00897b
    border-color: #00897b
    color: #fff
    font-weight: 600
  &.danger
    border-color: #ef9a9a
    color: #c62828
</style>
