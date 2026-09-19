<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getEvaluation, getProcessReport, updateEvaluation } from '@/api/report'
import { getAllProjects } from '@/api/project'
import type { Project } from '@/types/project'
import type { EvaluationPayload, ProcessReportItem } from '@/types/report'
import { formatDate } from '@/utils/format'
import { beijingNow } from '@/utils/time'

const loading = ref(false)
const items = ref<ProcessReportItem[]>([])
const total = ref(0)
const projects = ref<Project[]>([])
const query = reactive({
  page: 1, page_size: 50, project_id: undefined as number | undefined,
  personnel_keyword: '', organization_keyword: '',
  start_date: beijingNow().startOf('month').format('YYYY-MM-DD'),
  end_date: beijingNow().endOf('month').format('YYYY-MM-DD'),
})
const evaluationDialog = ref(false)
const evaluationTaskId = ref<number>()
const evaluationForm = reactive<EvaluationPayload>({ achievement_rate: 100, achievement_quality: 100, comment: '' })
const canEvaluate = (row: ProcessReportItem) => row.can_evaluate

async function loadProcess() {
  loading.value = true
  try {
    const result = await getProcessReport({ ...query })
    items.value = result.items
    total.value = result.total
  } finally { loading.value = false }
}

async function openEvaluation(row: ProcessReportItem) {
  evaluationTaskId.value = row.task_id
  const current = await getEvaluation(row.task_id)
  Object.assign(evaluationForm, current || { achievement_rate: row.achievement_rate ?? 100, achievement_quality: row.achievement_quality ?? 100, comment: '' })
  evaluationDialog.value = true
}

async function saveEvaluation() {
  if (!evaluationTaskId.value) return
  await updateEvaluation(evaluationTaskId.value, evaluationForm)
  ElMessage.success('达成评价已保存')
  evaluationDialog.value = false
  await loadProcess()
}

onMounted(async () => {
  projects.value = await getAllProjects()
  await loadProcess()
})
</script>

<template>
  <div class="page-shell">
    <header class="page-header">
      <div><h1 class="page-title">项目过程报表</h1><p class="page-subtitle">按当前账号可见项目展示；项目和任务完成后，由项目负责人、L3 或超级管理员进行一次性评价。</p></div>
    </header>
    <section class="surface report-card">
      <div class="report-filter">
        <el-select v-model="query.project_id" clearable filterable placeholder="项目" style="width:190px"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id"/></el-select>
        <el-input v-model="query.personnel_keyword" clearable placeholder="姓名 / 工号" style="width:170px" @keyup.enter="query.page=1;loadProcess()"/>
        <el-input v-model="query.organization_keyword" clearable placeholder="部门 / 组织" style="width:170px" @keyup.enter="query.page=1;loadProcess()"/>
        <el-date-picker v-model="query.start_date" type="date" value-format="YYYY-MM-DD" placeholder="开始日期"/>
        <el-date-picker v-model="query.end_date" type="date" value-format="YYYY-MM-DD" placeholder="结束日期"/>
        <el-button @click="query.page=1;loadProcess()">查询</el-button>
      </div>
      <el-table v-loading="loading" :data="items" stripe>
        <el-table-column prop="project_name" label="项目" fixed min-width="150"/>
        <el-table-column prop="level1_task" label="一级任务" fixed min-width="150"/>
        <el-table-column prop="level2_task" label="二级任务" min-width="160"/>
        <el-table-column prop="owner_name" label="负责人" width="120"/>
        <el-table-column label="计划开始" width="120"><template #default="{row}">{{formatDate(row.planned_start)}}</template></el-table-column>
        <el-table-column label="计划结束" width="120"><template #default="{row}">{{formatDate(row.planned_end)}}</template></el-table-column>
        <el-table-column label="实际开始" width="120"><template #default="{row}">{{formatDate(row.actual_start)}}</template></el-table-column>
        <el-table-column label="实际结束" width="120"><template #default="{row}">{{formatDate(row.actual_end)}}</template></el-table-column>
        <el-table-column label="预估人力" width="95"><template #default="{row}">{{row.estimated_hours}}h</template></el-table-column>
        <el-table-column label="实际人力" width="95"><template #default="{row}">{{row.actual_hours}}h</template></el-table-column>
        <el-table-column label="达成率" width="90"><template #default="{row}">{{row.achievement_rate==null?'—':`${row.achievement_rate}%`}}</template></el-table-column>
        <el-table-column label="达成质量" width="100"><template #default="{row}">{{row.achievement_quality==null?'—':`${row.achievement_quality}%`}}</template></el-table-column>
        <el-table-column prop="effective_status" label="状态" width="90"/>
        <el-table-column label="评价" fixed="right" width="120"><template #default="{row}"><el-tag v-if="row.evaluation_id" type="success" effect="plain">已完成评价</el-tag><el-button v-else-if="canEvaluate(row)" link type="primary" @click="openEvaluation(row)">评价</el-button><span v-else>—</span></template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="loadProcess"/></div>
    </section>
    <el-dialog v-model="evaluationDialog" title="任务达成评价" width="500px">
      <el-form :model="evaluationForm" label-position="top">
        <el-form-item label="达成率"><el-slider v-model="evaluationForm.achievement_rate" show-input :min="0" :max="100"/></el-form-item>
        <el-form-item label="达成质量"><el-slider v-model="evaluationForm.achievement_quality" show-input :min="0" :max="100"/></el-form-item>
        <el-form-item label="评价说明"><el-input v-model="evaluationForm.comment" type="textarea" :rows="4"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="evaluationDialog=false">取消</el-button><el-button type="primary" @click="saveEvaluation">保存评价</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>.report-card{padding:18px;overflow:hidden}.report-filter{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 18px}</style>
