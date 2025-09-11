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
      <div class="regenerate-form" v-if="showRegenerateInput" role="region" aria-labelledby="regenerate-heading">
        <h3 id="regenerate-heading" class="sr-only">新しいキーワードで再生成</h3>
        <div class="input-wrapper">
          <label for="regenerate-input" class="sr-only">新しいキーワードを入力</label>
          <input 
            id="regenerate-input"
            v-model="regenerateKeyword" 
            type="text" 
            inputmode="search" 
            placeholder="新しいキーワードを入力してください" 
            class="regenerate-input"
            :class="{ 'input-error': errorMessage }"
            maxlength="100"
            @keydown.enter.prevent="handleRegenerate"
            @input="errorMessage = ''"
            aria-describedby="regenerate-help regenerate-counter"
            :aria-invalid="!!errorMessage"
          />
          <div class="input-feedback">
            <span id="regenerate-counter" class="character-counter" :class="{ 'counter-warning': characterCount > 90 }">
              {{ characterCount }}/100
            </span>
          </div>
        </div>
        <p id="regenerate-help" class="sr-only">エンターキーを押すか再生成ボタンをクリックして新しいプランを生成</p>
        <div v-if="errorMessage" class="error-message" role="alert" aria-live="polite">
          {{ errorMessage }}
        </div>
        <div class="regenerate-buttons">
          <button 
            @click="handleRegenerate" 
            :disabled="!isKeywordValid || isRegenerating" 
            class="regenerate-submit" 
            :class="{ 'loading': isRegenerating }"
            aria-describedby="regenerate-help"
          >
            <span v-if="isRegenerating">生成中...</span>
            <span v-else>再生成</span>
          </button>
          <button @click="cancelRegenerate" class="regenerate-cancel" :disabled="isRegenerating">キャンセル</button>
        </div>
      </div>
      <button v-else @click="showRegenerateForm" class="regenerate-button" aria-describedby="regenerate-description">
        <span class="button-icon">🔄</span>
        <span class="button-text">新しいキーワードで再生成</span>
      </button>
      <p id="regenerate-description" class="sr-only">現在の提案が気に入らない場合は、新しいキーワードで別のプランを生成できます</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
const props = defineProps({ 
  plans: { 
    type: Array, 
    required: true,
    validator: (value) => Array.isArray(value) && value.every(item => item && typeof item === 'object')
  } 
})
const emit = defineEmits(['select-plan', 'regenerate'])

const showRegenerateInput = ref(false)
const regenerateKeyword = ref('')
const isRegenerating = ref(false)
const errorMessage = ref('')

// 簡易画像割当: タイトル + id を seed に Unsplash のランダムサムネイル（将来は API/自前画像に差し替え可）
const keywords = ['travel','landscape','japan','city','nature','culture','ocean','mountain']
const enrichedPlans = computed(() => {
  if (!Array.isArray(props.plans)) return []
  
  return props.plans.map((p, idx) => {
    if (!p || typeof p !== 'object') return null
    
    const key = encodeURIComponent(((p.title||'') + ' ' + keywords[idx % keywords.length]).trim())
    return { 
      raw: p, 
      id: p.id || idx, 
      image: `https://source.unsplash.com/featured/400x300?${key}` 
    }
  }).filter(Boolean)
})

