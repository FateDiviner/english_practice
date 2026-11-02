<script setup>
import { computed, ref } from 'vue'

import AudioButton from '../AudioButton.vue'
import GradeMark from '../GradeMark.vue'
import SpellInput from '../SpellInput.vue'

const props = defineProps({
  question: { type: Object, required: true },
  index: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  phase: { type: String, default: 'answering' },
  feedback: { type: Object, default: null },
  modelValue: { type: String, default: '' },
  hintEnabled: { type: Boolean, default: false },
  isLast: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'submit', 'next', 'toggle-hint'])
const accent = ref('uk')
const spellInput = ref(null)

const phonetic = computed(() => {
  if (accent.value === 'us') return props.question.phonetic_us || props.question.phonetic_uk || '—'
  return props.question.phonetic_uk || props.question.phonetic_us || '—'
})
const hasBothPhonetics = computed(() => props.question.phonetic_uk && props.question.phonetic_us)
const isSubmitted = computed(() => ['submitted', 'finishing', 'finished'].includes(props.phase))
const isBusy = computed(() => ['submitting', 'finishing'].includes(props.phase))
const status = computed(() => {
  if (!isSubmitted.value) return 'default'
  return props.feedback?.is_correct ? 'correct' : 'wrong'
})

function submit() {
  if (isBusy.value || isSubmitted.value || !props.modelValue.trim()) return
  emit('submit')
}

defineExpose({ focus: () => spellInput.value?.focus() })
</script>

<template>
  <article class="question-card surface">
    <header class="question-card__header">
      <div>
        <p class="eyebrow">DICTATION · {{ String(index + 1).padStart(2, '0') }}</p>
        <span>{{ index + 1 }} / {{ total }}</span>
      </div>
      <div class="question-card__progress" aria-hidden="true">
        <span :style="{ width: `${((index + 1) / total) * 100}%` }"></span>
      </div>
    </header>

    <div class="question-card__prompt">
      <div class="prompt-phonetic">
        <div v-if="hasBothPhonetics" class="accent-switch" role="group" aria-label="音标口音">
          <button
            type="button"
            :class="{ 'accent-switch__item--active': accent === 'uk' }"
            @click="accent = 'uk'"
          >
            UK
          </button>
          <button
            type="button"
            :class="{ 'accent-switch__item--active': accent === 'us' }"
            @click="accent = 'us'"
          >
            US
          </button>
        </div>
        <strong>{{ phonetic }}</strong>
        <AudioButton
          :key="`${question.word_id}-${accent}`"
          :word-id="question.word_id"
          :audio-url="question.audio_url || ''"
          :accent="accent"
          label="单词"
        />
      </div>
      <p class="prompt-pos">{{ question.part_of_speech || '词汇' }}</p>
      <h2 class="prompt-meaning">{{ question.meaning_cn || '请根据音标与提示默写单词' }}</h2>
    </div>

    <div class="answer-area">
      <SpellInput
        ref="spellInput"
        :model-value="modelValue"
        :disabled="isBusy || isSubmitted"
        :status="status"
        :hint="hintEnabled ? question.hint : null"
        aria-label="默写答案"
        @update:model-value="emit('update:modelValue', $event)"
        @submit="submit"
      />
      <div class="answer-area__tools">
        <button
          class="text-link"
          type="button"
          :disabled="isSubmitted"
          @click="emit('toggle-hint')"
        >
          {{ hintEnabled ? '收起长度提示' : '需要长度提示' }}
        </button>
        <span v-if="hintEnabled" class="answer-area__hint">
          {{ question.hint?.length || 0 }} 个字母
        </span>
      </div>
    </div>

    <Transition name="feedback">
      <section
        v-if="isSubmitted"
        class="feedback"
        :class="feedback?.is_correct ? 'feedback--correct' : 'feedback--wrong'"
      >
        <div class="feedback__headline">
          <GradeMark :type="feedback?.is_correct ? 'correct' : 'wrong'" :size="42" />
          <div>
            <strong>{{ feedback?.is_correct ? '拼写正确' : '再记一遍这个词' }}</strong>
            <p v-if="feedback?.is_correct">把它留在记忆里，继续下一页。</p>
            <p v-else>
              正确拼写：
              <b class="feedback__answer">{{ feedback?.correct_spelling }}</b>
            </p>
          </div>
        </div>
        <div v-if="feedback?.example_en || feedback?.example_cn" class="feedback__example">
          <p v-if="feedback.example_en">{{ feedback.example_en }}</p>
          <p v-if="feedback.example_cn">{{ feedback.example_cn }}</p>
        </div>
      </section>
    </Transition>

    <footer class="question-card__footer">
      <button
        v-if="!isSubmitted"
        class="primary-button"
        type="button"
        :disabled="isBusy || !modelValue.trim()"
        @click="submit"
      >
        {{ isBusy ? '正在核对…' : '提交答案' }}
      </button>
      <button v-else class="primary-button" type="button" :disabled="isBusy" @click="emit('next')">
        {{ isLast ? (isBusy ? '正在收卷…' : '完成本轮') : '下一题' }}
      </button>
      <span v-if="!isSubmitted" class="question-card__enter-note">按 Enter 提交</span>
      <span v-else class="question-card__enter-note">按 Enter 继续</span>
    </footer>
  </article>
</template>

<style scoped src="./QuestionCard.css"></style>
