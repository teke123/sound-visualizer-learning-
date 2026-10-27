<script setup lang="ts">
/**
 * P11 账号页（FR-106 / FR-102–108）：
 * 未登录 → 注册 / 登录入口与说明；已登录 → 性别与方言区/母语背景设置（FR-107）、
 * 退出、重新标定、清空档案入口、注销（密码确认 + 二次确认）。
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { QBtn } from 'quasar'
import { useContextStore } from '@/stores/context'
import { dialectLabel, genderLabel, useAuth } from '@/features/auth'
import { useCalibration } from '@/features/calibration'
import { errorCopy } from '@/copy/usePageCopy'
import CalibrationPanel from '@/features/assessment/components/CalibrationPanel.vue'
import DangerConfirmDialog from '@/components/DangerConfirmDialog.vue'
import DialectSelector from '@/components/DialectSelector.vue'
import GenderSelector from '@/components/GenderSelector.vue'

const router = useRouter()
const route = useRoute()
const contextStore = useContextStore()
const auth = useAuth()

const deleteOpen = ref(false)
const clearArchiveOpen = ref(false)
const recalibrateOpen = ref(false)

// 方言区/母语背景与性别（FR-107）：随 context 下发，本地编辑后全量保存
const dialectDraft = ref('')
const genderDraft = ref('')
const profileSaved = ref(false)
watch(
  () => [contextStore.context.dialectBackground, contextStore.context.gender] as const,
  ([dialect, gender]) => {
    dialectDraft.value = dialect ?? ''
    genderDraft.value = gender ?? ''
    profileSaved.value = false
  },
  { immediate: true },
)
const profileDirty = computed(
  () =>
    (dialectDraft.value || null) !== (contextStore.context.dialectBackground ?? null) ||
    (genderDraft.value || null) !== (contextStore.context.gender ?? null),
)

async function saveProfile() {
  const ok = await auth.updateProfile({
    dialectBackground: dialectDraft.value || null,
    gender: genderDraft.value || null,
  })
  if (ok) profileSaved.value = true
}

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
        音域：{{ contextStore.context.calibration.status === 'personal' ? '已标定' : '未标定（可在录音前标定，也可跳过）' }}
      </p>
      <p class="dialect-status">
        方言区 / 母语背景：{{ contextStore.context.dialectBackground ? dialectLabel(contextStore.context.dialectBackground) : '未填写' }}
      </p>
      <p class="dialect-status">
        性别：{{ contextStore.context.gender ? genderLabel(contextStore.context.gender) : '未填写' }}
      </p>
      <div class="dialect-edit">
        <DialectSelector v-model="dialectDraft" />
        <GenderSelector v-model="genderDraft" />
        <QBtn
          type="button"
          unelevated
          no-caps
          color="primary"
          :label="auth.busy.value ? '保存中…' : '保存资料'"
          :disable="!profileDirty || auth.busy.value"
          @click="saveProfile"
        />
      </div>
      <p v-if="profileSaved" class="dialect-saved">✅ 已更新。</p>
      <p v-if="auth.error.value" class="dialect-error">{{ errorCopy(auth.error.value).title }}</p>

      <div class="profile-actions">
        <QBtn type="button" outline no-caps color="blue-grey-4" text-color="blue-grey-9" label="重新标定音域" @click="recalibrateOpen = true" />
        <QBtn type="button" outline no-caps color="blue-grey-4" text-color="blue-grey-9" label="删除录音 / 清空档案" @click="openClearArchive" />
        <QBtn type="button" outline no-caps color="blue-grey-4" text-color="blue-grey-9" label="退出登录" @click="logout" />
        <QBtn type="button" outline no-caps color="red-3" text-color="red-9" label="注销账号" @click="deleteOpen = true" />
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

.dialect-status
  margin: 4px 0
  font-size: 14px
  color: #546e7a

.dialect-edit
  display: flex
  gap: 10px
  align-items: flex-end
  margin-top: 8px
  flex-wrap: wrap

.dialect-saved
  margin: 6px 0 0
  font-size: 13px
  color: #1b5e20

.dialect-error
  margin: 6px 0 0
  font-size: 13px
  color: #c62828

.profile-actions
  display: flex
  flex-wrap: wrap
  gap: 10px
  margin-top: 14px

// 未登录「登录 / 注册」入口的 RouterLink 胶囊样式（原按钮已换 QBtn，仅这两个链接仍用）
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
</style>
