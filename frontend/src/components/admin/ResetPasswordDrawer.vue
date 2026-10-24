<script setup>
import { ref, watch } from 'vue'

import { resetAdminUserPassword } from '../../api/admin'
import { getErrorMessage } from '../../utils/errors'
import AdminDrawer from '../AdminDrawer.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  user: { type: Object, default: null },
})

const emit = defineEmits(['close', 'submitted'])

const password = ref('')
const confirmPassword = ref('')
const errorMessage = ref('')
const isResetting = ref(false)

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    password.value = ''
    confirmPassword.value = ''
    errorMessage.value = ''
  },
)

async function submit() {
  errorMessage.value = ''
  if (password.value.length < 8) {
    errorMessage.value = '新密码至少需要 8 位。'
    return
  }
  if (password.value !== confirmPassword.value) {
    errorMessage.value = '两次输入的新密码不一致。'
    return
  }

  isResetting.value = true
  try {
    await resetAdminUserPassword(props.user.id, password.value)
    emit('submitted', props.user)
    emit('close')
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '密码没有重置成功。')
  } finally {
    isResetting.value = false
  }
}
</script>

<template>
  <AdminDrawer
    :open="open"
    title="重置用户密码"
    :description="user ? `正在处理：${user.username}` : ''"
    @close="emit('close')"
  >
    <form class="reset-form" @submit.prevent="submit">
      <label class="field">
        <span class="field-label">新密码</span>
        <input
          v-model="password"
          class="field-input"
          type="password"
          minlength="8"
          maxlength="72"
          autocomplete="new-password"
        />
      </label>
      <label class="field">
        <span class="field-label">确认新密码</span>
        <input
          v-model="confirmPassword"
          class="field-input"
          type="password"
          minlength="8"
          maxlength="72"
          autocomplete="new-password"
        />
      </label>
      <p v-if="errorMessage" class="inline-notice inline-notice--error" role="alert">
        {{ errorMessage }}
      </p>
      <p class="field-help">重置后旧密码立即失效，请通过安全渠道告知用户。</p>
      <div class="form-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="submit" :disabled="isResetting">
          {{ isResetting ? '重置中…' : '确认重置' }}
        </button>
      </div>
    </form>
  </AdminDrawer>
</template>

<style scoped>
.reset-form {
  display: grid;
  gap: 20px;
}
</style>
