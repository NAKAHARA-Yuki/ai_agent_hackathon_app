<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import BackButton from '@/components/BackButton.vue'

const auth = useAuthStore()
const me = computed(() => auth.user)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const profile = ref({ display_name: '', age: '', birthdate: '', gender: '', hobbies: [], location: '', budget: '', notes: '' })
const toast = ref('')
const latestPersona = ref(null)
const hobbiesError = ref('')
const canAddHobby = computed(() => (profile.value.hobbies?.length || 0) < 10)
const dobError = ref('')
const displayAge = computed(() => {
  const a = profile.value.age
  return (a === '' || a == null || Number.isNaN(a)) ? '—' : String(a)
})

function splitHobbies(input) {
  if (Array.isArray(input)) return input
  if (typeof input === 'string') return input.split(',').map(s => s.trim()).filter(Boolean)
  return []
}

async function loadProfile() {
  try {
    const resp = await fetch('/api/profile', { headers: { 'Content-Type': 'application/json', ...auth.authHeader() } })
    if (resp.ok) {
      const data = await resp.json()
      const p = data.profile || {}
      profile.value = {
        display_name: p.display_name || (data.name || me.value?.name || ''),
        age: p.age || '',
        birthdate: p.birthdate || '',
        gender: p.gender || '',
        hobbies: splitHobbies(p.hobbies || []),
        location: p.location || '',
        budget: p.budget || '',
        notes: p.notes || ''
      }
      // 読み込み時にも生年月日から年齢を再計算
      if (profile.value.birthdate) {
        profile.value.age = calcAge(profile.value.birthdate)
      }
    }
  } catch (e) {
    error.value = e?.message || 'プロフィールの取得に失敗しました'
  }
}

async function loadLatestPersona() {
  try {
    const resp = await fetch('/api/persona/latest', { headers: { ...auth.authHeader() } })
    if (resp.ok) latestPersona.value = await resp.json()
  } catch {}
}

function addTag(e) {
  const v = (e.target.value || '').trim().replace(/,+$/, '')
  if (v) {
    if (v.length > 30) {
      hobbiesError.value = '各趣味は30文字以内で入力してください'
      return
    }
    if (!canAddHobby.value) {
      hobbiesError.value = '趣味は最大10件までです'
      return
    }
    const exists = profile.value.hobbies.some(h => h.toLowerCase() === v.toLowerCase())
    if (!exists) profile.value.hobbies.push(v)
    hobbiesError.value = ''
  }
  e.target.value = ''
}

function calcAge(dobStr) {
  try {
    if (!dobStr) return ''
    const today = new Date()
    const [y, m, d] = dobStr.split('-').map(Number)
    if (!y || !m || !d) return ''
    let age = today.getFullYear() - y
    const hasHadBirthday = (today.getMonth() + 1 > m) || ((today.getMonth() + 1 === m) && (today.getDate() >= d))
    if (!hasHadBirthday) age -= 1
    if (age < 0 || age > 120) return ''
    return age
  } catch { return '' }
}

// 生年月日変更で年齢を自動更新
watch(() => profile.value.birthdate, (v) => {
  // 構文と実在チェック
  dobError.value = ''
  if (!v) { profile.value.age = ''; return }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) {
    dobError.value = 'YYYY-MM-DD形式で入力してください'
    profile.value.age = ''
    return
  }
  const [y, m, d] = v.split('-').map(Number)
  const dt = new Date(y, m - 1, d)
  if (!(dt && dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d)) {
    dobError.value = '存在しない日付です'
    profile.value.age = ''
    return
  }
  const age = calcAge(v)
  if (age === '') {
    dobError.value = '年齢が計算できません'
  }
  profile.value.age = age
})

async function saveProfile() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
  // save前に年齢をDOBから再計算（信頼できる形で送る）
    const ageFromDob = calcAge(profile.value.birthdate)
    const bodyProfile = { ...profile.value, hobbies: profile.value.hobbies }
    if (dobError.value) {
      delete bodyProfile.birthdate
    }
    if (ageFromDob === '' || ageFromDob == null || Number.isNaN(ageFromDob)) {
      delete bodyProfile.age
    } else {
      bodyProfile.age = ageFromDob
    }
    const payload = { profile: bodyProfile }
    const resp = await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...auth.authHeader() },
      body: JSON.stringify(payload)
    })
    if (!resp.ok) {
      const e = await resp.json().catch(() => ({}))
      throw new Error(e?.error || '保存に失敗しました')
    }
  toast.value = '保存しました'
  setTimeout(() => (toast.value = ''), 2000)
  } catch (e) {
    error.value = e?.message || '保存に失敗しました'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadProfile(), loadLatestPersona()])
  loading.value = false
})
</script>

