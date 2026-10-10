<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadProjectInitiationReport, getProjectInitiationReport } from '@/api/project'
import type { ProjectInitiationReport } from '@/types/project'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  projectId?: number
  modelValue?: File | null
  editable?: boolean
  disabled?: boolean
  required?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [file: File | null] }>()
const fileInput = ref<HTMLInputElement>()
const report = ref<ProjectInitiationReport | null>(null)
const loading = ref(false)
const loadFailed = ref(false)
const downloading = ref(false)
let requestSequence = 0

async function refresh() {
  const sequence = ++requestSequence
  const projectId = props.projectId
  report.value = null
  loadFailed.value = false
  loading.value = Boolean(projectId)
  if (!projectId) return
  try {
    const result = await getProjectInitiationReport(projectId)
    if (sequence === requestSequence) report.value = result
  } catch {
    if (sequence === requestSequence) loadFailed.value = true
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function chooseFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || props.disabled || !props.editable) return
  if (!/\.(pdf|docx?|xlsx?|pptx?)$/i.test(file.name)) return ElMessage.warning('立项报告仅支持 Word（DOC/DOCX）、Excel（XLS/XLSX）、PPT（PPT/PPTX）或 PDF')
  if (!file.size || file.size > 20 * 1024 * 1024) return ElMessage.warning('请选择非空且不超过 20 MB 的立项报告')
  emit('update:modelValue', file)
}

const formatSize = (size: number) => size < 1024 * 1024 ? `${Math.ceil(size / 1024)} KB` : `${(size / 1024 / 1024).toFixed(1)} MB`

function validateRequired(): boolean {
  if (props.modelValue) return true
  if (loading.value) {
    ElMessage.warning('正在读取已上传的立项报告，请稍候再保存')
    return false
  }
  if (loadFailed.value) {
    ElMessage.warning('无法确认立项报告是否已上传，请重试读取或重新选择报告')
    return false
  }
  if (report.value) return true
  ElMessage.warning('项目立项报告为必传项，请先选择报告文件')
  return false
}

async function download() {
  if (!props.projectId || !report.value || downloading.value) return
  const filename = report.value.filename
  downloading.value = true
  try {
    const blob = await downloadProjectInitiationReport(props.projectId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch { /* The request interceptor displays the server error. */ }
  finally { downloading.value = false }
}

watch(() => props.projectId, refresh, { immediate: true })
onBeforeUnmount(() => { requestSequence += 1 })
defineExpose({ refresh, validateRequired })
</script>

<template>
  <div class="report-field">
    <div v-if="loading" class="report-hint">正在读取立项报告…</div>
    <div v-else-if="loadFailed" class="report-hint">附件信息加载失败 <el-button link type="primary" @click="refresh">重试</el-button></div>
    <div v-else-if="report" class="report-row">
      <el-button link type="primary" class="report-name" :loading="downloading" :disabled="disabled" @click="download">{{ report.filename }}</el-button>
      <span class="report-hint">{{ formatSize(report.size_bytes) }} · {{ formatDateTime(report.updated_at) }}</span>
      <el-button size="small" :loading="downloading" :disabled="disabled" @click="download">下载报告</el-button>
    </div>
    <span v-else-if="!modelValue" class="report-hint">暂未上传立项报告</span>
    <template v-if="editable">
      <input ref="fileInput" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx" hidden :disabled="disabled" @change="chooseFile" />
      <div class="report-row">
        <el-button :disabled="disabled" @click="fileInput?.click()">{{ modelValue || report ? '重新选择报告' : '选择立项报告' }}</el-button>
        <template v-if="modelValue">
          <span class="selected-report">{{ modelValue.name }}（{{ formatSize(modelValue.size) }}，待保存）</span>
          <el-button link type="danger" :disabled="disabled" @click="emit('update:modelValue', null)">取消选择</el-button>
        </template>
      </div>
      <p class="report-hint">{{ required ? '必传，' : '' }}限 1 个 Word（DOC/DOCX）、Excel（XLS/XLSX）、PPT（PPT/PPTX）或 PDF 文件，最大 20 MB。保存项目时上传，提交审批后不可更换。</p>
    </template>
  </div>
</template>

<style scoped>
.report-field{width:100%;display:grid;gap:8px;line-height:1.6}
.report-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.report-hint{margin:0;color:var(--el-text-color-secondary);font-size:12px}
.report-name{max-width:100%;height:auto;white-space:normal;text-align:left;overflow-wrap:anywhere}
.selected-report{font-size:13px;overflow-wrap:anywhere}
</style>
