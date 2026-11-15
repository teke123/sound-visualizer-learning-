<script setup lang="ts">
/**
 * P01 首页（编辑感 · 文字优先）
 * 只保留英雄区与「相关资料」区块；资料区等媒体素材到位后填充。
 */
</script>

<template>
  <div class="home">
    <!-- 英雄区 -->
    <section class="hero">
      <div class="hero-in">
        <h1 class="hero-wordmark vs-display">看得见的声音</h1>
        <p class="hero-tagline vs-display">读得准不准，曲线会告诉你</p>
        <div class="hero-actions">
          <RouterLink to="/map" class="hero-btn hero-btn--solid">从第一关开始 →</RouterLink>
          <RouterLink to="/search" class="hero-btn hero-btn--ghost">搜一个音</RouterLink>
        </div>
      </div>
    </section>

    <!-- 相关资料：等媒体素材到位后填充 -->
    <section class="materials">
      <h2 class="vs-display">相关资料</h2>
      <div class="materials-stage" aria-label="相关资料占位" />
    </section>
  </div>
</template>

<style scoped lang="sass">
.home
  display: flex
  flex-direction: column

/* ============================ 英雄区 ============================ */

.hero
  margin: -40px calc(50% - 50vw) 0
  padding: 104px 0 96px
  background: var(--vs-band)
  color: var(--vs-band-ink)

.hero-in
  max-width: 1180px
  margin: 0 auto
  padding: 0 24px

.hero-wordmark
  margin: 0
  font-size: clamp(56px, 8vw, 120px)
  line-height: 1.04
  letter-spacing: -0.03em
  color: var(--vs-band-ink)

.hero-tagline
  margin: 22px 0 0
  font-size: clamp(22px, 2.4vw, 32px)
  line-height: 1.35
  color: var(--vs-band-sub)

.hero-actions
  display: flex
  gap: 12px
  margin-top: 40px
  flex-wrap: wrap

.hero-btn
  display: inline-flex
  align-items: center
  justify-content: center
  height: 48px
  padding: 0 26px
  border-radius: 999px
  font-size: 14.5px
  font-weight: 600
  text-decoration: none
  transition: background 0.16s var(--vs-ease), border-color 0.16s var(--vs-ease), transform 0.16s var(--vs-ease)

.hero-btn--solid
  background: var(--vs-peach)
  color: var(--vs-band)
  &:hover
    background: #fdece0
    transform: translateY(-1px)

.hero-btn--ghost
  border: 1px solid rgba(248, 236, 225, 0.34)
  color: var(--vs-band-ink)
  &:hover
    border-color: rgba(248, 236, 225, 0.7)
    transform: translateY(-1px)

/* ============================ 相关资料（占位） ============================ */

.materials
  max-width: 1180px
  width: 100%
  margin: 0 auto
  padding: 96px 24px 0
  h2
    margin: 0
    font-size: 40px
    line-height: 1.24
    color: var(--vs-ink)

.materials-stage
  margin-top: 36px
  min-height: 420px
  border: 1px dashed var(--vs-line-strong)
  border-radius: var(--vs-r-lg)
  background: rgba(255, 255, 255, 0.35)

/* ============================ 响应式 ============================ */

@media (max-width: 900px)
  .hero
    margin-top: -24px
    padding: 64px 0 56px

  .hero-wordmark
    font-size: 48px

  .materials
    padding-top: 64px
    h2
      font-size: 30px

  .materials-stage
    min-height: 260px
</style>
