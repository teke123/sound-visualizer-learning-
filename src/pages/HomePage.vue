<script setup lang="ts">
/**
 * P01 首页：按原型 V5 重做。
 * 英雄区（搜索 + 四个入口）→ 为什么用它 → 专业资料 → 家长科普 → 小问答。
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '@/components/ui/AppIcon.vue'

const router = useRouter()
const keyword = ref('')

function submitSearch() {
  const q = keyword.value.trim()
  void router.push({ path: '/search', query: q ? { q } : {} })
}

const actions = [
  { icon: 'search', title: '搜一个音', desc: '找你想练的拼音或汉字', to: '/search', cls: 'a1' },
  { icon: 'mouth', title: '看懂发音', desc: '看嘴巴和舌头怎么摆', to: '/principles', cls: 'a2' },
  { icon: 'run', title: '跟着练', desc: '从第一关开始往上走', to: '/map', cls: 'a3' },
  { icon: 'mic', title: '录音比较', desc: '录下来，看看练得怎样', to: '/map', cls: 'a4' },
]

const faq = [
  { q: '我要怎么开始练习？', a: '点「搜一个音」找拼音，或者点「跟着练」直接开始第一关。' },
  { q: '录音结果一定准吗？', a: '每一关都可以录音。有些音听起来很接近，这些关的结果会标「仅供参考」——先对照示范再练、再录一遍。' },
  { q: '练习记录会自动保存吗？', a: '不会自动保存。保存进度和录音需要家长同意；不同意的录音，看过这一次结果后就不再留存。' },
]
</script>

<template>
  <div class="home">
    <!-- 英雄区 -->
    <section class="hero">
      <span class="hero-badge">
        <AppIcon name="wave" size="sm" />
        看得见的声音 · 普通话拼音发音学习
      </span>
      <h1>让每一个音<br /><em>看得见</em>，也读得准</h1>
      <div class="eq" aria-hidden="true">
        <i v-for="n in 11" :key="n" :style="{ animationDelay: `${Math.abs(6 - n) * 0.12}s` }" />
      </div>

      <form class="searchbar" @submit.prevent="submitSearch">
        <input
          v-model="keyword"
          type="search"
          placeholder="输入汉字、拼音或关卡名"
          aria-label="搜索关卡"
        />
        <button type="submit" class="search-btn">
          <AppIcon name="search" size="sm" />
          搜一个音
        </button>
      </form>

      <div class="actions">
        <RouterLink
          v-for="action in actions"
          :key="action.title"
          :to="action.to"
          class="action"
          :class="action.cls"
        >
          <span class="bubble"><AppIcon :name="action.icon" /></span>
          <b>{{ action.title }}</b>
          <small>{{ action.desc }}</small>
        </RouterLink>
      </div>
    </section>

    <!-- 为什么 -->
    <section class="sect">
      <h2><span class="bar" />为什么用「看得见的声音」</h2>
      <p class="lead">
        拼音卡只能看字形、听一遍录音。这里把嘴巴张多大、舌头放在哪、声音怎么起伏，一起摆在你眼前——先看懂，再跟着练，最后录下来比一比。
      </p>
    </section>

    <!-- 小问答 -->
    <section class="sect">
      <h2><span class="bar bar--violet" />小问答</h2>
      <details v-for="item in faq" :key="item.q" class="fold">
        <summary><AppIcon name="info" size="sm" />{{ item.q }}</summary>
        <div class="body">{{ item.a }}</div>
      </details>
    </section>
  </div>
</template>

<style scoped lang="sass">
.home
  padding-bottom: 8px

/* ============================ 英雄区 ============================ */

.hero
  text-align: center
  padding: 30px 0 8px

.hero-badge
  display: inline-flex
  align-items: center
  gap: 8px
  border: 1px solid rgba(30, 147, 232, 0.16)
  background: rgba(255, 255, 255, 0.78)
  backdrop-filter: blur(8px)
  color: var(--vs-brand-d)
  border-radius: 999px
  padding: 8px 18px
  font-size: 13px
  font-weight: 700
  box-shadow: var(--vs-sh-1)

.hero h1
  margin: 24px 0 0
  font-size: clamp(38px, 5vw, 62px)
  font-weight: 900
  letter-spacing: 2px
  line-height: 1.2
  text-wrap: balance
  color: var(--vs-ink)

