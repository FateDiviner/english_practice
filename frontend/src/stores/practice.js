import { defineStore } from 'pinia'

import { createPracticeSession, finishPracticeSession, submitPracticeAnswer } from '../api/practice'

export const usePracticeStore = defineStore('practice', {
  state: () => ({
    sessionId: null,
    mode: 'normal',
    wordbookId: null,
    count: 10,
    strictMode: true,
    total: 0,
    questions: [],
    currentIndex: 0,
    feedbackByWord: {},
    notice: '',
    phase: 'idle',
    summary: null,
    error: '',
  }),
  getters: {
    currentQuestion: (state) => state.questions[state.currentIndex] || null,
    currentFeedback: (state) => {
      const question = state.questions[state.currentIndex]
      return question ? state.feedbackByWord[question.word_id] || null : null
    },
    isLastQuestion: (state) => state.currentIndex >= state.questions.length - 1,
    answeredCount: (state) => Object.keys(state.feedbackByWord).length,
  },
  actions: {
    reset() {
      this.$patch({
        sessionId: null,
        total: 0,
        questions: [],
        currentIndex: 0,
        feedbackByWord: {},
        notice: '',
        phase: 'idle',
        summary: null,
        error: '',
      })
    },
    async startSession({ wordbookId = null, mode = 'normal', count = 10, strictMode = true }) {
      this.reset()
      this.wordbookId = wordbookId
      this.mode = mode
      this.count = count
      this.strictMode = strictMode
      this.phase = 'loading'
      try {
        const data = await createPracticeSession({
          wordbook_id: mode === 'normal' ? wordbookId : null,
          mode,
          count,
          strict_mode: strictMode,
        })
        this.$patch({
          sessionId: data.session_id,
          total: data.total,
          questions: data.questions,
          notice: data.notice || '',
          phase: 'answering',
        })
        return data
      } catch (error) {
        this.$patch({ phase: 'error', error: error.message || '练习创建失败' })
        throw error
      }
    },
    async submitAnswer(userInput, usedHint = false) {
      const question = this.currentQuestion
      if (!question || !['answering', 'submitting'].includes(this.phase)) return null
      this.phase = 'submitting'
      try {
        const result = await submitPracticeAnswer(this.sessionId, {
          word_id: question.word_id,
          user_input: userInput,
          used_hint: usedHint,
        })
        this.feedbackByWord[question.word_id] = result
        this.phase = 'submitted'
        return result
      } catch (error) {
        this.phase = 'answering'
        throw error
      }
    },
    async finish() {
      if (!this.sessionId) return null
      this.phase = 'finishing'
      try {
        this.summary = await finishPracticeSession(this.sessionId)
        this.phase = 'finished'
        return this.summary
      } catch (error) {
        this.phase = 'submitted'
        throw error
      }
    },
    async advance() {
      if (this.phase !== 'submitted') return
      if (this.isLastQuestion) {
        await this.finish()
        return
      }
      this.currentIndex += 1
      this.phase = 'answering'
    },
  },
})
