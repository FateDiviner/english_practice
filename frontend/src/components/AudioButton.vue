<script setup>
import { onBeforeUnmount, ref } from 'vue'

import { getWordAudio } from '../api/audio'

const props = defineProps({
  wordId: { type: Number, required: true },
  audioUrl: { type: String, default: '' },
  label: { type: String, default: '朗读' },
  compact: { type: Boolean, default: false },
})

const status = ref('idle')
let audioElement = null

async function playRemoteAudio(url) {
  audioElement?.pause()
  audioElement = new Audio(url)
  await audioElement.play()
}

function playTts() {
  if (!('speechSynthesis' in window)) throw new Error('当前浏览器不支持语音朗读')
  window.speechSynthesis.cancel()
  const isEnglishText = /^[A-Za-z][A-Za-z '-]*$/.test(props.label)
  const utterance = new SpeechSynthesisUtterance(isEnglishText ? props.label : 'word')
  utterance.lang = 'en-US'
  utterance.rate = 0.82
  window.speechSynthesis.speak(utterance)
}

async function play() {
  if (status.value === 'loading') return
  status.value = 'loading'
  try {
    if (props.audioUrl) {
      await playRemoteAudio(props.audioUrl)
    } else {
      const audio = await getWordAudio(props.wordId)
      if (audio?.audio_url) await playRemoteAudio(audio.audio_url)
      else playTts()
    }
    status.value = 'playing'
  } catch {
    status.value = 'error'
  } finally {
    window.setTimeout(() => {
      status.value = 'idle'
    }, 1200)
  }
}

onBeforeUnmount(() => {
  audioElement?.pause()
  window.speechSynthesis?.cancel()
})
</script>

<template>
  <button
    class="audio-button"
    :class="{ 'audio-button--compact': compact }"
    type="button"
    :aria-label="`${label}发音`"
    :title="status === 'error' ? '朗读失败，请稍后再试' : `${label}发音`"
    @click="play"
  >
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5 10V14H8L12 17V7L8 10H5Z" />
      <path d="M15 9C17 11 17 13 15 15" />
      <path v-if="status !== 'playing'" d="M17.5 6.5C21 9.5 21 14.5 17.5 17.5" />
      <path v-else d="M18 9L21 12M21 9L18 12" />
    </svg>
    <span>{{ status === 'loading' ? '载入' : compact ? '听' : '朗读' }}</span>
  </button>
</template>

<style scoped>
.audio-button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  padding: 5px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-small);
  background: transparent;
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  transition:
    border-color 160ms ease,
    background-color 160ms ease;
}

.audio-button:hover {
  border-color: var(--color-border-hover);
  background: var(--color-background-muted);
}

.audio-button svg {
  width: 17px;
  height: 17px;
}

.audio-button path {
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.7;
}

.audio-button--compact {
  gap: 4px;
  min-height: 28px;
  padding: 2px 7px;
}
</style>
