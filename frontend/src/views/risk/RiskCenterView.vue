<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { TagProps } from 'element-plus'
import { handleRisk, getRisks, getRiskStats, syncRisks } from '@/api/risk'
import { getProjects } from '@/api/project'
import { getUserOptions } from '@/api/user'
import type { Project } from '@/types/project'
import type { RiskRecord, RiskStats } from '@/types/risk'
import type { UserOption } from '@/types/user'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false), syncing = ref(false), dialogVisible = ref(false)
const rows = ref<RiskRecord[]>([]), total = ref(0), selected = ref<RiskRecord>()
const projects = ref<Project[]>([]), users = ref<UserOption[]>([])
const stats = ref<RiskStats>({ total: 0, open: 0, resolved: 0, by_status: {}, by_level: {} })
const query = reactive({ page: 1, page_size: 20, status: 'open' as string | undefined, risk_type: undefined as string | undefined, risk_level: undefined as string | undefined, project_id: undefined as number | undefined, user_id: undefined as number | undefined })
const form = reactive({ status: 'resolved', handling_note: '' })
const typeLabels: Record<string, string> = { staffing_conflict: '人力冲突', workload_overload: '负载超限', task_delay: '任务延期', project_delay: '项目延期', long_unupdated: '久未更新' }
const levelTypes: Record<string, TagProps['type']> = { low: 'info', medium: 'warning', high: 'danger', critical: 'danger' }

async function load() {
  loading.value = true
  try { const [page, summary] = await Promise.all([getRisks(query), getRiskStats()]); rows.value = page.items; total.value = page.total; stats.value = summary } finally { loading.value = false }
}
async function scan() {
  syncing.value = true
  try { const result = await syncRisks(); ElMessage.success(`扫描完成：新增 ${result.created}，刷新 ${result.refreshed}，重开 ${result.reopened}`); await load() } finally { syncing.value = false }
}
function openHandle(item: RiskRecord) { selected.value = item; form.status = 'resolved'; form.handling_note = ''; dialogVisible.value = true }
async function submitHandle() {
  if (!selected.value || !form.handling_note.trim()) return ElMessage.warning('请填写处理说明')
  await handleRisk(selected.value.id, form)
  ElMessage.success('风险状态已更新')
  dialogVisible.value = false
  await load()
}
onMounted(async () => { const [p, u] = await Promise.all([getProjects({ page: 1, page_size: 200 }), getUserOptions()]); projects.value = p.items; users.value = u; await load() })
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">风险中心</h1><p class="page-subtitle">集中发现人力冲突、负载超限、任务/项目延期和长期未更新事项。</p></div><el-button v-if="userStore.hasPermission('risk:handle')" type="primary" :loading="syncing" @click="scan">立即扫描</el-button></header>
    <section class="risk-metrics">
      <article class="surface metric"><span>风险总数</span><strong>{{ stats.total }}</strong></article>
      <article class="surface metric open"><span>未关闭</span><strong>{{ stats.open }}</strong></article>
      <article class="surface metric critical"><span>严重风险</span><strong>{{ stats.by_level.critical || 0 }}</strong></article>
      <article class="surface metric resolved"><span>已关闭</span><strong>{{ stats.resolved }}</strong></article>
    </section>
    <section class="surface filter-bar">
      <el-select v-model="query.status" clearable placeholder="处理状态" style="width:130px"><el-option label="待处理" value="open"/><el-option label="处理中" value="handling"/><el-option label="已解决" value="resolved"/><el-option label="已忽略" value="ignored"/></el-select>
      <el-select v-model="query.risk_type" clearable placeholder="风险类型" style="width:150px"><el-option v-for="(label,key) in typeLabels" :key="key" :label="label" :value="key"/></el-select>
      <el-select v-model="query.risk_level" clearable placeholder="风险等级" style="width:130px"><el-option label="一般" value="medium"/><el-option label="高" value="high"/><el-option label="严重" value="critical"/></el-select>
      <el-select v-model="query.project_id" clearable filterable placeholder="项目" style="width:190px"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id"/></el-select>
      <el-select v-model="query.user_id" clearable filterable placeholder="责任人" style="width:150px"><el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id"/></el-select>
      <el-button type="primary" plain @click="query.page=1;load()">查询</el-button>
    </section>
    <section class="surface table-card" v-loading="loading">
      <el-table :data="rows">
        <el-table-column label="等级" width="82"><template #default="{row}"><el-tag :type="levelTypes[row.risk_level]" effect="light">{{ row.risk_level }}</el-tag></template></el-table-column>
        <el-table-column label="风险" min-width="250"><template #default="{row}"><strong class="risk-title">{{ row.title }}</strong><small>{{ row.detail }}</small></template></el-table-column>
        <el-table-column prop="project_name" label="项目" min-width="150" show-overflow-tooltip/>
        <el-table-column prop="task_name" label="任务" min-width="140" show-overflow-tooltip/>
        <el-table-column prop="user_name" label="责任人" width="100"/>
        <el-table-column label="检测时间" width="160"><template #default="{row}">{{ formatDateTime(row.detected_at) }}</template></el-table-column>
        <el-table-column label="状态" width="95"><template #default="{row}"><el-tag type="info">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="90" fixed="right"><template #default="{row}"><el-button v-if="userStore.hasPermission('risk:handle')&&['open','handling'].includes(row.status)" link type="primary" @click="openHandle(row)">处理</el-button></template></el-table-column>
      </el-table>
      <div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" layout="total, prev, pager, next" :total="total" @change="load"/></div>
    </section>
    <el-dialog v-model="dialogVisible" title="处理风险" width="520px"><el-form label-position="top"><el-form-item label="处理结果"><el-radio-group v-model="form.status"><el-radio-button value="handling">处理中</el-radio-button><el-radio-button value="resolved">已解决</el-radio-button><el-radio-button value="ignored">忽略</el-radio-button></el-radio-group></el-form-item><el-form-item label="处理说明" required><el-input v-model="form.handling_note" type="textarea" :rows="4" maxlength="2000" show-word-limit/></el-form-item></el-form><template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="submitHandle">保存</el-button></template></el-dialog>
  </div>
</template>

<style scoped>
.risk-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.metric{padding:20px 22px;border-left:3px solid #7792ad}.metric span{display:block;color:#8490a0;font-size:12px}.metric strong{display:block;margin-top:6px;color:#253348;font-size:27px}.metric.open{border-left-color:#d19a4d}.metric.critical{border-left-color:#b94c4c}.metric.resolved{border-left-color:#4f8b6f}.risk-title,.risk-title+small{display:block}.risk-title{color:#3a4659;font-size:13px}.risk-title+small{margin-top:5px;color:#8b95a3;font-size:11px;line-height:1.5}
</style>
