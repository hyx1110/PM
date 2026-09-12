<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteWorkCalendarDay,
  getWorkCalendar,
  saveWorkCalendarDay,
} from '@/api/work-calendar'
import type { WorkCalendarDay } from '@/types/work-calendar'

const year = ref(new Date().getFullYear())
const loading = ref(false)
const items = ref<WorkCalendarDay[]>([])
const dialogVisible = ref(false)
const editingDate = ref('')
const form = reactive({
  work_date: '',
  day_type: 'holiday' as 'holiday' | 'workday',
  name: '',
  source: '',
})

async function load() {
  loading.value = true
  try {
    items.value = await getWorkCalendar(year.value)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingDate.value = ''
  Object.assign(form, {
    work_date: `${year.value}-01-01`,
    day_type: 'holiday',
    name: '',
    source: '',
  })
  dialogVisible.value = true
}

function openEdit(item: WorkCalendarDay) {
  editingDate.value = item.work_date
  Object.assign(form, {
    work_date: item.work_date,
    day_type: item.day_type,
    name: item.name,
    source: item.source || '',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.work_date || !form.name.trim()) {
    return ElMessage.warning('请选择日期并填写名称')
  }
  await saveWorkCalendarDay(form.work_date, {
    day_type: form.day_type,
    name: form.name.trim(),
    source: form.source.trim() || undefined,
  })
  ElMessage.success('工作日历已保存')
  dialogVisible.value = false
  year.value = Number(form.work_date.slice(0, 4))
  await load()
}

async function remove(item: WorkCalendarDay) {
  await ElMessageBox.confirm(
    `确认删除 ${item.work_date} 的日历覆盖规则吗？删除后将恢复按周一至周五判断。`,
    '删除日历规则',
    { type: 'warning' },
  )
  await deleteWorkCalendarDay(item.work_date)
  ElMessage.success('日历规则已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page-shell">
    <header class="page-header">
      <div>
        <h1 class="page-title">工作日历</h1>
        <p class="page-subtitle">L3 维护法定节假日和调休工作日；未配置日期默认周一至周五可预约。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增日期规则</el-button>
    </header>
    <el-alert title="系统迁移已内置 2026 年国务院公布的节假日及调休工作日，可在此维护后续年度。" type="info" :closable="false" show-icon/>
    <section class="surface filter-bar">
      <span>查看年度</span>
      <el-input-number v-model="year" :min="2000" :max="2100" :controls="false" style="width:120px"/>
      <el-button @click="load">查询</el-button>
    </section>
    <section class="surface table-card">
      <el-table v-loading="loading" :data="items" stripe>
        <el-table-column prop="work_date" label="日期" width="130"/>
        <el-table-column label="类型" width="130">
          <template #default="{row}"><el-tag :type="row.day_type==='holiday'?'danger':'success'">{{ row.day_type === 'holiday' ? '不可预约（节假日）' : '可预约（调休工作日）' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="160"/>
        <el-table-column prop="source" label="来源/依据" min-width="280" show-overflow-tooltip/>
        <el-table-column label="操作" width="130">
          <template #default="{row}"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" description="本年度没有覆盖规则，将按周一至周五作为工作日"/>
    </section>
    <el-dialog v-model="dialogVisible" :title="editingDate ? '编辑日期规则' : '新增日期规则'" width="520px">
      <el-form :model="form" label-position="top">
        <el-form-item label="日期" required><el-date-picker v-model="form.work_date" type="date" value-format="YYYY-MM-DD" :disabled="Boolean(editingDate)" style="width:100%"/></el-form-item>
        <el-form-item label="日期类型" required><el-radio-group v-model="form.day_type"><el-radio value="holiday">节假日（不可预约）</el-radio><el-radio value="workday">调休工作日（可预约）</el-radio></el-radio-group></el-form-item>
        <el-form-item label="名称" required><el-input v-model="form.name" maxlength="100" placeholder="例如：春节、法定调休工作日"/></el-form-item>
        <el-form-item label="来源/依据"><el-input v-model="form.source" maxlength="255" type="textarea" :rows="3"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>
