<script setup>
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { register } from '../../api/auth'
import { getErrorMessage } from '../../utils/errors'

const router = useRouter()
const form = reactive({ username: '', email: '', password: '', confirmPassword: '' })
const errorMessage = ref('')
const isSubmitting = ref(false)

function validate() {
  if (!form.username.trim()) return '请填写用户名。'
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) return '请填写有效的邮箱地址。'
  if (form.password.length < 8) return '密码至少需要 8 位。'
  if (form.password !== form.confirmPassword) return '两次输入的密码不一致。'
  return ''
}

async function submit() {
  if (isSubmitting.value) return
  errorMessage.value = validate()
  if (errorMessage.value) return
  isSubmitting.value = true
  try {
    await register({
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
    })
    await router.replace({ name: 'login', query: { registered: '1' } })
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '注册未完成，请稍后再试。')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="auth-form">
    <p class="eyebrow">BEGIN A NEW PAGE</p>
    <h2>领一张练习桌</h2>
    <p class="auth-form__lead">注册后即可浏览词书、开始默写，并记录每一次进步。</p>

    <p v-if="errorMessage" class="inline-notice inline-notice--error" role="alert">
      {{ errorMessage }}
    </p>

    <form novalidate @submit.prevent="submit">
      <label class="line-field">
        <span>用户名</span>
        <input
          v-model="form.username"
          type="text"
          autocomplete="username"
          maxlength="50"
          placeholder="你的称呼"
        />
      </label>
      <label class="line-field">
        <span>邮箱</span>
        <input
          v-model="form.email"
          type="email"
          autocomplete="email"
          maxlength="100"
          placeholder="name@example.com"
        />
      </label>
      <label class="line-field">
        <span>密码</span>
        <input
          v-model="form.password"
          type="password"
          autocomplete="new-password"
          minlength="8"
          maxlength="72"
          placeholder="至少 8 位"
        />
      </label>
      <label class="line-field">
        <span>确认密码</span>
        <input
          v-model="form.confirmPassword"
          type="password"
          autocomplete="new-password"
          minlength="8"
          maxlength="72"
          placeholder="再写一次"
        />
      </label>
      <button class="primary-button auth-form__submit" type="submit" :disabled="isSubmitting">
        {{ isSubmitting ? '正在创建…' : '创建账户' }}
      </button>
    </form>

    <p class="auth-form__switch">
      已经有账户？
      <RouterLink to="/login">返回登录</RouterLink>
    </p>
  </div>
</template>

<style scoped>
.auth-form h2 {
  margin-bottom: 10px;
  font-size: var(--font-size-xl);
}

.auth-form__lead {
  margin-bottom: 28px;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.auth-form .inline-notice {
  margin-bottom: 18px;
}

.auth-form form {
  display: grid;
  gap: 23px;
}

.line-field {
  display: grid;
  gap: 7px;
}

.line-field span {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
  letter-spacing: 0.06em;
}

.line-field input {
  width: 100%;
  padding: 8px 0 12px;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  border-radius: 0;
  outline: 0;
  background: transparent;
  font-size: var(--font-size-md);
}

.line-field input:hover {
  border-bottom-color: var(--color-border-hover);
}

.line-field input:focus {
  border-bottom-color: var(--color-primary);
}

.line-field input::placeholder {
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.auth-form__submit {
  width: 100%;
  margin-top: 4px;
}

.auth-form__switch {
  margin: 26px 0 0;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
  text-align: center;
}

.auth-form__switch a {
  margin-left: 4px;
  font-weight: 600;
}
</style>
