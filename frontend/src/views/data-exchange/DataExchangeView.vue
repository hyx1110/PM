<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { beijingNow } from '@/utils/time'
import { ElMessage } from 'element-plus'
import { confirmAction } from '@/utils/confirm'
import type { TagProps } from 'element-plus'
import { downloadExport, downloadImportTemplate, getImportJobs, uploadImportWorkbook } from '@/api/data-exchange'
import type { ImportJob } from '@/types/data-exchange'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import { getAllProjects } from '@/api/project'
import type { Project } from '@/types/project'

const loading = ref(false), importing = ref(false), detailVisible = ref(false)
const userStore = useUserStore()
const jobs = ref<ImportJob[]>([]), total = ref(0), selected = ref<ImportJob>(), selectedFile = ref<File>()
const projects = ref<Project[]>([])
const resource = ref(''), importQuery = reactive({ page: 1, page_size: 20, resource_type: undefined as string | undefined })
const exportForm = reactive({
  kind: 'schedules' as 'schedules'|'executions'|'process-report',
  range: [beijingNow().startOf('month').format('YYYY-MM-DD'), beijingNow().format('YYYY-MM-DD')],
  project_id: undefined as number | undefined,
  personnel_keyword: '',
  organization_keyword: '',
})
const resources = computed(() => {
  const roles = userStore.profile?.roles || []
  const items: Array<{ value: string; label: string }> = []
  if (roles.includes('super_admin')) items.push({ value: 'users', label: '用户' })
  if (roles.some((role) => ['super_admin', 'department_manager', 'functional_manager', 'project_manager'].includes(role))) {
    items.push({ value: 'projects', label: '项目' }, { value: 'tasks', label: '任务' })
  }
  return items
})
const canImport = computed(() =>
  userStore.hasPermission('import:manage') && resources.value.length > 0,
)
const statusTypes: Record<string, TagProps['type']> = { completed: 'success', partial: 'warning', failed: 'danger', processing: 'info' }