.hero h1 em
  font-style: normal
  background: linear-gradient(112deg, #1478d8 2%, #22a7d8 50%, #37c6c4 100%)
  -webkit-background-clip: text
  background-clip: text
  -webkit-text-fill-color: transparent
  color: var(--vs-brand)

.eq
  display: flex
  align-items: flex-end
  justify-content: center
  gap: 7px
  height: 42px
  margin-top: 26px

.eq i
  width: 8px
  border-radius: 999px
  background: linear-gradient(180deg, #6dc4f0, #1e93e8)
  animation: eq 1.3s ease-in-out infinite
  height: 12px

@keyframes eq
  0%, 100%
    height: 10px
    opacity: 0.5
  50%
    height: 42px
    opacity: 1

.searchbar
  margin: 22px auto 0
  max-width: 620px
  display: flex
  gap: 8px
  background: #fff
  border: 1px solid var(--vs-line)
  border-radius: 18px
  padding: 8px 8px 8px 18px
  box-shadow: 0 10px 30px rgba(20, 38, 57, 0.07), 0 2px 6px rgba(20, 38, 57, 0.04)
  transition: border-color 0.2s var(--vs-ease), box-shadow 0.2s var(--vs-ease)

.searchbar:focus-within
  border-color: #c0dff6
  box-shadow: 0 12px 34px rgba(30, 147, 232, 0.14), 0 0 0 4px rgba(30, 147, 232, 0.08)

.searchbar input
  flex: 1
  border: none
  outline: none
  background: transparent
  font-size: 16px
  color: var(--vs-ink)
  min-width: 0
  min-height: 48px
  font-family: inherit

.searchbar input::placeholder
  color: var(--vs-mute)
  font-size: 13.5px

.search-btn
  border: none
  cursor: pointer
  border-radius: 14px
  padding: 0 20px
  min-height: 48px
  font-family: inherit
  font-size: 14.5px
  font-weight: 700
  color: #fff
  background: linear-gradient(135deg, #2aa0ee, #1477c4)
  box-shadow: 0 8px 20px rgba(30, 147, 232, 0.24)
  display: inline-flex
  align-items: center
  gap: 8px
  white-space: nowrap

.search-btn:hover
  background: linear-gradient(135deg, #3aaaf2, #1779c9)

.actions
  display: grid
  grid-template-columns: repeat(4, 1fr)
  gap: 14px
  margin-top: 26px

.action
  border: 1px solid rgba(228, 238, 247, 0.9)
  cursor: pointer
  text-align: center
  color: var(--vs-ink)
  min-height: 128px
  border-radius: 20px
  background: #fff
  box-shadow: var(--vs-sh-1)
  padding: 18px 10px
  display: flex
  flex-direction: column
  align-items: center
  gap: 9px
  text-decoration: none
  transition: transform 0.25s var(--vs-ease), box-shadow 0.25s var(--vs-ease), border-color 0.25s var(--vs-ease)

.action:hover
  transform: translateY(-4px)
  box-shadow: var(--vs-sh-2)
  border-color: #cbe6f8

.action .bubble
  width: 48px
  height: 48px
  border-radius: 15px
  display: flex
  align-items: center
  justify-content: center
  background: linear-gradient(135deg, #52b0ec, #1e93e8)
  color: #fff
  box-shadow: 0 8px 18px rgba(30, 147, 232, 0.26)

.action.a2 .bubble
  background: linear-gradient(135deg, #3cc79b, #0e9a72)
  box-shadow: 0 8px 18px rgba(18, 166, 123, 0.26)

.action.a3 .bubble
  background: linear-gradient(135deg, #7fcbf2, #1c95c9)
  box-shadow: 0 8px 18px rgba(34, 167, 216, 0.28)

.action.a4 .bubble
  background: linear-gradient(135deg, #e0a44f, #c9823c)
  box-shadow: 0 8px 18px rgba(200, 135, 58, 0.26)

.action b
  font-size: 15px

.action small
  color: var(--vs-sub)
  font-size: 12px
  line-height: 1.6

/* ============================ 内容区 ============================ */

.sect
  margin-top: 34px

.sect > h2
  font-size: 20px
  font-weight: 900
  display: flex
  align-items: center
  gap: 8px
  margin: 0
  color: var(--vs-ink)

.bar
  width: 5px
  height: 19px
  border-radius: 3px
  background: linear-gradient(180deg, #52b0ec, #22a7d8)

.bar--violet
  background: var(--vs-violet)

.bar--green
  background: var(--vs-green)

.lead
  margin: 8px 0 0
  font-size: 13.5px
  color: var(--vs-sub)
  line-height: 1.9

.fold
  margin-top: 12px
  background: #fff
  border-radius: var(--vs-r-lg)
  box-shadow: var(--vs-sh-1)
  border: 1px solid rgba(20, 38, 57, 0.055)
  overflow: hidden

.fold > summary
  cursor: pointer
  list-style: none
  padding: 16px
  font-size: 14px
  font-weight: 700
  display: flex
  align-items: center
  gap: 8px
  color: var(--vs-ink)

.fold > summary::-webkit-details-marker
  display: none

.fold > summary .vs-ico
  color: var(--vs-sub)

.fold > summary:hover
  background: #f8fafe

.fold .body
  padding: 0 16px 16px
  font-size: 13.5px
  color: var(--vs-sub)
  line-height: 1.9

/* ============================ 响应式 ============================ */

@media (max-width: 900px)
  .hero
    padding: 16px 0 4px

  .hero h1
    font-size: 36px
    letter-spacing: 1px

  .actions
    grid-template-columns: repeat(2, 1fr)

  .searchbar input
    font-size: 14px

  .searchbar input::placeholder
    font-size: 12px

</style>
