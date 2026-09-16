<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { beijingNow } from '@/utils/time'
import { ElMessage } from 'element-plus'
import type { TagProps } from 'element-plus'
import { downloadExport, downloadImportTemplate, getImportJobs, uploadImportWorkbook } from '@/api/data-exchange'
import type { ImportJob } from '@/types/data-exchange'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const loading = ref(false), importing = ref(false), detailVisible = ref(false)
const userStore = useUserStore()
const jobs = ref<ImportJob[]>([]), total = ref(0), selected = ref<ImportJob>(), selectedFile = ref<File>()
const resource = ref('users'), importQuery = reactive({ page: 1, page_size: 20, resource_type: undefined as string | undefined })
const exportForm = reactive({ kind: 'schedules' as 'schedules'|'executions'|'process-report', range: [beijingNow().startOf('month').format('YYYY-MM-DD'), beijingNow().format('YYYY-MM-DD')] })
const resources = [{ value: 'users', label: '用户' }, { value: 'projects', label: '项目' }, { value: 'tasks', label: '任务' }]
const statusTypes: Record<string, TagProps['type']> = { completed: 'success', partial: 'warning', failed: 'danger', processing: 'info' }

function saveBlob(blob: Blob, filename: string) { const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url) }
async function load() { loading.value = true; try { const page = await getImportJobs(importQuery); jobs.value = page.items; total.value = page.total } finally { loading.value = false } }
async function template() { saveBlob(await downloadImportTemplate(resource.value), `${resource.value}_import_template.xlsx`) }
function chooseFile(event: Event) { selectedFile.value = (event.target as HTMLInputElement).files?.[0] }
async function upload() { if (!selectedFile.value) return ElMessage.warning('请选择 .xlsx 文件'); importing.value = true; try { const job = await uploadImportWorkbook(resource.value, selectedFile.value); ElMessage.success(`导入完成：成功 ${job.success_rows}，失败 ${job.failed_rows}`); selectedFile.value = undefined; await load() } finally { importing.value = false } }
async function exportData() { if (!exportForm.range?.length) return ElMessage.warning('请选择日期范围'); const blob = await downloadExport(exportForm.kind, { start_date: exportForm.range[0], end_date: exportForm.range[1] }); saveBlob(blob, `${exportForm.kind}_${exportForm.range[0]}_${exportForm.range[1]}.xlsx`) }
function showErrors(item: ImportJob) { selected.value = item; detailVisible.value = true }
onMounted(() => { if (userStore.hasPermission('import:manage')) load() })
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">数据导入导出</h1><p class="page-subtitle">通过标准 Excel 模板批量维护主数据，并导出排期、执行与项目过程报表。</p></div></header>
    <section class="exchange-grid" :class="{single:!userStore.hasPermission('import:manage')}">
      <article v-if="userStore.hasPermission('import:manage')" class="surface panel"><span class="overline">IMPORT</span><h2>Excel 数据导入</h2><p>先下载对应模板。系统逐行校验，成功行入库，失败行在任务明细中保留原因。</p><el-form label-position="top"><el-form-item label="导入对象"><el-select v-model="resource" style="width:100%"><el-option v-for="item in resources" :key="item.value" :label="item.label" :value="item.value"/></el-select></el-form-item><el-form-item label="Excel 文件"><label class="file-picker"><input type="file" accept=".xlsx" @change="chooseFile"><span>{{ selectedFile?.name || '选择 .xlsx 文件' }}</span></label></el-form-item></el-form><div class="actions"><el-button @click="template">下载标准模板</el-button><el-button type="primary" :loading="importing" @click="upload">开始导入</el-button></div></article>
      <article class="surface panel"><span class="overline">EXPORT</span><h2>业务报表导出</h2><p>日期和工时以真实 Excel 类型输出，可直接用于筛选、透视和后续统计。</p><el-form label-position="top"><el-form-item label="报表类型"><el-select v-model="exportForm.kind" style="width:100%"><el-option label="人力排期明细" value="schedules"/><el-option label="任务执行明细" value="executions"/><el-option label="项目过程报表" value="process-report"/></el-select></el-form-item><el-form-item label="业务日期"><el-date-picker v-model="exportForm.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" style="width:100%"/></el-form-item></el-form><div class="actions end"><el-button type="primary" @click="exportData">导出 Excel</el-button></div></article>
    </section>
    <section v-if="userStore.hasPermission('import:manage')" class="surface table-card" v-loading="loading"><div class="table-toolbar"><h2>导入记录</h2><el-select v-model="importQuery.resource_type" clearable placeholder="全部对象" style="width:140px" @change="importQuery.page=1;load()"><el-option v-for="item in resources" :key="item.value" :label="item.label" :value="item.value"/></el-select></div><el-table :data="jobs"><el-table-column prop="id" label="任务" width="80"/><el-table-column prop="resource_type" label="对象" width="100"/><el-table-column prop="original_filename" label="文件" min-width="200" show-overflow-tooltip/><el-table-column prop="operator_name" label="操作人" width="110"/><el-table-column label="结果" width="180"><template #default="{row}"><span class="counts"><b class="success">{{row.success_rows}}</b> 成功 / <b class="failed">{{row.failed_rows}}</b> 失败 / {{row.total_rows}} 总计</span></template></el-table-column><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusTypes[row.status]">{{row.status}}</el-tag></template></el-table-column><el-table-column label="时间" width="160"><template #default="{row}">{{formatDateTime(row.created_at)}}</template></el-table-column><el-table-column label="操作" width="90"><template #default="{row}"><el-button link type="primary" :disabled="!row.errors?.length" @click="showErrors(row)">错误明细</el-button></template></el-table-column></el-table><div class="table-footer"><el-pagination v-model:current-page="importQuery.page" :page-size="importQuery.page_size" layout="total, prev, pager, next" :total="total" @change="load"/></div></section>
    <el-dialog v-model="detailVisible" title="导入错误明细" width="720px"><el-table :data="selected?.errors || []" max-height="460"><el-table-column prop="row" label="Excel 行" width="90"/><el-table-column prop="field" label="字段" width="160"/><el-table-column prop="message" label="错误原因" min-width="330"/></el-table></el-dialog>
  </div>
</template>

<style scoped>
.exchange-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.panel{padding:25px}.overline{color:#7890aa;font-size:10px;font-weight:700;letter-spacing:.16em}.panel h2,.table-toolbar h2{margin:8px 0;color:#2b394d;font-size:17px}.panel>p{min-height:42px;margin:0 0 17px;color:#8490a0;font-size:12px;line-height:1.7}.actions{display:flex;justify-content:space-between}.actions.end{justify-content:flex-end}.file-picker{display:flex;width:100%;height:40px;align-items:center;border:1px dashed #cbd3dc;border-radius:9px;background:#fafbfd;padding:0 12px;color:#66778a;cursor:pointer}.file-picker input{display:none}.table-toolbar{display:flex;align-items:center;justify-content:space-between;padding:11px 0}.counts{color:#7a8595;font-size:11px}.counts b{font-size:13px}.counts .success{color:#3f8b68}.counts .failed{color:#b65050}
.exchange-grid.single{grid-template-columns:1fr}
</style>
