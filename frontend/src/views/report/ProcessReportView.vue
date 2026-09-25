<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'
import { getEvaluation, getProcessReport, updateEvaluation } from '@/api/report'
import { getAllProjects } from '@/api/project'
import { getDepartmentOptions, getOrganizationTree } from '@/api/organization'
import { getUserOptions } from '@/api/user'
import PersonnelScopeCascader from '@/components/common/PersonnelScopeCascader.vue'
import type { DepartmentOption, OrganizationNode } from '@/types/organization'
import type { Project } from '@/types/project'
import type { EvaluationPayload, ProcessReportItem } from '@/types/report'
import type { UserOption } from '@/types/user'
import { formatDate } from '@/utils/format'
import { beijingNow } from '@/utils/time'

const loading = ref(false)
const items = ref<ProcessReportItem[]>([])
const total = ref(0)
const projects = ref<Project[]>([])
const users = ref<UserOption[]>([])
const departments = ref<DepartmentOption[]>([])
const organizations = ref<OrganizationNode[]>([])
const filterScopes = ref<string[]>([])
const query = reactive({
  page: 1, page_size: 50, project_id: undefined as number | undefined,
  start_date: beijingNow().startOf('month').format('YYYY-MM-DD'),
  end_date: beijingNow().endOf('month').format('YYYY-MM-DD'),
})
const evaluationDialog = ref(false)
const evaluationProjectId = ref<number>()
const evaluationForm = reactive<EvaluationPayload>({ achievement_rate: 100, achievement_quality: 100, comment: '' })
const canEvaluate = (row: ProcessReportItem) => row.can_evaluate
const expandedTaskIds = ref<Set<number>>(new Set())

interface ReportTaskNode {
  row: ProcessReportItem
  children: ReportTaskNode[]
}

type ReportTreeRow = ProcessReportItem & {
  treeLevel: number
  hasChildren: boolean
}

const reportForest = computed<ReportTaskNode[]>(() => {
  const nodes = new Map<number, ReportTaskNode>()
  const rootsByProject = new Map<number, ReportTaskNode[]>()
  const projectOrder: number[] = []
  items.value.forEach((item) => nodes.set(item.task_id, { row: item, children: [] }))
  items.value.forEach((item) => {
    const node = nodes.get(item.task_id)!
    const parent = item.parent_id ? nodes.get(item.parent_id) : undefined
    if (parent && parent.row.project_id === item.project_id) {
      parent.children.push(node)
      return
    }
    if (!rootsByProject.has(item.project_id)) {
      rootsByProject.set(item.project_id, [])
      projectOrder.push(item.project_id)
    }
    rootsByProject.get(item.project_id)!.push(node)
  })
  return projectOrder.flatMap((projectId) => rootsByProject.get(projectId) || [])
})

const visibleReportRows = computed<ReportTreeRow[]>(() => {
  const rows: ReportTreeRow[] = []
  const visit = (node: ReportTaskNode, level: number) => {
    rows.push({ ...node.row, treeLevel: level, hasChildren: node.children.length > 0 })
    if (node.children.length && expandedTaskIds.value.has(node.row.task_id)) {
      node.children.forEach((child) => visit(child, level + 1))
    }
  }
  reportForest.value.forEach((node) => visit(node, 0))
  return rows
})

function resetExpandedTasks() {
  expandedTaskIds.value = new Set(
    items.value
      .map((item) => item.parent_id)
      .filter((id): id is number => Boolean(id)),
  )
}

function toggleTask(row: ReportTreeRow) {
  const next = new Set(expandedTaskIds.value)
  if (next.has(row.task_id)) next.delete(row.task_id)
  else next.add(row.task_id)
  expandedTaskIds.value = next
}

function formatPeriod(start?: string | null, end?: string | null, openEnded = false) {
  if (!start) return '—'
  return `${formatDate(start)} 至 ${end ? formatDate(end) : (openEnded ? '进行中' : '—')}`
}

async function loadProcess() {
  loading.value = true
  try {
    const result = await getProcessReport({
      ...query,
      personnel_scope: filterScopes.value.length ? filterScopes.value.join(',') : undefined,
    })
    items.value = result.items
    total.value = result.total
    resetExpandedTasks()
  } finally { loading.value = false }
}

async function openEvaluation(row: ProcessReportItem) {
  evaluationProjectId.value = row.project_id
  const current = await getEvaluation(row.project_id)
  Object.assign(evaluationForm, current || { achievement_rate: row.achievement_rate ?? 100, achievement_quality: row.achievement_quality ?? 100, comment: '' })
  evaluationDialog.value = true
}

async function saveEvaluation() {
  if (!evaluationProjectId.value) return
  await updateEvaluation(evaluationProjectId.value, evaluationForm)
  ElMessage.success('项目评价已保存')
  evaluationDialog.value = false
  await loadProcess()
}

const projectRowSpans = computed(() => {
  const spans = new Map<number, number>()
  for (let index = 0; index < visibleReportRows.value.length;) {
    let count = 1
    while (visibleReportRows.value[index + count]?.project_id === visibleReportRows.value[index].project_id) count += 1
    spans.set(index, count)
    for (let offset = 1; offset < count; offset += 1) spans.set(index + offset, 0)
    index += count
  }
  return spans
})

