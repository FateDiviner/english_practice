<script setup>
import { reactive, ref, watch } from 'vue'

import { createAdminWord, updateAdminWord } from '../../api/admin'
import AdminDrawer from '../AdminDrawer.vue'
import { getErrorMessage, hasBusinessCode } from '../../utils/errors'

const props = defineProps({
  open: { type: Boolean, default: false },
  word: { type: Object, default: null },
  wordbookId: { type: Number, required: true },
  wordbookName: { type: String, default: '' },
})

const emit = defineEmits(['close', 'saved'])
const form = reactive({
  id: null,
  spelling: '',
  phonetic_uk: '',
  phonetic_us: '',
  meaning_cn: '',
  part_of_speech: '',
  example_en: '',
  example_cn: '',
  audio_url: '',
  sort_order: 0,
})
const isSaving = ref(false)
const formError = ref('')

function resetForm() {
  const word = props.word
  Object.assign(form, {
    id: word?.id || null,
    spelling: word?.spelling || '',
    phonetic_uk: word?.phonetic_uk || '',
    phonetic_us: word?.phonetic_us || '',
    meaning_cn: word?.meaning_cn || '',
    part_of_speech: word?.part_of_speech || '',
    example_en: word?.example_en || '',
    example_cn: word?.example_cn || '',
    audio_url: word?.audio_url || '',
    sort_order: word?.sort_order || 0,
  })
  formError.value = ''
}

async function saveWord() {
  if (!form.spelling.trim()) {
    formError.value = '单词拼写不能为空。'
    return
  }
  isSaving.value = true
  formError.value = ''
  const payload = {
    spelling: form.spelling.trim(),
    phonetic_uk: form.phonetic_uk.trim() || null,
    phonetic_us: form.phonetic_us.trim() || null,
    meaning_cn: form.meaning_cn.trim() || null,
    part_of_speech: form.part_of_speech.trim() || null,
    example_en: form.example_en.trim() || null,
    example_cn: form.example_cn.trim() || null,
    audio_url: form.audio_url.trim() || null,
    sort_order: Number(form.sort_order) || 0,
  }
  try {
    if (form.id) await updateAdminWord(form.id, payload)
    else await createAdminWord(props.wordbookId, payload)
    emit('saved', form.id ? '单词信息已更新。' : '新单词已加入词书。')
  } catch (error) {
    formError.value = hasBusinessCode(error, 40901)
      ? '这本词书中已经有相同拼写的单词。'
      : getErrorMessage(error, '单词没有保存成功。')
  } finally {
    isSaving.value = false
  }
}

watch(
  () => [props.open, props.word],
  ([isOpen]) => {
    if (isOpen) resetForm()
  },
  { immediate: true },
)
</script>

<template>
  <AdminDrawer
    :open="open"
    :title="form.id ? '编辑单词' : '新增单词'"
    :description="`正在编辑：${wordbookName}`"
    @close="$emit('close')"
  >
    <form class="form-grid" @submit.prevent="saveWord">
      <label class="field">
        <span class="field-label">拼写</span>
        <input v-model="form.spelling" class="field-input" maxlength="100" />
      </label>
      <label class="field">
        <span class="field-label">词性</span>
        <input
          v-model="form.part_of_speech"
          class="field-input"
          maxlength="20"
          placeholder="n. / v. / adj."
        />
      </label>
      <label class="field">
        <span class="field-label">英式音标</span>
        <input v-model="form.phonetic_uk" class="field-input" maxlength="100" />
      </label>
      <label class="field">
        <span class="field-label">美式音标</span>
        <input v-model="form.phonetic_us" class="field-input" maxlength="100" />
      </label>
      <label class="field form-grid__wide">
        <span class="field-label">中文释义</span>
        <input v-model="form.meaning_cn" class="field-input" maxlength="255" />
      </label>
      <label class="field form-grid__wide">
        <span class="field-label">英文例句</span>
        <textarea v-model="form.example_en" class="field-input form-textarea" rows="3"></textarea>
      </label>
      <label class="field form-grid__wide">
        <span class="field-label">例句译文</span>
        <textarea v-model="form.example_cn" class="field-input form-textarea" rows="3"></textarea>
      </label>
      <label class="field form-grid__wide">
        <span class="field-label">音频地址</span>
        <input
          v-model="form.audio_url"
          class="field-input"
          maxlength="255"
          placeholder="留空则由浏览器 TTS 朗读"
        />
      </label>
      <label class="field">
        <span class="field-label">排序</span>
        <input v-model.number="form.sort_order" class="field-input" type="number" min="0" />
      </label>
      <p v-if="formError" class="inline-notice inline-notice--error form-grid__wide" role="alert">
        {{ formError }}
      </p>
      <div class="form-actions form-grid__wide">
        <button class="secondary-button" type="button" @click="$emit('close')">取消</button>
        <button class="primary-button" type="submit" :disabled="isSaving">
          {{ isSaving ? '保存中…' : '保存单词' }}
        </button>
      </div>
    </form>
  </AdminDrawer>
</template>

<style scoped>
.form-textarea {
  min-height: 78px;
  resize: vertical;
}
</style>
