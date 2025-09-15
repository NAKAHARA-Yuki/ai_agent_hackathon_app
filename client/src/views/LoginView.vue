<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import BackButton from '@/components/BackButton.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const user_id = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

// セッション切れによるリダイレクトかどうかを判定
const isSessionExpired = computed(() => route.query.reason === 'expired')
const sessionMessage = computed(() => {
  if (isSessionExpired.value) {
    return 'セッションの有効期限が切れました。再度ログインしてください。'
  }
  return ''
})

onMounted(() => {
  // セッション期限切れメッセージを表示
  if (sessionMessage.value) {
    error.value = sessionMessage.value
  }
})

async function submit() {
  try {
    error.value = ''
    loading.value = true
    await auth.login({ user_id: user_id.value, password: password.value })
    const redirect = route.query.redirect || { name: 'home' }
    router.replace(redirect)
  } catch (e) {
    error.value = e?.message || 'ログインに失敗しました'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth">
    <section class="panel">
      <h1>ログイン</h1>
      <p class="lead">アカウントでログインして診断を進めましょう。</p>

      <form @submit.prevent="submit" class="form">
        <div class="field">
          <label>ユーザーID</label>
          <input v-model.trim="user_id" type="text" autocomplete="username" placeholder="例: gemini-user" />
        </div>
        <div class="field">
          <label>パスワード</label>
          <input v-model="password" type="password" autocomplete="current-password" placeholder="••••••" />
          <p class="muted">パスワードは8文字以上である必要があります。</p>
        </div>

        <p v-if="error" class="error">{{ error }}</p>

        <button class="primary" :disabled="loading">
          {{ loading ? '送信中…' : 'ログイン' }}
        </button>

        <p class="muted">アカウント未作成の方は <router-link :to="{ name: 'signup', query: route.query }">新規登録</router-link></p>
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
button.primary { background:#2d7ef7; color:white; border:none; padding:12px 16px; border-radius:10px; }
.muted { color:#6b7280; font-size:14px; margin: 8px 0 0; }

/* モバイルでの適切な表示 */
@media (max-width: 768px) {
  .auth { 
    padding: 16px; 
  }
  .panel { 
    width: 100%; 
    border-radius: var(--radius-lg); 
    box-shadow: var(--shadow-md); 
    padding: 20px;
    box-sizing: border-box;
  }
}
</style>
