<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { getAdminImportJob, importAdminWords, listAdminWordbooks } from '../../api/admin'
import ImportPreview from '../../components/admin/ImportPreview.vue'
import ImportResultPanel from '../../components/admin/ImportResultPanel.vue'
import ImportStepper from '../../components/admin/ImportStepper.vue'
import { getErrorMessage } from '../../utils/errors'
import {
  IMPORT_FIELDS,
  parseDelimited,
  suggestMapping,
  validateImportRows,
} from '../../utils/delimited'

const STEPS = ['上传文件', '列映射', '预览校验', '确认导入', '导入结果']
const POLL_INTERVAL_MS = 1200
const TEXT_FILE_PATTERN = /\.(csv|tsv|txt)$/i
const currentStep = ref(1)
const wordbooks = ref([])
const selectedWordbookId = ref('')
const selectedFile = ref(null)
const headers = ref([])
const rows = ref([])
const mapping = reactive({})
const isReadingFile = ref(false)
const fileError = ref('')
const errorMessage = ref('')
const isImporting = ref(false)
const importJob = ref(null)
const jobError = ref('')
let pollTimer = null

const validationErrors = computed(() => validateImportRows(headers.value, rows.value, mapping))
const canContinue = computed(() => {
  if (currentStep.value === 1) {
    return Boolean(selectedWordbookId.value && selectedFile.value && headers.value.length)
  }
  if (currentStep.value === 2) return mapping.spelling !== undefined && mapping.spelling !== ''
  if (currentStep.value === 3) return validationErrors.value.length === 0 && rows.value.length > 0
  return true
})
const selectedWordbook = computed(() =>
  wordbooks.value.find((book) => book.id === Number(selectedWordbookId.value)),
)

async function loadWordbooks() {
  try {
    const result = await listAdminWordbooks({ page: 1, pageSize: 100 })
    wordbooks.value = result.items || []
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '词书列表暂时无法读取。')
  }
}

function clearPolling() {
  if (pollTimer) window.clearTimeout(pollTimer)
  pollTimer = null
}

async function handleFile(event) {
  const file = event.target.files?.[0] || null
  selectedFile.value = file
  headers.value = []
  rows.value = []
  fileError.value = ''
  for (const key of Object.keys(mapping)) delete mapping[key]
  if (!file) return
  if (!TEXT_FILE_PATTERN.test(file.name)) {
    fileError.value = '浏览器预览目前支持 CSV / TSV；Excel 文件请先另存为 CSV 再导入。'
    return
  }
  isReadingFile.value = true
  try {
    const parsed = parseDelimited(await file.text())
    if (parsed.length < 2) {
      fileError.value = '文件至少需要一行表头和一行数据。'
      return
    }
    headers.value = parsed[0]
    rows.value = parsed.slice(1)
    Object.assign(mapping, suggestMapping(headers.value))
  } catch {
    fileError.value = '文件读取失败，请确认编码与格式后重试。'
  } finally {
    isReadingFile.value = false
  }
}

function goNext() {
  errorMessage.value = ''
  if (!canContinue.value) {
    errorMessage.value = '请先完成当前步骤中的必填项。'
    return
  }
  if (currentStep.value < 4) currentStep.value += 1
}

function goBack() {
  errorMessage.value = ''
  if (currentStep.value > 1 && currentStep.value < 5) currentStep.value -= 1
}

async function confirmImport() {
  if (isImporting.value) return
  isImporting.value = true
  errorMessage.value = ''
  jobError.value = ''
  try {
    const result = await importAdminWords(Number(selectedWordbookId.value), selectedFile.value, {
      ...mapping,
    })
    importJob.value = { id: result.import_job_id, status: 'pending' }
    currentStep.value = 5
    scheduleJobPolling()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '导入任务没有创建成功，请稍后再试。')
  } finally {
    isImporting.value = false
  }
}

async function loadImportJob() {
  if (!importJob.value?.id) return
  try {
    importJob.value = await getAdminImportJob(importJob.value.id)
    jobError.value = ''
    if (['pending', 'processing'].includes(importJob.value.status)) scheduleJobPolling()
  } catch (error) {
    jobError.value = getErrorMessage(error, '暂时无法读取导入进度。')
  }
}

function scheduleJobPolling() {
  clearPolling()
  pollTimer = window.setTimeout(loadImportJob, POLL_INTERVAL_MS)
}

function restart() {
  clearPolling()
  currentStep.value = 1
  selectedFile.value = null
  headers.value = []
  rows.value = []
  importJob.value = null
  jobError.value = ''
  errorMessage.value = ''
  for (const key of Object.keys(mapping)) delete mapping[key]
}

