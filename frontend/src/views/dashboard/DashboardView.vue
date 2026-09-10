<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Calendar, Collection, Timer, WarningFilled } from '@element-plus/icons-vue'
import { getDashboardSummary } from '@/api/report'
import type { DashboardSummary } from '@/types/report'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const data = ref<DashboardSummary>({ projects_total: 0, projects_running: 0, delayed_tasks: 0, pending_schedules: 0, today_schedules: 0 })
const cards = [
  { key: 'projects_total', label: '可见项目', icon: Collection, color: '#315f8e' },
  { key: 'projects_running', label: '进行中项目', icon: Timer, color: '#4b7b6b' },
  { key: 'pending_schedules', label: '待确认预约', icon: Calendar, color: '#92713c' },
  { key: 'delayed_tasks', label: '延期任务', icon: WarningFilled, color: '#a75858' },
] as const

onMounted(async () => {
  loading.value = true
  try { data.value = await getDashboardSummary() } finally { loading.value = false }
})
</script>

<template>
  <div class="page-shell" v-loading="loading">
    <header class="page-header">
      <div><h1 class="page-title">早上好，{{ userStore.profile?.name }}</h1><p class="page-subtitle">这里是当前项目与人力协同工作的简要概览。</p></div>
      <el-button type="primary" @click="$router.push('/schedules')">查看共享看板</el-button>
    </header>
    <section class="metrics">
      <article v-for="card in cards" :key="card.key" class="surface metric">
        <div class="metric-icon" :style="{ color: card.color, backgroundColor: `${card.color}14` }"><el-icon><component :is="card.icon" /></el-icon></div>
        <div><span>{{ card.label }}</span><strong>{{ data[card.key] }}</strong></div>
      </article>
    </section>
    <section class="dashboard-grid">
      <article class="surface focus-card">
        <div><span class="overline">TODAY</span><h2>今日共有 {{ data.today_schedules }} 条人力安排</h2><p>进入共享看板查看人员、项目和小时粒度排期。</p></div>
        <el-button plain @click="$router.push('/schedules')">打开看板</el-button>
      </article>
      <article class="surface guide-card">
        <h3>V1.0 工作闭环</h3>
        <ol><li>建立项目与项目成员</li><li>拆分两级任务并明确负责人</li><li>预约人力并由成员确认</li><li>填报实际执行数据</li><li>在过程报表完成评价</li></ol>
      </article>
    </section>
  </div>
</template>

<style scoped>
.metrics { display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; }
.metric { display: flex; align-items: center; gap: 16px; padding: 22px; }
.metric-icon { display: grid; width: 44px; height: 44px; place-items: center; border-radius: 13px; font-size: 20px; }
.metric span { display: block; color: #8993a1; font-size: 12px; }
.metric strong { display: block; margin-top: 3px; color: #202b3d; font-size: 27px; font-weight: 650; }
.dashboard-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 16px; }
.focus-card { display: flex; min-height: 220px; align-items: end; justify-content: space-between; padding: 30px; background: linear-gradient(135deg,#edf3f8,#fff); }
.overline { color: #6f89a3; font-size: 10px; font-weight: 700; letter-spacing: .18em; }
.focus-card h2 { margin: 12px 0 8px; color: #26364a; font-size: 23px; }
.focus-card p { margin: 0; color: #7c8796; font-size: 13px; }
.guide-card { padding: 25px 28px; }
.guide-card h3 { margin: 0 0 18px; color: #26364a; font-size: 15px; }
.guide-card ol { margin: 0; padding-left: 20px; color: #6f7988; font-size: 13px; line-height: 2.15; }
</style>

