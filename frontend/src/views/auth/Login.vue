<script setup>
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../../stores/auth'
import { getErrorMessage } from '../../utils/errors'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const form = reactive({ account: '', password: '' })
const errorMessage = ref('')
const isSubmitting = ref(false)

async function submit() {
  if (isSubmitting.value) return
  errorMessage.value = ''
  if (!form.account.trim() || !form.password) {
    errorMessage.value = '请填写账号与密码。'
    return
  }
  isSubmitting.value = true
  try {
    await authStore.login({
      account: form.account.trim(),
      password: form.password,
    })
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '登录未完成，请核对账号与密码。')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="auth-form">
    <p class="eyebrow">WELCOME BACK</p>
    <h2>回到你的练习桌</h2>
    <p class="auth-form__lead">用用户名或邮箱登录，继续今天的默写。</p>

    <p v-if="route.query.registered" class="inline-notice inline-notice--success">
      注册成功，现在可以登录了。
    </p>
    <p v-if="errorMessage" class="inline-notice inline-notice--error" role="alert">
      {{ errorMessage }}
    </p>

    <form novalidate @submit.prevent="submit">
      <label class="line-field">
        <span>用户名 / 邮箱</span>
        <input
          v-model="form.account"
          type="text"
          autocomplete="username"
          maxlength="100"
          placeholder="输入你的登录账号"
        />
      </label>
      <label class="line-field">
        <span>密码</span>
        <input
          v-model="form.password"
          type="password"
          autocomplete="current-password"
          minlength="8"
          maxlength="72"
          placeholder="至少 8 位"
        />
      </label>
      <button class="primary-button auth-form__submit" type="submit" :disabled="isSubmitting">
        {{ isSubmitting ? '正在登录…' : '进入练习桌' }}
      </button>
    </form>

    <p class="auth-form__switch">
      还没有账户？
      <RouterLink to="/register">创建新账户</RouterLink>
    </p>
  </div>
</template>

<style scoped>
.auth-form h2 {
  margin-bottom: 10px;
  font-size: var(--font-size-xl);
}

.auth-form__lead {
  margin-bottom: 34px;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
}

.auth-form .inline-notice {
  margin-bottom: 18px;
}

.auth-form form {
  display: grid;
  gap: 26px;
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
  margin-top: 8px;
}

.auth-form__switch {
  margin: 28px 0 0;
  color: var(--color-disabled);
  font-size: var(--font-size-sm);
  text-align: center;
}

.auth-form__switch a {
  margin-left: 4px;
  font-weight: 600;
}
</style>