<template>
  <main class="mypage">
    <section class="panel">
  <BackButton />
      <h1>マイページ</h1>
      <p class="muted">アカウント名: {{ me?.name || me?.id }}</p>
  <transition name="fade"><div v-if="toast" class="toast">{{ toast }}</div></transition>

      <div v-if="loading">読み込み中...</div>
      <div v-else>
        <form class="grid" @submit.prevent="saveProfile">
          <div class="field">
            <label>表示名</label>
            <input v-model="profile.display_name" type="text" placeholder="いざ旅 太郎" />
          </div>
          <div class="field">
            <label>生年月日</label>
            <input v-model="profile.birthdate" type="date" :max="new Date().toISOString().slice(0,10)" />
          </div>
          <div class="field">
            <label>年齢</label>
            <div class="readonly-value" :class="{ 'muted': displayAge==='—' }">{{ displayAge }}</div>
          </div>
          <div class="field">
            <label>性別</label>
            <div class="segmented compact" role="radiogroup" aria-label="性別">
              <button type="button" class="seg-btn" :class="{ active: profile.gender==='男性' }" @click="profile.gender='男性'" role="radio" :aria-checked="profile.gender==='男性'">男性</button>
              <button type="button" class="seg-btn" :class="{ active: profile.gender==='女性' }" @click="profile.gender='女性'" role="radio" :aria-checked="profile.gender==='女性'">女性</button>
              <button type="button" class="seg-btn" :class="{ active: profile.gender==='その他' }" @click="profile.gender='その他'" role="radio" :aria-checked="profile.gender==='その他'">その他</button>
              <button type="button" class="seg-btn" :class="{ active: profile.gender==='回答しない' }" @click="profile.gender='回答しない'" role="radio" :aria-checked="profile.gender==='回答しない'">回答しない</button>
            </div>
          </div>
          <div class="field full">
            <label>趣味（Enter/カンマで追加）</label>
            <div class="tags-input" @click="$event.currentTarget.querySelector('input')?.focus()">
              <span v-for="(h, idx) in profile.hobbies" :key="h+idx" class="tag" @click="profile.hobbies.splice(idx,1)">{{ h }} <span class="x">×</span></span>
              <input
                class="tag-editor"
                type="text"
                :placeholder="canAddHobby ? '登山' : '最大に達しました'"
                :disabled="!canAddHobby"
                @keydown.enter.prevent="addTag($event)"
                @keydown="if ($event.key===',') { $event.preventDefault(); addTag($event) }"
                @blur="addTag($event)"
              />
            </div>
            <div class="hint-row">
              <span class="muted">残り {{ Math.max(0, 10 - (profile.hobbies?.length || 0)) }} 件まで</span>
              <span v-if="hobbiesError" class="error small">{{ hobbiesError }}</span>
            </div>
          </div>
          <div class="field">
            <label>普段の拠点</label>
            <input v-model="profile.location" type="text" placeholder="東京" />
          </div>
          <div class="field">
            <label>だいたいの予算感</label>
            <input v-model="profile.budget" type="text" placeholder="1泊2日で2万円" />
          </div>
          <div class="field full">
            <label>メモ</label>
            <textarea v-model="profile.notes" rows="3" placeholder="移動は少なめで、自然が多い場所が好き など"></textarea>
          </div>

          <div class="actions">
            <button class="primary" type="submit" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
        </form>

        <div class="persona" v-if="latestPersona?.profile">
          <h3>最新の診断</h3>
          <p class="muted">タイプ: {{ latestPersona.profile.title }}</p>
          <p>{{ latestPersona.profile.description }}</p>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.mypage { display:grid; place-items:center; padding:32px 16px; height:100%; overflow:auto; }
.panel { width:min(920px,100%); background:white; padding:28px 22px; border-radius:16px; box-shadow:0 10px 30px rgba(0,0,0,0.08); }
.muted { color:#6b7280; }
.error { color:#b91c1c; }
.grid { display:grid; grid-template-columns: repeat(2, 1fr); gap:14px; }
.field { display:flex; flex-direction:column; gap:6px; }
.field.full { grid-column: 1 / -1; }
label { font-size: 13px; color:#374151; }
input, select, textarea { padding:10px 12px; border:1px solid #e5e7eb; border-radius:10px; font-size:14px; }
input:focus, select:focus, textarea:focus { outline:none; border-color:#2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.15); }
.actions { margin-top: 8px; }
button.primary { background:#2563eb; color:#fff; border:none; padding:10px 16px; border-radius:10px; cursor:pointer; }
.persona { margin-top: 20px; padding-top: 12px; border-top: 1px solid #eee; }
.tags-input { display:flex; align-items:center; gap:6px; flex-wrap: wrap; padding:8px; border:1px solid #e5e7eb; border-radius:10px; }
.tag { background:#eef2ff; color:#1f2937; border-radius:999px; padding:4px 8px; cursor:pointer; }
.tag .x { margin-left:6px; color:#6b7280; }
.tag-editor { border:none; outline:none; min-width: 80px; padding:6px; }
.toast { position: sticky; top: 8px; background:#16a34a; color:#fff; padding:6px 10px; border-radius: 8px; display:inline-block; margin-left: 8px; }
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* モバイルでの全画面対応 */
@media (max-width: 768px) {
  .mypage { 
    padding: 0; 
    place-items: stretch;
  }
  .panel { 
    width: 100%; 
    min-height: 100vh;
    min-height: 100dvh;
    border-radius: 0; 
    box-shadow: none; 
    padding: 24px;
    overflow-y: auto;
  }
  .grid { 
    grid-template-columns: 1fr; 
  }
}
.segmented { display:inline-flex; background:#f3f4f6; border-radius:10px; padding:2px; gap:2px; }
.segmented.compact { padding:1px; gap:2px; }
.seg-btn { border:none; background:transparent; padding:4px 8px; border-radius:6px; cursor:pointer; color:#374151; font-size: 12px; line-height: 1.1; }
.seg-btn.active { background:#2563eb; color:#fff; }
.seg-btn:focus { outline: 2px solid #93c5fd; outline-offset: 1px; }
.hint-row { display:flex; justify-content: space-between; align-items:center; margin-top:6px; }
.error.small { font-size: 12px; }
.readonly-value { padding:10px 12px; border:1px dashed #e5e7eb; border-radius:10px; font-size:14px; background:#f9fafb; }
@media (max-width: 800px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
