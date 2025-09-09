<template>
  <div class="wizard-screen suggestions-screen">
    <div class="header">
      <h1>旅行プランのご提案</h1>
      <p class="tagline">気になるプランを選択してください</p>
    </div>
    <div class="wizard-scroll cards" role="list">
      <div
        v-for="plan in enrichedPlans"
        :key="plan.id"
        role="listitem"
        class="card"
        :style="{ '--bg-img': `url(${plan.image})` }"
        tabindex="0"
        @click="$emit('select-plan', plan.raw)"
        @keydown.enter.prevent="$emit('select-plan', plan.raw)"
      >
        <div class="card-overlay"></div>
        <div class="card-content">
          <h2 class="title">{{ plan.raw.title }}</h2>
          <p class="tags">{{ plan.raw.tags }}</p>
        </div>
      </div>
    </div>
    <div class="regenerate-section">
      <p class="regenerate-text">気に入るプランがありませんか？</p>
      <div class="regenerate-form" v-if="showRegenerateInput">
        <input 
          v-model="regenerateKeyword" 
          type="text" 
          inputmode="search" 
          placeholder="新しいキーワードを入力してください" 
          class="regenerate-input"
          @keydown.enter.prevent="handleRegenerate"
        />
        <div class="regenerate-buttons">
          <button @click="handleRegenerate" :disabled="!regenerateKeyword.trim()" class="regenerate-submit">再生成</button>
          <button @click="cancelRegenerate" class="regenerate-cancel">キャンセル</button>
        </div>
      </div>
      <button v-else @click="showRegenerateForm" class="regenerate-button">
        🔄 新しいキーワードで再生成
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
const props = defineProps({ plans: { type: Array, default: () => [] } })
const emit = defineEmits(['select-plan', 'regenerate'])

const showRegenerateInput = ref(false)
const regenerateKeyword = ref('')

// 簡易画像割当: タイトル + id を seed に Unsplash のランダムサムネイル（将来は API/自前画像に差し替え可）
const keywords = ['travel','landscape','japan','city','nature','culture','ocean','mountain']
const enrichedPlans = computed(() => props.plans.map((p, idx) => {
  const key = encodeURIComponent(((p.title||'') + ' ' + keywords[idx % keywords.length]).trim())
  return { raw: p, id: p.id, image: `https://source.unsplash.com/featured/400x300?${key}` }
}))

function showRegenerateForm() {
  showRegenerateInput.value = true
  regenerateKeyword.value = ''
}

function cancelRegenerate() {
  showRegenerateInput.value = false
  regenerateKeyword.value = ''
}

function handleRegenerate() {
  if (!regenerateKeyword.value.trim()) return
  emit('regenerate', regenerateKeyword.value)
  showRegenerateInput.value = false
  regenerateKeyword.value = ''
}
</script>

<style scoped>
.suggestions-screen { padding:16px 16px 24px; display:flex; flex-direction:column; gap:16px; }
.header h1 { margin:4px 0 0; font-size:20px; font-weight:700; letter-spacing:-.5px; text-align:center; }
.header .tagline { margin:4px 0 4px; text-align:center; font-size:12px; color:var(--color-text-subtle); }
/* 縦一列表示 */
.cards { display:flex; flex-direction:column; gap:18px; padding:4px 2px 20px; }
.card { position:relative; width:100%; height:180px; border-radius:18px; overflow:hidden; cursor:pointer; isolation:isolate; background:#ddd; display:flex; }
.card::before { content:""; position:absolute; inset:0; background:var(--bg-img) center/cover no-repeat; filter:brightness(1) saturate(1.1); transition:transform .6s ease; }
.card-overlay { position:absolute; inset:0; background:linear-gradient(to top, rgba(0,0,0,0.55), rgba(0,0,0,0.05)); mix-blend-mode:multiply; }
.card-content { position:relative; z-index:2; margin-top:auto; padding:14px 16px 14px; color:#fff; text-shadow:0 2px 4px rgba(0,0,0,.4); display:flex; flex-direction:column; gap:6px; }
.title { font-size:16px; font-weight:600; line-height:1.3; margin:0; letter-spacing:.2px; }
.tags { margin:0; font-size:12px; opacity:.9; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:1; -webkit-box-orient:vertical; }
.card:focus-visible { outline:2px solid var(--color-focus); outline-offset:2px; }
.card:hover::before { transform:scale(1.05); }
.card:active { transform:scale(.97); }

/* 再生成セクション */
.regenerate-section { 
  margin-top: 20px; 
  padding: 20px 16px; 
  background: rgba(255, 255, 255, 0.8); 
  border-radius: 16px; 
  border: 1px solid rgba(0, 0, 0, 0.08);
  text-align: center;
}

.regenerate-text { 
  margin: 0 0 16px; 
  font-size: 14px; 
  color: var(--color-text-subtle); 
}

.regenerate-button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.regenerate-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}

.regenerate-button:active {
  transform: translateY(0);
}

.regenerate-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 400px;
  margin: 0 auto;
}

.regenerate-input {
  width: 100%;
  padding: 12px 16px;
  font-size: 14px;
  border: 1px solid rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  background: white;
  color: var(--color-text);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
  box-sizing: border-box;
}

.regenerate-input:focus {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
  border-color: var(--color-focus);
}

.regenerate-buttons {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.regenerate-submit {
  background: var(--color-primary);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.regenerate-submit:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.regenerate-submit:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.regenerate-cancel {
  background: transparent;
  color: var(--color-text-subtle);
  border: 1px solid rgba(0, 0, 0, 0.2);
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.regenerate-cancel:hover {
  background: rgba(0, 0, 0, 0.05);
}

@media (min-width:640px){
  .card { height:200px; }
  .title { font-size:18px; }
  .regenerate-form { max-width: 500px; }
}
</style>
