<script setup lang="ts">
/**
 * P11 账号页（FR-106 / FR-102–108）：
 * 未登录 → 注册 / 登录入口与说明；已登录 → 退出、同意状态 + 历史、撤回、
 * 注销（密码确认）、清空档案入口、重新标定、本会话临时记录。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { identityApi, type ConsentStateResponse } from '@/api'
import { useContextStore } from '@/stores/context'
import { useAuth } from '@/features/auth'
import { useConsent } from '@/features/consent'
import { useCalibration } from '@/features/calibration'
import { errorCopy } from '@/copy/usePageCopy'
import ConsentTimeline from '@/components/ConsentTimeline.vue'
import SessionRecordsPanel from '@/components/SessionRecordsPanel.vue'
import CalibrationPanel from '@/components/CalibrationPanel.vue'
import DangerConfirmDialog from '@/components/DangerConfirmDialog.vue'

const router = useRouter()
const contextStore = useContextStore()
const auth = useAuth()
const consent = useConsent()

const consentState = ref<ConsentStateResponse | null>(null)
const consentLoading = ref(false)

const withdrawOpen = ref(false)
const deleteOpen = ref(false)
const clearArchiveOpen = ref(false)
const recalibrateOpen = ref(false)

const calibration = useCalibration()

const authenticated = computed(() => contextStore.isAuthenticated)

async function loadConsent() {
  if (!authenticated.value) return
  consentLoading.value = true
  try {
    const res = await identityApi.consentState()
    consentState.value = res.data
  } catch {
    consentState.value = null
  } finally {
    consentLoading.value = false
  }
}

onMounted(() => void loadConsent())

const CONSENT_STATUS_LABELS: Record<string, string> = {
  none: '未处理',
  granted: '已同意保存',
  rejected: '已拒绝',
  revoked: '已撤回',
}

async function logout() {
  await auth.logout()
  await router.push('/')
}

/** 撤回：删除录音、结果、学习进度与音域（D-17） */
async function confirmWithdraw() {
  await auth.revokeConsent()
  withdrawOpen.value = false
  consentState.value = null
  await router.push('/')
}

/** 注销：密码确认 + 全会话失效 */
async function confirmDeleteAccount(password?: string) {
  const ok = await auth.deleteAccount(password ?? '')
  if (ok) {
    deleteOpen.value = false
    auth.finishAccountDeletion()
    await router.push('/')
  }
}

/** 清空档案：跳转 P10（删除范围与撤回不同） */
function openClearArchive() {
  void router.push('/archive')
}
</script>

<template>
  <div class="account-page">
    <h1>账号</h1>

    <!-- 未登录 -->
    <section v-if="!authenticated" class="guest-panel">
      <p class="guest-note">可以不登录直接学习；登录并同意后才能保存进度和录音。</p>
      <div class="guest-actions">
        <RouterLink to="/account/login" class="acc-btn primary">登录</RouterLink>
        <RouterLink to="/account/register" class="acc-btn">注册</RouterLink>
      </div>
      <ul class="guest-facts">
        <li>用户名 + 密码即可，不收集邮箱或手机号</li>
        <li>不提供密码找回：忘记密码只能重新注册</li>
        <li>保存内容前会先征求你的同意，可随时撤回并删除</li>
      </ul>
    </section>

    <!-- 已登录 -->
    <template v-else>
      <section class="profile-card">
        <h2>{{ contextStore.context.username }}</h2>
        <p class="consent-status">
          保存状态：
          <strong :class="`status-${contextStore.consentStatus}`">
            {{ CONSENT_STATUS_LABELS[contextStore.consentStatus] ?? contextStore.consentStatus }}
          </strong>
        </p>
        <p v-if="contextStore.context.calibration.status !== 'none'" class="cal-status">
          音域：
          {{ contextStore.context.calibration.status === 'personal' ? '个人音域' : '临时会话音域' }}
          <template v-if="contextStore.context.calibration.expiresAt">
            （{{ new Date(contextStore.context.calibration.expiresAt).toLocaleString('zh-CN', { hour12: false }) }} 到期）
          </template>
        </p>
        <p v-else class="cal-status">音域：未标定（录音检测前会先引导标定）</p>

        <div class="profile-actions">
          <button v-if="consent.consentEntryAvailable.value" type="button" class="acc-btn primary" @click="consent.openDialog()">
            {{ contextStore.consentStatus === 'none' ? '阅读保存说明' : '重新同意保存' }}
          </button>
          <button type="button" class="acc-btn" @click="recalibrateOpen = true">重新标定音域</button>
          <button type="button" class="acc-btn" @click="openClearArchive">删除录音 / 清空档案</button>
          <button v-if="contextStore.consentGranted" type="button" class="acc-btn danger" @click="withdrawOpen = true">
            撤回同意
          </button>
          <button type="button" class="acc-btn" @click="logout">退出登录</button>
          <button type="button" class="acc-btn danger" @click="deleteOpen = true">注销账号</button>
        </div>
      </section>

      <section class="consent-history">
        <h2>同意记录</h2>
        <p v-if="consentLoading">读取中…</p>
        <ConsentTimeline v-else-if="consentState" :decisions="consentState.decisions" />
        <p v-else class="history-empty">暂时读不到同意记录。</p>
      </section>

      <SessionRecordsPanel class="acc-session" />
    </template>

    <!-- 撤回确认（删除范围写明，FR-104） -->
    <DangerConfirmDialog
      :open="withdrawOpen"
      title="撤回同意并删除全部数据？"
      message="撤回后将立即停止保存，并删除：全部录音与结果（含临时）、声音档案、学习进度、个人音域与标定。此操作不可恢复，再次同意也不会找回已删数据。"
      confirm-label="撤回并删除"
      @confirm="confirmWithdraw"
      @cancel="withdrawOpen = false"
    />

    <!-- 注销确认（输入密码） -->
    <DangerConfirmDialog
      :open="deleteOpen"
      title="注销账号？"
      message="将按撤回的全部范围清理数据（录音、结果、进度、音域），并删除账号、失效全部登录会话；用户名不再可用。此操作不可恢复。"
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

.consent-status, .cal-status
  margin: 4px 0
  font-size: 14px
  color: #546e7a

.status-granted
  color: #2e7d32
.status-none, .status-rejected, .status-revoked
  color: #bf360c

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

.consent-history
  background: #fff
  border: 1px solid #eceff1
  border-radius: 14px
  padding: 16px 20px
  h2
    margin: 0 0 6px
    font-size: 16px

.history-empty
  color: #90a4ae
  font-size: 13px

.acc-session
  margin-top: 4px
</style>
