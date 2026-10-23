<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { listWordbooks } from '../../api/wordbooks'
import PracticeComplete from '../../components/practice/PracticeComplete.vue'
import PracticeSetup from '../../components/practice/PracticeSetup.vue'
import QuestionCard from '../../components/practice/QuestionCard.vue'
import { usePracticeStore } from '../../stores/practice'
import { getErrorMessage } from '../../utils/errors'

const ALLOWED_COUNTS = [10, 20, 50]
const route = useRoute()
const practiceStore = usePracticeStore()
const wordbooks = ref([])
const isLoadingBooks = ref(true)
const setupError = ref('')
const actionError = ref('')
const answerInput = ref('')
const hintEnabled = ref(false)
const activeConfig = reactive({ mode: 'normal', wordbookId: null, count: 10, strictMode: true })

const initialMode = computed(() => (route.query.mode === 'wrong_only' ? 'wrong_only' : 'normal'))
const initialWordbookId = computed(() => {
  const value = Number(route.query.wordbook_id)
  return Number.isFinite(value) && value > 0 ? value : ''
})
const hasQuestions = computed(() => practiceStore.questions.length > 0)
const showSetup = computed(
  () =>
    !hasQuestions.value &&
    ['idle', 'error'].includes(practiceStore.phase) &&
    practiceStore.phase !== 'loading',
)

async function loadWordbooks() {
  isLoadingBooks.value = true
  try {
    const result = await listWordbooks({ page: 1, pageSize: 100 })
    wordbooks.value = result.items || []
  } catch {
    wordbooks.value = []
  } finally {
    isLoadingBooks.value = false
  }
}

function applyConfig(config) {
  activeConfig.mode = config.mode
  activeConfig.wordbookId = config.wordbookId
  activeConfig.count = config.count
  activeConfig.strictMode = config.strictMode
}

async function startPractice(config) {
  if (practiceStore.phase === 'loading') return
  setupError.value = ''
  actionError.value = ''
  answerInput.value = ''
  hintEnabled.value = false
  applyConfig(config)
  try {
    await practiceStore.startSession(config)
  } catch (error) {
    setupError.value = getErrorMessage(error, '这一轮暂时无法开始，请稍后再试。')
  }
}

function startFromQuery() {
  if (route.query.mode === 'wrong_only') {
    const requestedCount = Number(route.query.count)
    const count = ALLOWED_COUNTS.includes(requestedCount) ? requestedCount : 10
    startPractice({ mode: 'wrong_only', wordbookId: null, count, strictMode: true })
    return
  }
  if (initialWordbookId.value) {
    const requestedCount = Number(route.query.count)
    const count = ALLOWED_COUNTS.includes(requestedCount) ? requestedCount : 20
    startPractice({
      mode: 'normal',
      wordbookId: initialWordbookId.value,
      count,
      strictMode: route.query.strict !== 'false',
    })
  }
}

async function submitAnswer() {
  if (!answerInput.value.trim()) return
  actionError.value = ''
  try {
    await practiceStore.submitAnswer(answerInput.value, hintEnabled.value)
  } catch (error) {
    actionError.value = getErrorMessage(error, '答案暂未提交成功，请再试一次。')
  }
}

async function nextQuestion() {
  if (practiceStore.phase !== 'submitted') return
  actionError.value = ''
  try {
    await practiceStore.advance()
    answerInput.value = ''
    hintEnabled.value = false
  } catch (error) {
    actionError.value = getErrorMessage(error, '收卷时遇到问题，请再试一次。')
  }
}

function toggleHint() {
  hintEnabled.value = !hintEnabled.value
}

function replay() {
  startPractice({
    mode: activeConfig.mode,
    wordbookId: activeConfig.wordbookId,
    count: activeConfig.count,
    strictMode: activeConfig.strictMode,
  })
}

function handleGlobalKeydown(event) {
  if (event.key !== 'Enter' || event.isComposing) return
  const tagName = event.target?.tagName
  if (['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(tagName)) return
  if (practiceStore.phase === 'submitted') {
    event.preventDefault()
    nextQuestion()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleGlobalKeydown)
  await loadWordbooks()
  startFromQuery()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<template>
  <div class="app-page practice-page">
    <header class="page-header">
      <div class="page-header__copy">
        <p class="eyebrow">DICTATION ROOM</p>
        <h1 class="page-title">默写练习</h1>
        <p class="page-copy">先听、再看提示，然后把记忆里的拼写写到横线上。</p>
      </div>
      <span v-if="hasQuestions" class="practice-page__index">
        第 {{ practiceStore.currentIndex + 1 }} 题 / 共 {{ practiceStore.total }} 题
      </span>
    </header>

    <div v-if="practiceStore.phase === 'loading'" class="skeleton-stack" aria-label="正在出题">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <PracticeComplete
      v-else-if="practiceStore.phase === 'finished' && practiceStore.summary"
      :summary="practiceStore.summary"
      :mode="practiceStore.mode"
      @replay="replay"
    />

    <template v-else-if="hasQuestions && practiceStore.currentQuestion">
      <p v-if="practiceStore.notice" class="inline-notice practice-page__notice">
        {{ practiceStore.notice }}
      </p>
      <p
        v-if="actionError"
        class="inline-notice inline-notice--error practice-page__notice"
        role="alert"
      >
        {{ actionError }}
      </p>
      <QuestionCard
        :question="practiceStore.currentQuestion"
        :index="practiceStore.currentIndex"
        :total="practiceStore.total"
        :phase="practiceStore.phase"
        :feedback="practiceStore.currentFeedback"
        :model-value="answerInput"
        :hint-enabled="hintEnabled"
        :is-last="practiceStore.isLastQuestion"
        @update:model-value="answerInput = $event"
        @submit="submitAnswer"
        @next="nextQuestion"
        @toggle-hint="toggleHint"
      />
    </template>

    <PracticeSetup
      v-else-if="showSetup"
      :wordbooks="wordbooks"
      :is-loading="isLoadingBooks"
      :error-message="setupError"
      :initial-mode="initialMode"
      :initial-wordbook-id="initialWordbookId"
      @start="startPractice"
    />

    <section v-else class="state-panel state-panel--center">
      <h2 class="state-title">练习桌正在整理</h2>
      <p class="state-copy">请稍等片刻，或返回词书架重新选择一组词。</p>
    </section>
  </div>
</template>

<style scoped>
.practice-page {
  padding-bottom: 90px;
}

.practice-page__index {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}

.practice-page__notice {
  max-width: 780px;
  margin: 22px auto 0;
}
</style>