function spanMethod({ rowIndex, column }: { rowIndex: number; column: { property?: string } }) {
  if (!['project_name', 'achievement_rate', 'achievement_quality', 'project_evaluation'].includes(column.property || '')) return [1, 1]
  const span = projectRowSpans.value.get(rowIndex) ?? 1
  return span ? [span, 1] : [0, 0]
}

onMounted(async () => {
  [projects.value, users.value, departments.value, organizations.value] = await Promise.all([
    getAllProjects(), getUserOptions(), getDepartmentOptions(), getOrganizationTree(),
  ])
  await loadProcess()
})
</script>

<template>
  <div class="page-shell">
    <header class="page-header">
      <div><h1 class="page-title">项目过程报表</h1><p class="page-subtitle">按当前账号可见项目展示任务过程数据；项目完成后由本项目经理、部门主管或超级管理员进行一次项目级评价。</p></div>
    </header>
    <section class="surface report-card">
      <div class="report-filter">
        <el-select v-model="query.project_id" clearable filterable placeholder="项目" style="width:190px"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id"/></el-select>
        <PersonnelScopeCascader v-model="filterScopes" :users="users" :departments="departments" :organizations="organizations" placeholder="部门 / 组织 / 项目成员（可多选）" />
        <el-date-picker v-model="query.start_date" type="date" value-format="YYYY-MM-DD" placeholder="开始日期"/>
        <el-date-picker v-model="query.end_date" type="date" value-format="YYYY-MM-DD" placeholder="结束日期"/>
        <el-button @click="query.page=1;loadProcess()">查询</el-button>
      </div>
      <el-table v-loading="loading" :data="visibleReportRows" stripe :span-method="spanMethod" row-key="task_id" table-layout="fixed">
        <el-table-column prop="project_name" label="项目名称" fixed min-width="145" align="center" show-overflow-tooltip><template #default="{row}"><strong class="project-name">{{row.project_name}}</strong></template></el-table-column>
        <el-table-column prop="task_name" label="任务名称" fixed min-width="190">
          <template #default="{row}">
            <div class="task-cell" :style="{paddingLeft:`${row.treeLevel*22}px`}">
              <button v-if="row.hasChildren" class="tree-toggle" :title="expandedTaskIds.has(row.task_id)?'折叠子任务':'展开子任务'" @click="toggleTask(row)"><el-icon><ArrowDown v-if="expandedTaskIds.has(row.task_id)"/><ArrowRight v-else/></el-icon></button>
              <span v-else class="tree-spacer"></span>
              <span :title="row.task_path">{{row.task_name}}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="owner_name" label="项目成员" min-width="120" show-overflow-tooltip/>
        <el-table-column label="计划工期" min-width="170" align="center"><template #default="{row}">{{formatPeriod(row.planned_start,row.planned_end)}}</template></el-table-column>
        <el-table-column label="实际工期" min-width="170" align="center"><template #default="{row}">{{formatPeriod(row.actual_start,row.actual_end,true)}}</template></el-table-column>
        <el-table-column label="预估人力" min-width="100" align="center"><template #default="{row}">{{row.estimated_hours}}h</template></el-table-column>
        <el-table-column label="实际人力" min-width="100" align="center"><template #default="{row}">{{row.actual_hours}}h</template></el-table-column>
        <el-table-column prop="achievement_rate" label="项目达成率" min-width="110" align="center"><template #default="{row}">{{row.achievement_rate==null?'—':`${row.achievement_rate}%`}}</template></el-table-column>
        <el-table-column prop="achievement_quality" label="项目达成质量" min-width="120" align="center"><template #default="{row}">{{row.achievement_quality==null?'—':`${row.achievement_quality}%`}}</template></el-table-column>
        <el-table-column prop="effective_status" label="状态" min-width="95" align="center"/>
        <el-table-column prop="project_evaluation" label="项目评价" fixed="right" min-width="120" align="center"><template #default="{row}"><el-tag v-if="row.evaluation_id" type="success" effect="plain">已完成评价</el-tag><el-button v-else-if="canEvaluate(row)" link type="primary" @click="openEvaluation(row)">评价项目</el-button><span v-else>—</span></template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="loadProcess"/></div>
    </section>
    <el-dialog v-model="evaluationDialog" title="项目达成评价" width="500px">
      <el-form :model="evaluationForm" label-position="top">
        <el-form-item label="达成率"><el-slider v-model="evaluationForm.achievement_rate" show-input :min="0" :max="100"/></el-form-item>
        <el-form-item label="达成质量"><el-slider v-model="evaluationForm.achievement_quality" show-input :min="0" :max="100"/></el-form-item>
        <el-form-item label="评价说明"><el-input v-model="evaluationForm.comment" type="textarea" :rows="4"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="evaluationDialog=false">取消</el-button><el-button type="primary" @click="saveEvaluation">保存评价</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.report-card{padding:18px;overflow:hidden}.report-filter{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 18px}
.project-name{display:block;overflow:hidden;color:#334155;font-size:13px;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.task-cell{display:flex;min-width:0;align-items:center;gap:7px}.task-cell>span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tree-toggle{display:grid;width:24px;height:24px;flex:0 0 24px;place-items:center;border:0;border-radius:7px;background:transparent;color:#718096;cursor:pointer}.tree-toggle:hover{background:#edf3f8;color:#315f8e}.tree-spacer{width:24px;flex:0 0 24px}
</style>
