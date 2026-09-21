<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getMyTasks } from '@/api/task'
import type { Task } from '@/types/task'
import { formatDate } from '@/utils/format'

const loading = ref(false)
const tasks = ref<Task[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 20, status: '' })
const statuses = ['not_started', 'running', 'completed', 'delayed']
const statusLabel: Record<string, string> = {
  not_started: '未开始',
  running: '进行中',
  completed: '已完成',
  delayed: '已逾期',
}

async function load() {
  loading.value = true
  try {
    const result = await getMyTasks({
      page: query.page,
      page_size: query.page_size,
      status: query.status || undefined,
    })
    tasks.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-shell">
    <header class="page-header">
      <div><h1 class="page-title">我的任务</h1><p class="page-subtitle">只展示由你负责的任务，无需浏览完整项目管理结构。</p></div>
    </header>
    <section class="surface filter-bar">
      <el-select v-model="query.status" clearable placeholder="任务状态" style="width:160px">
        <el-option v-for="item in statuses" :key="item" :label="statusLabel[item]" :value="item" />
      </el-select>
      <el-button @click="query.page=1;load()">查询</el-button>
    </section>
    <section class="surface table-card">
      <el-table v-loading="loading" :data="tasks" stripe>
        <el-table-column prop="name" label="任务名称" min-width="180" />
        <el-table-column prop="project_name" label="所属项目" min-width="160" />
        <el-table-column prop="project_manager_name" label="项目经理" width="110" />
        <el-table-column label="计划开始" width="130"><template #default="{row}">{{ formatDate(row.planned_start) }}</template></el-table-column>
        <el-table-column label="计划结束" width="130"><template #default="{row}">{{ formatDate(row.planned_end) }}</template></el-table-column>
        <el-table-column label="预计工时" width="95"><template #default="{row}">{{ row.estimated_hours }}h</template></el-table-column>
        <el-table-column label="预约工时" width="95"><template #default="{row}">{{ row.booked_hours }}h</template></el-table-column>
        <el-table-column label="任务状态" width="105"><template #default="{row}"><el-tag :type="row.effective_status==='delayed'?'danger':row.effective_status==='completed'?'success':'info'" effect="plain">{{ statusLabel[row.effective_status] }}</el-tag></template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="load" /></div>
    </section>
  </div>
</template>
