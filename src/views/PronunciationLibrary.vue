<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUnitsStore } from '@/stores/units'
import { useUserStore } from '@/stores/user'
import { favoritesApi } from '@/api'
import { STATIC_UNITS } from '@/data/staticUnits'

const router = useRouter()
const unitsStore = useUnitsStore()
const userStore = useUserStore()

const searchQuery = ref('')
const category = ref<'all' | '声母' | '韵母' | '声调'>('all')
const favorites = ref<string[]>([])
const compareIds = ref<string[]>([])

onMounted(async () => {
  await unitsStore.fetchPublished()
  try {
    const res = await favoritesApi.list(userStore.userId)
    favorites.value = res.data
  } catch { /* optional */ }
})

const units = computed(() => {
  let list = STATIC_UNITS
  if (category.value !== 'all') list = list.filter(u => u.category === category.value)
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(u =>
      u.pinyin.includes(q) || u.character.includes(q) || u.conclusion.includes(q)
    )
  }
  return list
})

async function toggleFavorite(id: string, e: Event) {
  e.stopPropagation()
  const on = favorites.value.includes(id)
  try {
    if (on) {
      await favoritesApi.remove(userStore.userId, id)
      favorites.value = favorites.value.filter(x => x !== id)
    } else {
      await favoritesApi.add(userStore.userId, id)
      favorites.value = [...favorites.value, id]
    }
  } catch {
    ElMessage.error('收藏操作失败')
  }
}

function toggleCompare(id: string, e: Event) {
  e.stopPropagation()
  if (compareIds.value.includes(id)) {
    compareIds.value = compareIds.value.filter(x => x !== id)
  } else if (compareIds.value.length < 2) {
    compareIds.value = [...compareIds.value, id]
  } else {
    compareIds.value = [compareIds.value[1]!, id]
  }
}

const comparePair = computed(() =>
  compareIds.value.map(id => STATIC_UNITS.find(u => u.id === id)).filter(Boolean)
)
</script>

<template>
  <div class="library-view">
    <div class="header">
      <div>
        <h2>发音库</h2>
        <p>首批 {{ STATIC_UNITS.length }} 个已发布单元 · 未完成内容不公开展示</p>
      </div>
      <el-input v-model="searchQuery" placeholder="搜索拼音或汉字..." prefix-icon="Search" clearable style="max-width:280px" />
    </div>

    <div class="filters">
      <el-tag v-for="c in ['all','声母','韵母','声调']" :key="c"
        :type="category === c ? 'primary' : 'info'"
        effect="plain"
        style="cursor:pointer;margin-right:8px"
        @click="category = c as any"
      >{{ c === 'all' ? '全部' : c }}</el-tag>
    </div>

    <div v-if="comparePair.length === 2" class="compare-bar card">
      <h4>并排比较</h4>
      <div class="compare-row">
        <div v-for="u in comparePair" :key="u!.id">
          <strong>{{ u!.character }}</strong> {{ u!.pinyin }}
          <p>{{ u!.conclusion }}</p>
        </div>
      </div>
      <p class="hint">关键差异请进入各单元听示范与检测对比。</p>
    </div>

    <div class="grid">
      <el-card v-for="u in units" :key="u.id" shadow="hover" class="unit-card" @click="router.push(`/learn/${u.id}`)">
        <div class="top">
          <span class="char">{{ u.character }}</span>
          <el-button :icon="favorites.includes(u.id) ? 'StarFilled' : 'Star'" circle size="small" @click="toggleFavorite(u.id, $event)" />
        </div>
        <div class="py">{{ u.pinyin }}</div>
        <p>{{ u.conclusion }}</p>
        <el-button size="small" :type="compareIds.includes(u.id) ? 'primary' : 'default'" @click="toggleCompare(u.id, $event)">
          {{ compareIds.includes(u.id) ? '已选比较' : '加入比较' }}
        </el-button>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.library-view { max-width: 1000px; margin: 0 auto; }
.header { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.filters { margin-bottom: 16px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.unit-card { cursor: pointer; }
.top { display: flex; justify-content: space-between; align-items: center; }
.char { font-size: 32px; font-weight: 700; }
.py { color: #409eff; margin: 4px 0 8px; }
.unit-card p { font-size: 13px; color: #909399; min-height: 40px; }
.card { background: #fff; padding: 16px; border-radius: 12px; margin-bottom: 16px; }
.compare-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.hint { font-size: 12px; color: #909399; }
@media (max-width: 600px) { .compare-row { grid-template-columns: 1fr; } }
</style>
