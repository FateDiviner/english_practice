<script setup>
import { onBeforeUnmount, ref } from 'vue'

import { getWordAudio, getWordTtsAudio } from '../api/audio'

const props = defineProps({
  wordId: { type: Number, required: true },
  audioUrl: { type: String, default: '' },
  label: { type: String, default: '朗读' },
  ttsText: { type: String, default: '' },
  accent: { type: String, default: 'us' },
  compact: { type: Boolean, default: false },
})

const status = ref('idle')
let audioElement = null
let objectUrl = ''

function releaseAudio() {
  audioElement?.pause()
  audioElement = null
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = ''
  }
}

async function playUrl(url) {
  releaseAudio()
  const element = new Audio(url)
  audioElement = element
  await element.play()
}

async function playSystemAudio() {
  let blob
  try {
    blob = await getWordTtsAudio(props.wordId, props.accent)
  } catch {
    return false
  }
  if (!(blob instanceof Blob) || blob.size === 0) return false

  releaseAudio()
  objectUrl = URL.createObjectURL(blob)
  try {
    const element = new Audio(objectUrl)
    audioElement = element
    await element.play()
  } catch {
    return false
  }
  return true
}

function pickVoice(lang) {
  if (!('speechSynthesis' in window)) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  const sameLang = voices.filter((voice) => voice.lang === lang)
  const samePrefix = voices.filter((voice) => voice.lang?.startsWith(lang.slice(0, 2)))
  return (
    sameLang.find((voice) => voice.localService) ||
    sameLang[0] ||
    samePrefix.find((voice) => voice.localService) ||
    samePrefix[0] ||
    null
  )
}

function playTts(text) {
  if (!('speechSynthesis' in window)) throw new Error('当前浏览器不支持语音朗读')
  const isEnglishText = /^[A-Za-z][A-Za-z '-]*$/.test(text || '')
  const lang = props.accent === 'uk' ? 'en-GB' : 'en-US'
  const utterance = new SpeechSynthesisUtterance(isEnglishText ? text : 'word')
  utterance.lang = lang
  utterance.rate = 0.82
  const voice = pickVoice(lang)
  if (voice) utterance.voice = voice

  const synth = window.speechSynthesis
  if (synth.speaking || synth.pending) synth.cancel()
  synth.speak(utterance)
}

async function play() {
  if (status.value === 'loading') return
  status.value = 'loading'
  try {
    if (props.audioUrl) {
      await playUrl(props.audioUrl)
    } else {
      const audio = await getWordAudio(props.wordId)
      if (audio?.audio_url) {
        await playUrl(audio.audio_url)
      } else if (!(await playSystemAudio())) {
        playTts(audio?.tts_text || props.ttsText)
      }
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
  releaseAudio()
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