function saveBlob(blob: Blob, filename: string) { const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url) }
async function load() { loading.value = true; try { const page = await getImportJobs(importQuery); jobs.value = page.items; total.value = page.total } finally { loading.value = false } }
async function template() { if (!resource.value) return; saveBlob(await downloadImportTemplate(resource.value), `${resource.value}_import_template.xlsx`) }
function chooseFile(event: Event) { selectedFile.value = (event.target as HTMLInputElement).files?.[0] }
async function upload() {
  if (importing.value) return
  if (!resource.value) return ElMessage.warning('当前角色没有可导入的数据类型')
  if (!selectedFile.value) return ElMessage.warning('请选择 .xlsx 文件')
  importing.value = true
  try {
    if (!(await confirmAction(`导入类型：${resources.value.find(item => item.value === resource.value)?.label}\n文件：${selectedFile.value.name}\n确认导入？有效数据行将写入系统，失败行不会回滚已成功的行。项目导入后为草稿，须逐项补传立项报告再提交审批；父任务按现有规则进入审批流程。`, '导入数据', '确认导入'))) return
    const job = await uploadImportWorkbook(resource.value, selectedFile.value)
    ElMessage.success(`导入完成：成功 ${job.success_rows}，失败 ${job.failed_rows}`)
    if (resource.value === 'projects' && job.success_rows > 0) ElMessage.warning('项目已导入为草稿，请到项目管理逐项补传立项报告并提交审批')
    selectedFile.value = undefined
    await load()
  } catch { /* API interceptor displays the error. */ }
  finally { importing.value = false }
}
async function exportData() { if (!exportForm.range?.length) return ElMessage.warning('请选择日期范围'); const blob = await downloadExport(exportForm.kind, { start_date: exportForm.range[0], end_date: exportForm.range[1], project_id: exportForm.project_id, personnel_keyword: exportForm.personnel_keyword || undefined, organization_keyword: exportForm.organization_keyword || undefined }); saveBlob(blob, `${exportForm.kind}_${exportForm.range[0]}_${exportForm.range[1]}.xlsx`) }
function showErrors(item: ImportJob) { selected.value = item; detailVisible.value = true }
onMounted(async () => { resource.value = resources.value[0]?.value || ''; projects.value = await getAllProjects(); if (canImport.value) await load() })
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">数据导入导出</h1></div></header>
    <section class="exchange-grid" :class="{single:!canImport}">
      <article v-if="canImport" class="surface panel"><h2>Excel 数据导入</h2><el-form label-position="top"><el-form-item label="导入对象"><el-select v-model="resource" style="width:100%"><el-option v-for="item in resources" :key="item.value" :label="item.label" :value="item.value"/></el-select></el-form-item><el-form-item label="Excel 文件"><label class="file-picker"><input type="file" accept=".xlsx" @change="chooseFile"><span>{{ selectedFile?.name || '选择 .xlsx 文件' }}</span></label></el-form-item></el-form><div class="actions"><el-button @click="template">下载标准模板</el-button><el-button type="primary" :loading="importing" @click="upload">开始导入</el-button></div></article>
      <article class="surface panel"><h2>业务报表导出</h2><el-form label-position="top"><el-form-item label="报表类型"><el-select v-model="exportForm.kind" style="width:100%"><el-option label="人力排期明细" value="schedules"/><el-option label="任务执行明细" value="executions"/><el-option label="项目过程报表" value="process-report"/></el-select></el-form-item><el-form-item label="项目"><el-select v-model="exportForm.project_id" clearable filterable placeholder="全部可见项目" style="width:100%"><el-option v-for="item in projects" :key="item.id" :label="`${item.code} · ${item.name}`" :value="item.id"/></el-select></el-form-item><div class="export-filter-grid"><el-form-item label="人员"><el-input v-model="exportForm.personnel_keyword" clearable placeholder="姓名 / 工号"/></el-form-item><el-form-item label="组织"><el-input v-model="exportForm.organization_keyword" clearable placeholder="部门 / 组织"/></el-form-item></div><el-form-item label="业务日期"><el-date-picker v-model="exportForm.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" style="width:100%"/></el-form-item></el-form><div class="actions end"><el-button type="primary" @click="exportData">导出 Excel</el-button></div></article>
    </section>
    <section v-if="canImport" class="surface table-card" v-loading="loading"><div class="table-toolbar"><h2>导入记录</h2><el-select v-model="importQuery.resource_type" clearable placeholder="全部对象" style="width:140px" @change="importQuery.page=1;load()"><el-option v-for="item in resources" :key="item.value" :label="item.label" :value="item.value"/></el-select></div><el-table :data="jobs"><el-table-column prop="id" label="任务" width="80"/><el-table-column prop="resource_type" label="对象" width="100"/><el-table-column prop="original_filename" label="文件" min-width="200" show-overflow-tooltip/><el-table-column prop="operator_name" label="操作人" width="110"/><el-table-column label="结果" width="180"><template #default="{row}"><span class="counts"><b class="success">{{row.success_rows}}</b> 成功 / <b class="failed">{{row.failed_rows}}</b> 失败 / {{row.total_rows}} 总计</span></template></el-table-column><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusTypes[row.status]">{{row.status}}</el-tag></template></el-table-column><el-table-column label="时间" width="160"><template #default="{row}">{{formatDateTime(row.created_at)}}</template></el-table-column><el-table-column label="操作" width="90"><template #default="{row}"><el-button link type="primary" :disabled="!row.errors?.length" @click="showErrors(row)">错误明细</el-button></template></el-table-column></el-table><div class="table-footer"><el-pagination v-model:current-page="importQuery.page" :page-size="importQuery.page_size" layout="total, prev, pager, next" :total="total" @change="load"/></div></section>
    <el-dialog v-model="detailVisible" title="导入错误明细" width="720px"><el-table :data="selected?.errors || []" max-height="460"><el-table-column prop="row" label="Excel 行" width="90"/><el-table-column prop="field" label="字段" width="160"/><el-table-column prop="message" label="错误原因" min-width="330"/></el-table></el-dialog>
  </div>
</template>

<style scoped>
.exchange-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.panel{padding:25px}.panel h2,.table-toolbar h2{margin:8px 0;color:#2b394d;font-size:17px}.actions{display:flex;justify-content:space-between}.actions.end{justify-content:flex-end}.file-picker{display:flex;width:100%;height:40px;align-items:center;border:1px dashed #cbd3dc;border-radius:9px;background:#fafbfd;padding:0 12px;color:#66778a;cursor:pointer}.file-picker input{display:none}.table-toolbar{display:flex;align-items:center;justify-content:space-between;padding:11px 0}.counts{color:#7a8595;font-size:11px}.counts b{font-size:13px}.counts .success{color:#3f8b68}.counts .failed{color:#b65050}
.exchange-grid.single{grid-template-columns:1fr}
.export-filter-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
</style>