const characterCount = computed(() => regenerateKeyword.value.length)
const isKeywordValid = computed(() => {
  const keyword = regenerateKeyword.value.trim()
  return keyword.length > 0 && keyword.length <= 100 && !/[<>'"&\x00-\x1F\x7F-\x9F]/.test(keyword)
})

function showRegenerateForm() {
  showRegenerateInput.value = true
  regenerateKeyword.value = ''
  errorMessage.value = ''
}

function cancelRegenerate() {
  showRegenerateInput.value = false
  regenerateKeyword.value = ''
  errorMessage.value = ''
  isRegenerating.value = false
}

async function handleRegenerate() {
  if (!isKeywordValid.value || isRegenerating.value) return
  
  const keyword = regenerateKeyword.value.trim()
  
  // 追加のサニタイズ: 制御文字と危険な文字を除去
  const sanitizedKeyword = keyword.replace(/[<>'"&\x00-\x1F\x7F-\x9F]/g, '')
  if (sanitizedKeyword.length === 0) {
    errorMessage.value = 'キーワードに使用できない文字が含まれています'
    return
  }
  
  if (sanitizedKeyword.length > 100) {
    errorMessage.value = 'キーワードは100文字以内で入力してください'
    return
  }

  try {
    isRegenerating.value = true
    errorMessage.value = ''
    emit('regenerate', sanitizedKeyword)
    showRegenerateInput.value = false
    regenerateKeyword.value = ''
  } catch (error) {
    console.error('Regeneration error:', error)
    errorMessage.value = '再生成中にエラーが発生しました。もう一度お試しください。'
    isRegenerating.value = false
  }
}
</script>

<style scoped>
.suggestions-screen { padding:16px 16px 24px; display:flex; flex-direction:column; gap:16px; }
.header h1 { margin:4px 0 0; font-size:20px; font-weight:700; letter-spacing:-.5px; text-align:center; }
.header .tagline { margin:4px 0 4px; text-align:center; font-size:12px; color:var(--color-text-subtle); }
/* 縦一列表示 */
.cards { display:flex; flex-direction:column; gap:18px; padding:4px 2px 20px; }
.card { position:relative; width:100%; height:160px; border-radius:18px; overflow:hidden; cursor:pointer; isolation:isolate; background:#ddd; display:flex; }
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
  display: flex;
  align-items: center;
  gap: 8px;
}

.regenerate-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}

.regenerate-button:active {
  transform: translateY(0);
}

.regenerate-button:focus-visible {
  outline: 2px solid var(--color-focus, #007bff);
  outline-offset: 2px;
}

.button-icon {
  font-size: 16px;
}

.button-text {
  white-space: nowrap;
}

.regenerate-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 400px;
  margin: 0 auto;
}

.input-wrapper {
  position: relative;
}

.regenerate-input {
  width: 100%;
  padding: 12px 16px;
  font-size: 14px;
  border: 1px solid rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  background: white;
  color: var(--color-text, #333);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
  box-sizing: border-box;
  transition: border-color 0.2s ease;
}

.regenerate-input:focus {
  outline: 2px solid var(--color-focus, #007bff);
  outline-offset: 2px;
  border-color: var(--color-focus, #007bff);
}

.regenerate-input.input-error {
  border-color: #dc3545;
  box-shadow: 0 2px 6px rgba(220, 53, 69, 0.15);
}

.input-feedback {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.character-counter {
  font-size: 12px;
  color: var(--color-text-subtle, #666);
}

.character-counter.counter-warning {
  color: #ff6b35;
  font-weight: 600;
}

.error-message {
  color: #dc3545;
  font-size: 12px;
  margin: 0;
  padding: 4px 8px;
  background: rgba(220, 53, 69, 0.1);
  border: 1px solid rgba(220, 53, 69, 0.2);
  border-radius: 6px;
}

.regenerate-buttons {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.regenerate-submit {
  background: var(--color-primary, #007bff);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 80px;
}

.regenerate-submit:hover:not(:disabled) {
  background: var(--color-primary-hover, #0056b3);
}

.regenerate-submit:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.regenerate-submit.loading {
  background: #6c757d;
  cursor: wait;
}

.regenerate-submit:focus-visible {
  outline: 2px solid var(--color-focus, #007bff);
  outline-offset: 2px;
}

.regenerate-cancel {
  background: transparent;
  color: var(--color-text-subtle, #666);
  border: 1px solid rgba(0, 0, 0, 0.2);
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.regenerate-cancel:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.05);
}

.regenerate-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.regenerate-cancel:focus-visible {
  outline: 2px solid var(--color-focus, #007bff);
  outline-offset: 2px;
}

/* スクリーンリーダー専用テキスト */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* モバイルでの適切な表示 - カードの伸縮を防止 */
@media (max-width: 768px) {
  .suggestions-screen { 
    flex: 1; 
    min-height: 0;
    overflow-y: auto;
    padding: 12px; 
    margin: 0;
    border-radius: 0;
    box-shadow: none;
    background: transparent;
    padding-bottom: calc(env(safe-area-inset-bottom) + 20px);
  }
  
  .header h1 {
    font-size: 18px;
  }
  
  .header .tagline {
    font-size: 13px;
  }
  
  .cards {
    padding: 4px 0 20px; /* 左右のpaddingを削除 */
    gap: 14px; /* カード間の間隔を少し広げる */
  }
  
  .card {
    height: 140px; /* モバイルでは少し低く */
    border-radius: 14px;
  }
  
  .card-content {
    padding: 12px 14px;
  }
  
  .title {
    font-size: 15px;
    line-height: 1.4;
  }
  
  .tags {
    font-size: 11px;
    line-height: 1.3;
  }
  
  .regenerate-section {
    margin: 12px 0 0;
    padding: 14px;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 12px;
  }
  
  .regenerate-text {
    font-size: 13px;
  }
  
  .regenerate-button {
    padding: 14px 20px;
    font-size: 15px;
    min-height: 48px; /* タッチフレンドリーなサイズ */
  }
  
  .regenerate-form {
    max-width: 100%; /* モバイルでは全幅使用 */
  }
  
  .regenerate-input {
    padding: 14px 16px;
    font-size: 15px;
    min-height: 48px;
    box-sizing: border-box;
  }
  
  .regenerate-buttons {
    gap: 10px;
  }
  
  .regenerate-submit,
  .regenerate-cancel {
    padding: 12px 20px;
    font-size: 15px;
    min-height: 44px;
  }
}

/* 非常に小さな画面用の追加調整 */
@media (max-width: 480px) {
  .suggestions-screen {
    padding: 10px;
  }
  
  .card {
    height: 120px;
  }
  
  .regenerate-buttons {
    flex-direction: column; /* 縦並びでより使いやすく */
    gap: 8px;
  }
  
  .regenerate-submit,
  .regenerate-cancel {
    width: 100%;
    min-height: 48px;
  }
}

@media (min-width:640px){
  .card { height:180px; }
  .title { font-size:18px; }
  .regenerate-form { max-width: 500px; }
}
</style>
