<script setup lang="ts">
// 账号页（P11，FR-106）：未登录时提供注册与登录入口及说明
// 「保存进度和录音需先同意」（FR-102）；登录后提供退出、同意状态查看、
// 撤回同意、删除单条录音与清空档案的入口（FR-104）。
// 同意与撤回是服务端记录（NFR-15），本页只做展示与发起操作。
import { usePageCopy } from '@/composables/usePageCopy'

const { copy } = usePageCopy('P11')
</script>

<template>
  <div class="account-view">
    <h2>账号</h2>
    <p class="intro">{{ copy.subtitle }}</p>

    <!-- 未登录：注册 / 登录（FR-107 轻量账号） -->
    <el-card class="auth-card">
      <template #header><span>注册 / 登录</span></template>
      <p class="hint">不登录也可以学习；录音结果当次可见。要保存进度和录音，需要先注册或登录，并完成保存同意。</p>
      <!-- 重构时恢复：注册/登录表单、错误态（账号不存在/密码错误） -->
    </el-card>

    <!-- 已登录：同意状态与删除入口（FR-104/FR-106） -->
    <el-card class="consent-card">
      <template #header><span>保存同意与数据管理</span></template>
      <ul class="consent-list">
        <li>同意状态：显示当前是否已同意保存，以及同意时间。</li>
        <li>撤回同意：撤回后立即停止新增保存；已保存条目仍可在档案中查看，直至删除。</li>
        <li>删除：支持删除单条录音与清空全部档案，删除后不可恢复（二次确认）。</li>
      </ul>
      <!-- 重构时恢复：同意状态卡片、撤回按钮、删除入口（跳转档案或内嵌列表） -->
    </el-card>
  </div>
</template>

<style scoped>
.account-view { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.intro { color: #606266; font-size: 14px; margin: 0; }
.hint { color: #909399; font-size: 13px; margin: 0 0 12px; }
.consent-list { margin: 0; padding-left: 18px; color: #606266; font-size: 14px; line-height: 1.9; }
</style>