onMounted(loadWordbooks)
onBeforeUnmount(clearPolling)
</script>

<template>
  <div class="app-page admin-page">
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">THE INTAKE DESK</p>
        <h1 class="page-title">单词导入向导</h1>
        <p class="page-copy">按五个步骤完成文件解析、字段映射、预览校验与正式导入。</p>
      </div>
    </header>

    <ImportStepper :current="currentStep" :steps="STEPS" />
    <p v-if="errorMessage" class="inline-notice inline-notice--error wizard-notice" role="alert">
      {{ errorMessage }}
    </p>

    <section class="wizard-step surface">
      <template v-if="currentStep === 1">
        <div class="step-heading">
          <span>STEP 01</span>
          <h2>选择目标词书与文件</h2>
          <p>支持 CSV / TSV 文件。第一行必须是表头，文件内容只在浏览器内做预览。</p>
        </div>
        <label class="field">
          <span class="field-label">目标词书</span>
          <select v-model="selectedWordbookId" class="field-input">
            <option value="" disabled>请选择一本词书</option>
            <option v-for="book in wordbooks" :key="book.id" :value="book.id">
              {{ book.name }}
            </option>
          </select>
        </label>
        <label class="file-drop">
          <span class="file-drop__title">{{ selectedFile ? selectedFile.name : '选择文件' }}</span>
          <span class="file-drop__hint">CSV / TSV / TXT · 首行为表头</span>
          <input type="file" accept=".csv,.tsv,.txt,.xlsx,.xls" @change="handleFile" />
        </label>
        <p v-if="isReadingFile" class="field-help">正在读取文件…</p>
        <p v-if="fileError" class="inline-notice inline-notice--error" role="alert">
          {{ fileError }}
        </p>
      </template>

      <template v-else-if="currentStep === 2">
        <div class="step-heading">
          <span>STEP 02</span>
          <h2>把表格列对应到单词字段</h2>
          <p>拼写是必填字段；其余字段可以不导入。</p>
        </div>
        <div class="mapping-grid">
          <label v-for="field in IMPORT_FIELDS" :key="field.key" class="field">
            <span class="field-label">{{ field.label }}<b v-if="field.required"> *</b></span>
            <select v-model="mapping[field.key]" class="field-input">
              <option value="">不导入</option>
              <option
                v-for="(header, index) in headers"
                :key="`${field.key}-${index}`"
                :value="String(index)"
              >
                {{ header || `第 ${index + 1} 列` }}
              </option>
            </select>
          </label>
        </div>
      </template>

      <template v-else-if="currentStep === 3">
        <div class="step-heading">
          <span>STEP 03</span>
          <h2>预览与校验</h2>
          <p>检查前 20 行样本，并在正式导入前处理空拼写或重复行。</p>
        </div>
        <ImportPreview :headers="headers" :rows="rows" :errors="validationErrors" />
      </template>

      <template v-else-if="currentStep === 4">
        <div class="step-heading">
          <span>STEP 04</span>
          <h2>确认这份导入清单</h2>
          <p>确认后将把同一文件与列映射提交给导入接口。</p>
        </div>
        <dl class="confirm-list">
          <div>
            <dt>目标词书</dt>
            <dd>{{ selectedWordbook?.name }}</dd>
          </div>
          <div>
            <dt>文件</dt>
            <dd>{{ selectedFile?.name }}</dd>
          </div>
          <div>
            <dt>数据行</dt>
            <dd>{{ rows.length }} 行</dd>
          </div>
          <div>
            <dt>映射字段</dt>
            <dd>{{ Object.keys(mapping).length }} 个</dd>
          </div>
          <div>
            <dt>校验问题</dt>
            <dd>{{ validationErrors.length }} 个</dd>
          </div>
        </dl>
        <button class="primary-button" type="button" :disabled="isImporting" @click="confirmImport">
          {{ isImporting ? '正在创建任务…' : '确认并开始导入' }}
        </button>
      </template>

      <ImportResultPanel
        v-else
        :job="importJob"
        :error="jobError"
        :fallback-total="rows.length"
        @restart="restart"
      />
    </section>

    <footer v-if="currentStep < 5" class="wizard-footer">
      <button v-if="currentStep > 1" class="secondary-button" type="button" @click="goBack">
        上一步
      </button>
      <span v-else></span>
      <button
        v-if="currentStep < 4"
        class="primary-button"
        type="button"
        :disabled="!canContinue"
        @click="goNext"
      >
        下一步
      </button>
    </footer>
  </div>
</template>

<style scoped src="./ImportWizard.css"></style>
