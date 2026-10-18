<script setup lang="ts">
/**
 * MicPermissionGuide：麦克风被拒后的开启指引（FR-904），按浏览器分别说明。
 */
const GUIDES: Array<{ browser: string; steps: string[] }> = [
  {
    browser: 'Chrome（电脑）',
    steps: [
      '点击地址栏左侧的小锁或齿轮图标',
      '找到「麦克风」，将权限改为「允许」',
      '刷新本页后重新点击录音',
    ],
  },
  {
    browser: 'Edge（电脑）',
    steps: ['点击地址栏的权限图标', '把麦克风设为「允许」', '刷新页面重试'],
  },
  {
    browser: 'Safari（macOS）',
    steps: [
      'Safari 菜单 → 设置（偏好设置）→ 网站 → 麦克风',
      '将本站设为「允许」',
      '刷新页面重试',
    ],
  },
  {
    browser: 'iOS Safari（iPhone / iPad）',
    steps: [
      '系统设置 → Safari（或设置 → 应用 → Safari）→ 麦克风，打开开关',
      '若之前拒绝过：设置 → Safari → 高级 → 网站数据，清除本站数据后重试',
      '回到本页重新点击录音',
    ],
  },
  {
    browser: 'Android Chrome',
    steps: [
      '地址栏权限提示中选择「允许」',
      '或系统设置 → 应用 → Chrome → 权限 → 麦克风，设为「仅使用此应用时允许」',
      '刷新页面重试',
    ],
  },
]
</script>

<template>
  <section class="mic-guide" aria-label="如何开启麦克风权限">
    <h3>麦克风权限被拒绝了</h3>
    <p>按你使用的浏览器开启麦克风后，回来点击「重试」即可继续：</p>
    <details v-for="guide in GUIDES" :key="guide.browser" class="guide-item">
      <summary>{{ guide.browser }}</summary>
      <ol>
        <li v-for="(step, index) in guide.steps" :key="index">{{ step }}</li>
      </ol>
    </details>
  </section>
</template>

<style scoped lang="sass">
.mic-guide
  background: #fbe9e7
  border: 1px solid #ffab91
  border-radius: 10px
  padding: 12px 16px

  h3
    margin: 0 0 4px
    font-size: 15px
    color: #bf360c

  p
    font-size: 13px
    color: #5d4037

.guide-item
  margin-top: 8px
  summary
    cursor: pointer
    font-size: 14px
    color: #3e2723
    min-height: 36px
    display: flex
    align-items: center
  ol
    padding-left: 20px
    font-size: 13px
    color: #5d4037
    line-height: 1.8
</style>
