<script setup lang="ts">
/**
 * 页面状态块
 * ---------------------------------------------------------------------------
 * 页面的「加载中 / 空 / 出错 / 未开放」四种状态统一走这个组件，
 * 文案一律取自 src/data/pages.ts 的文案位，页面不再散写提示语。
 *
 * 与 SRS 的关系（07 章 UI 状态）：
 *   - 「未开放」是内容未发布 / 检测未开放时的正式状态，不是错误，
 *     也不写「敬请期待」凑数；
 *   - 「空」是页面可用但确实还没有内容；
 *   - 「出错」必须说清是后端没连上，而不是让人误判成「搜不到」。
 */
import { computed } from 'vue'
import type { PageCopySlots } from '@/data/pages'

export type PageStateKind = 'loading' | 'empty' | 'error' | 'unopened'

const props = withDefaults(
  defineProps<{
    /** 要渲染的状态；为 null 时不渲染任何东西（页面自己渲染内容） */
    state: PageStateKind | null
    /** 页号对应的文案位（usePageCopy(code).copy） */
    copy: PageCopySlots
    /** 补充说明，例如后端返回的原始错误信息 */
    detail?: string
    /** 是否显示主按钮（默认错误态与空态显示） */
    showAction?: boolean
    /** 覆盖主按钮文案；默认取 copy.cta */
    actionText?: string
    /** 紧凑模式（用于卡片内部） */
    compact?: boolean
  }>(),
  { compact: false },
)

const emit = defineEmits<{ (e: 'action'): void }>()

const text = computed(() => {
  switch (props.state) {
    case 'loading':
      return props.copy.loading
    case 'empty':
      return props.copy.empty
    case 'error':
      return props.copy.error
    case 'unopened':
      return props.copy.unopened
    default:
      return ''
  }
})

const withAction = computed(() =>
  props.showAction === undefined
    ? props.state === 'error' || props.state === 'empty'
    : props.showAction,
)

const actionLabel = computed(() => props.actionText || props.copy.cta)
</script>

<template>
  <div v-if="state" class="page-state" :class="{ compact }">
    <!-- 加载中：骨架屏，避免空白页被误认为「没有内容」 -->
    <template v-if="state === 'loading'">
      <p class="state-text">{{ text }}</p>
      <el-skeleton :rows="compact ? 2 : 4" animated />
    </template>

    <!-- 出错：红色告警，明确指向后端 -->
    <template v-else-if="state === 'error'">
      <el-alert type="error" show-icon :closable="false" :title="text" :description="detail" />
      <el-button v-if="withAction" type="primary" class="state-action" @click="emit('action')">
        {{ actionLabel }}
      </el-button>
    </template>

    <!-- 空 / 未开放：都走 el-empty，但文案与语义分开 -->
    <template v-else>
      <el-empty :description="text" :image-size="compact ? 60 : 100">
        <el-button v-if="withAction" type="primary" @click="emit('action')">
          {{ actionLabel }}
        </el-button>
      </el-empty>
      <p v-if="detail" class="state-detail">{{ detail }}</p>
    </template>
  </div>
</template>

<style scoped>
.page-state { padding: 8px 0; }
.page-state.compact { padding: 4px 0; }
.state-text { margin: 0 0 8px; font-size: 13px; color: #909399; }
.state-action { margin-top: 12px; }
.state-detail { margin: 4px 0 0; font-size: 12px; color: #c0c4cc; text-align: center; }
</style>
