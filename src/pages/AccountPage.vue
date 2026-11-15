<script setup lang="ts">
/**
 * P11 账号页（FR-106 / FR-102–108）：
 * 未登录 → 注册 / 登录入口与说明；已登录 → 性别与方言区/母语背景设置（FR-107）、
 * 退出、重新标定、清空档案入口、注销（密码确认 + 二次确认）。
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useContextStore } from '@/stores/context'
import { dialectLabel, genderLabel, useAuth } from '@/features/auth'
import { useCalibration } from '@/features/calibration'
import { errorCopy } from '@/copy/usePageCopy'
import CalibrationPanel from '@/features/assessment/components/CalibrationPanel.vue'
import DangerConfirmDialog from '@/components/DangerConfirmDialog.vue'
import DialectSelector from '@/components/DialectSelector.vue'
import GenderSelector from '@/components/GenderSelector.vue'
import PageHead from '@/components/ui/PageHead.vue'
import AppIcon from '@/components/ui/AppIcon.vue'

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
    <PageHead title="账号" icon="user" />

    <!-- 未登录 -->
    <section v-if="!authenticated" class="panel guest-panel">
      <h2>注册或登录</h2>
      <p class="panel-note">注册并登录后使用：学习进度与录音结果自动保存到你的账号。注册 / 登录即代表同意服务条款。</p>
      <div class="guest-actions">
        <RouterLink to="/account/login" class="vs-btn">登录</RouterLink>
        <RouterLink to="/account/register" class="vs-btn vs-btn--ghost">注册</RouterLink>
      </div>
      <ul class="guest-facts">
        <li>用户名 + 密码即可，不收集邮箱或手机号</li>
        <li>不提供密码找回：忘记密码只能重新注册</li>
      </ul>
    </section>

    <!-- 已登录 -->
    <section v-else class="panel profile-card">
      <div class="profile-head">
        <span class="profile-mark"><AppIcon name="user" size="sm" /></span>
        <div>
          <h2>{{ contextStore.context.username }}</h2>
        </div>
      </div>

      <dl class="profile-rows">
        <div class="profile-row">
          <dt>音域</dt>
          <dd>{{ contextStore.context.calibration.status === 'personal' ? '已标定' : '未标定' }}</dd>
        </div>
        <div class="profile-row">
          <dt>方言区 / 母语背景</dt>
          <dd>{{ contextStore.context.dialectBackground ? dialectLabel(contextStore.context.dialectBackground) : '未填写' }}</dd>
        </div>
        <div class="profile-row">
          <dt>性别</dt>
          <dd>{{ contextStore.context.gender ? genderLabel(contextStore.context.gender) : '未填写' }}</dd>
        </div>
      </dl>

      <div class="dialect-edit">
        <DialectSelector v-model="dialectDraft" />
        <GenderSelector v-model="genderDraft" />
        <button type="button" class="vs-btn" :disabled="!profileDirty || auth.busy.value" @click="saveProfile">
          {{ auth.busy.value ? '保存中…' : '保存资料' }}
        </button>
      </div>
      <p v-if="profileSaved" class="dialect-saved">✅ 已更新。</p>
      <p v-if="auth.error.value" class="dialect-error">{{ errorCopy(auth.error.value).title }}</p>

      <div class="profile-actions">
        <button type="button" class="vs-btn vs-btn--ghost vs-btn--small" @click="recalibrateOpen = true">
          <AppIcon name="mic" size="sm" />重新标定音域
        </button>
        <button type="button" class="vs-btn vs-btn--ghost vs-btn--small" @click="openClearArchive">
          <AppIcon name="folder" size="sm" />删除录音 / 清空档案
        </button>
        <button type="button" class="vs-btn vs-btn--ghost vs-btn--small" @click="logout">退出登录</button>
        <button type="button" class="vs-btn vs-btn--ghost vs-btn--small danger" @click="deleteOpen = true">
          <AppIcon name="trash" size="sm" />注销账号
        </button>
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
  max-width: 760px
  margin: 0 auto
  display: flex
  flex-direction: column
  gap: 16px

.panel
  background: var(--vs-card)
  border: 1px solid var(--vs-line)
  border-radius: 8px
  box-shadow: var(--vs-sh-1)
  padding: 24px

.panel h2
  margin: 0
  font-size: 20px
  font-weight: 900
  letter-spacing: -0.3px

.panel-note
  color: var(--vs-sub)
  font-size: 13.5px
  margin: 6px 0 0
  line-height: 1.8

.guest-actions
  display: flex
  gap: 10px
  margin-top: 16px

.guest-facts
  margin: 18px 0 0
  padding: 14px 0 0 18px
  border-top: 1px dashed var(--vs-line2)
  color: var(--vs-mute)
  font-size: 13px
  line-height: 1.9

.profile-head
  display: flex
  align-items: center
  gap: 12px

.profile-mark
  width: 40px
  height: 40px
  border-radius: 8px
  flex: none
  display: flex
  align-items: center
  justify-content: center
  background: var(--vs-soft)
  color: var(--vs-brand)
  box-shadow: inset 0 0 0 1px var(--vs-brand-line)

.profile-rows
  margin: 18px 0 0
  border-top: 1px solid var(--vs-line)

.profile-row
  display: flex
  align-items: baseline
  gap: 12px
  padding: 10px 0
  border-bottom: 1px solid var(--vs-line)
  dt
    flex: 0 0 120px
    font-size: 13px
    color: var(--vs-mute)
  dd
    margin: 0
    font-size: 13.5px
    color: var(--vs-ink2)

.dialect-edit
  display: flex
  gap: 10px
  align-items: flex-end
  margin-top: 16px
  flex-wrap: wrap

.dialect-saved
  margin: 8px 0 0
  font-size: 13px
  color: var(--vs-green)

.dialect-error
  margin: 8px 0 0
  font-size: 13px
  color: var(--vs-brand-d)

.profile-actions
  display: flex
  flex-wrap: wrap
  gap: 8px
  margin-top: 20px
  padding-top: 16px
  border-top: 1px solid var(--vs-line)

.profile-actions .danger
  color: var(--vs-brand-d)
</style>
