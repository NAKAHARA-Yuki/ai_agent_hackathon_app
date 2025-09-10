<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { USER_ID_REGEX } from '@/constants/validation'
import BackButton from '@/components/BackButton.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const name = ref('')
const user_id = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  try {
    error.value = ''
    loading.value = true
    if (!USER_ID_REGEX.test(user_id.value)) throw new Error('ユーザーIDは英小文字・数字・_・-で3〜30文字')
    if (password.value.length < 8) throw new Error('パスワードは8文字以上にしてください')
    await auth.signup({ name: name.value, user_id: user_id.value, password: password.value })
    const redirect = route.query.redirect || { name: 'home' }
    router.replace(redirect)
  } catch (e) {
    error.value = e?.message || '登録に失敗しました'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth">
    <section class="panel">
      <h1>新規登録</h1>
      <p class="lead">アカウントを作成して診断を始めましょう。</p>

      <form @submit.prevent="submit" class="form">
        <div class="field">
          <label>お名前</label>
          <input v-model.trim="name" type="text" placeholder="山田 太郎" />
        </div>
        <div class="field">
          <label>ユーザーID</label>
          <input v-model.trim="user_id" type="text" placeholder="例: gemini-user" />
          <small class="hint">英小文字・数字・_・- の3〜30文字</small>
        </div>
        <div class="field">
          <label>パスワード</label>
          <input v-model="password" type="password" placeholder="••••••" />
          <p class="muted">パスワードは8文字以上である必要があります。</p>
        </div>

        <p v-if="error" class="error">{{ error }}</p>

        <button class="primary" :disabled="loading">
          {{ loading ? '送信中…' : '登録してはじめる' }}
        </button>

        <p class="muted">既にアカウントがある方は <router-link :to="{ name: 'login', query: route.query }">ログイン</router-link></p>
      </form>
    </section>
  </main>
</template>

<style scoped>
.auth { display:grid; place-items:center; padding:32px 16px; height:100%; overflow:auto; flex: 1 1 auto; width: 100%; }
.panel { width:min(560px,100%); background:white; padding:28px 22px; border-radius:16px; box-shadow:0 10px 30px rgba(0,0,0,0.08); }
.lead { color:#5a6b86; margin: 0 0 16px; }
.form { display:grid; gap:12px; }
.field { display:grid; gap:6px; }
.field input { padding:10px 12px; border-radius:8px; border:1px solid #dde1e7; }
.error { color:#c0392b; }
button.primary { background: var(--color-primary); color:white; border:none; padding:12px 16px; border-radius:10px; }
.hint { color:#6b7280; font-size:12px; }
.muted { color:#6b7280; font-size:14px; margin: 8px 0 0; }

/* モバイルでの全画面対応 */
@media (max-width: 768px) {
  .auth { 
    padding: 0; 
    place-items: stretch;
  }
  .panel { 
    width: 100%; 
    height: 100vh;
    height: 100dvh;
    border-radius: 0; 
    box-shadow: none; 
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 24px;
  }
}
</style>
