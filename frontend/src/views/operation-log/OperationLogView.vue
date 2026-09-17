<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getOperationLogs } from '@/api/operation-log'
import { getUserOptions } from '@/api/user'
import type { OperationLog } from '@/types/operation-log'
import type { UserOption } from '@/types/user'
import { formatDateTime } from '@/utils/format'

const loading=ref(false),logs=ref<OperationLog[]>([]),users=ref<UserOption[]>([]),total=ref(0),detailVisible=ref(false),selected=ref<OperationLog>()
const query=reactive({page:1,page_size:20,operator_id:undefined as number|undefined,module:'',start_date:'',end_date:''})
const modules=['user','organization','rbac','project','task','schedule','execution','evaluation']
const pretty=(value?:Record<string,unknown>)=>value?JSON.stringify(value,null,2):'—'
async function load(){loading.value=true;try{const result=await getOperationLogs({...query,module:query.module||undefined,start_date:query.start_date||undefined,end_date:query.end_date||undefined});logs.value=result.items;total.value=result.total}finally{loading.value=false}}
function open(row:OperationLog){selected.value=row;detailVisible.value=true}
onMounted(async()=>{users.value=await getUserOptions();await load()})
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">操作日志</h1><p class="page-subtitle">查看关键业务操作与共享看板修改前后数据。</p></div></header>
    <section class="surface filter-bar"><el-select v-model="query.operator_id" clearable filterable placeholder="操作人" style="width:160px"><el-option v-for="item in users" :key="item.id" :label="item.name" :value="item.id"/></el-select><el-select v-model="query.module" clearable placeholder="业务模块" style="width:160px"><el-option v-for="item in modules" :key="item" :value="item"/></el-select><el-date-picker v-model="query.start_date" type="date" value-format="YYYY-MM-DD" placeholder="开始日期"/><el-date-picker v-model="query.end_date" type="date" value-format="YYYY-MM-DD" placeholder="结束日期"/><el-button @click="query.page=1;load()">查询</el-button></section>
    <section class="surface table-card"><el-table v-loading="loading" :data="logs" stripe><el-table-column prop="operator_name" label="操作人" width="110"/><el-table-column prop="module" label="模块" width="110"/><el-table-column prop="change_summary" label="具体变化" min-width="360" show-overflow-tooltip/><el-table-column prop="reason" label="原因" min-width="140" show-overflow-tooltip/><el-table-column label="操作时间" width="155"><template #default="{row}">{{formatDateTime(row.created_at)}}</template></el-table-column><el-table-column label="详情" fixed="right" width="90"><template #default="{row}"><el-button link type="primary" @click="open(row)">查看</el-button></template></el-table-column></el-table><div class="table-footer"><el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :total="total" layout="total, sizes, prev, pager, next" @change="load"/></div></section>
    <el-dialog v-model="detailVisible" title="操作详情" width="900px"><div v-if="selected" class="diff"><section><h3>修改前</h3><pre>{{pretty(selected.before_data)}}</pre></section><section><h3>修改后</h3><pre>{{pretty(selected.after_data)}}</pre></section></div></el-dialog>
  </div>
</template>

<style scoped>.diff{display:grid;grid-template-columns:1fr 1fr;gap:14px}.diff section{min-width:0}.diff h3{margin:0 0 8px;color:#5e6a7c;font-size:12px}.diff pre{min-height:320px;margin:0;overflow:auto;border:1px solid #e6e9ed;border-radius:10px;background:#f8f9fb;padding:14px;color:#3e4a5b;font:11px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace}</style>
