<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import BackButton from '@/components/BackButton.vue'

const router = useRouter()
const auth = useAuthStore()
const route = useRoute()

const mode = ref('login') // 'login' | 'signup'

const name = ref('')
const user_id = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  try {
    error.value = ''
    loading.value = true
    if (mode.value === 'signup') {
      await auth.signup({ name: name.value, user_id: user_id.value, password: password.value })
    } else {
      await auth.login({ user_id: user_id.value, password: password.value })
    }
  const redirect = route.query.redirect || { name: 'home' }
  router.replace(redirect)
  } catch (e) {
    error.value = e?.message || 'エラーが発生しました'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth">
    <section class="panel">
  <BackButton />
      <h1>最高の旅行アシスタントをあなたのポケットに</h1>
      <p class="lead">アカウントを作成またはログインして、旅行スタイル診断から始めましょう。</p>

      <div class="tabs">
        <button :class="{active: mode==='login'}" @click="mode='login'">ログイン</button>
        <button :class="{active: mode==='signup'}" @click="mode='signup'">アカウント作成</button>
      </div>

      <form @submit.prevent="submit" class="form">
        <div v-if="mode==='signup'" class="field">
          <label>お名前</label>
          <input v-model.trim="name" type="text" placeholder="山田 太郎" />
        </div>
        <div class="field">
          <label>ユーザーID</label>
          <input v-model.trim="user_id" type="text" placeholder="例: nakahara_yuki" />
          <small class="hint">英小文字・数字・_・- の3〜30文字</small>
        </div>
        <div class="field">
          <label>パスワード</label>
          <input v-model="password" type="password" placeholder="••••••" />
        </div>

        <p v-if="error" class="error">{{ error }}</p>

        <button class="primary" :disabled="loading">
          {{ loading ? '送信中…' : (mode==='signup' ? '登録してはじめる' : 'ログイン') }}
        </button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.auth {
  display: grid;
  place-items: center;
  padding: 32px 16px;
  height: 100%;
  overflow: auto; /* ビュー内でのみスクロール */
  flex: 1 1 auto; width: 100%;
}
.panel {
  width: min(720px, 100%);
  background: white;
  padding: 28px 22px;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.08);
}
.lead { color: #5a6b86; }
.tabs { display:flex; gap:8px; margin: 12px 0 18px; }
.tabs button { flex:1; padding:10px; border-radius: 10px; border: 1px solid #e4e7ec; background:#f7f8fb; }
.tabs button.active { background:#e8f0ff; border-color:#2d7ef7; color:#2d7ef7; }
.form { display:grid; gap:12px; }
.field { display:grid; gap:6px; }
.field input { padding: 10px 12px; border-radius: 8px; border:1px solid #dde1e7; }
.error { color:#c0392b; margin: 4px 0; }
button.primary { background:#2d7ef7; color:white; border:none; padding:12px 16px; border-radius:10px; }

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
