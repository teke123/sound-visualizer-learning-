<script setup lang="ts">
/**
 * RecordingTips：录音按钮下方的附属环境提醒（FR-903），一行小字、不作卡片。
 * 检测到蓝牙耳机麦克风时追加警告：蓝牙输入会被切到 HFP 免提窄带（8/16 kHz），
 * 高频特征丢失，仅提示更换、不阻断录音（FR-1301 不设阻断式门禁）。
 */
import { useRecorderStore } from '@/stores/recorder'

const recorder = useRecorderStore()
</script>

<template>
  <p class="recording-tip">请在安静的地方录音，不要使用蓝牙耳机</p>
  <p v-if="recorder.inputBluetooth" class="recording-tip warn">
    当前检测到蓝牙耳机麦克风（{{ recorder.inputLabel }}）：录音会切换到窄带通话模式、丢失高频信息，请改用手机自带麦克风或外接麦克风
  </p>
</template>

<style scoped lang="sass">
.recording-tip
  margin: 0
  font-size: 12px
  color: #90a4ae
  &.warn
    color: #ef6c00
    font-weight: 600
</style>
