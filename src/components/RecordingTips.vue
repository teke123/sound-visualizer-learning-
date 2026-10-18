<script setup lang="ts">
/** RecordingTips：录音前环境提示（FR-903）：安静环境、麦克风距离 */
</script>

<template>
  <aside class="recording-tips" aria-label="录音前的准备">
    <h3>录音前</h3>
    <ul>
      <li>🎧 找一个安静的地方，避免背景噪音</li>
      <li>🎤 麦克风距离嘴巴约一拳（15–20 厘米），音量用平常说话的状态</li>
    </ul>
  </aside>
</template>

<style scoped lang="sass">
.recording-tips
  background: #fffde7
  border: 1px solid #ffe082
  border-radius: 10px
  padding: 12px 16px

  h3
    margin: 0 0 6px
    font-size: 14px
    color: #795548

  ul
    margin: 0
    padding-left: 18px
    color: #5d4037
    font-size: 13px
    line-height: 1.9
</style>
