<template>
  <div class="input-screen wizard-screen bg-gradient-to-b from-white to-slate-50 text-slate-900">
    <header class="screen-header">
      <h1>旅行プランの作成</h1>
    </header>
    <main class="screen-main">
      <div class="intro"><p>旅行のキーワードを入力してください</p></div>
      <div class="form">
        <input v-model="keyword" type="text" inputmode="search" placeholder="例: 京都、温泉、2泊3日" class="keyword" />
        <button @click="onClick" :disabled="!keyword.trim()" class="submit">プランを作成</button>
      </div>
    </main>
    <footer class="screen-footer">モック生成 (ローカル)</footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const emit = defineEmits(['create-plan'])
const keyword = ref('')
function onClick(){ emit('create-plan', keyword.value) }
</script>

<style scoped>
/* 1画面固定 & 非スクロール化 */
.input-screen { height:100%; width:100%; overflow:hidden; position:relative; padding:16px; box-sizing:border-box; display:flex; flex-direction:column; }
.screen-header { flex:0 0 auto; display:flex; justify-content:center; align-items:center; padding-top:12px; }
.screen-header h1 { font-size:18px; font-weight:700; margin:0; letter-spacing:-.5px; }
.screen-main { flex:1 1 auto; display:flex; flex-direction:column; justify-content:center; align-items:center; gap:24px; padding-bottom:calc(env(safe-area-inset-bottom)); box-sizing:border-box; }
.intro { text-align:center; max-width:360px; }
.intro p { margin:0; color: var(--color-text-subtle); font-size:14px; }
.form { width:100%; max-width:380px; display:flex; flex-direction:column; gap:12px; }
.keyword { width:100%; padding:14px 16px; font-size:15px; border:1px solid var(--color-border); border-radius:16px; background:#fff; color: var(--color-text); box-shadow:0 2px 6px rgba(0,0,0,0.04); }
.keyword:focus { outline:2px solid var(--color-focus); outline-offset:2px; }
.submit { width:100%; margin-top:0; background: var(--color-primary); border:none; border-radius:16px; padding:14px 18px; font-weight:600; font-size:15px; box-shadow:0 4px 14px rgba(37,99,235,0.25); }
.submit:hover:not(:disabled){ background: var(--color-primary-hover); }
.submit:active:not(:disabled){ background: var(--color-primary-active); transform: translateY(1px); }
.submit:disabled { background: var(--color-border); color: var(--color-text-subtle); box-shadow:none; }
.screen-footer { flex:0 0 auto; text-align:center; font-size:11px; color: var(--color-text-subtle); padding-bottom:calc(env(safe-area-inset-bottom)); }

/* 低身長端末 (高さ < 620px) で縦詰め */
@media (max-height: 620px){
  .screen-main { gap:16px; }
  .keyword { padding:12px 14px; }
  .submit { padding:12px 16px; font-size:14px; }
}

/* キーボード展開時 (モバイル推測) の安全策: 高さが極端に減ったらフレックス開始位置に */
@media (max-height: 540px){
  .screen-main { justify-content:flex-start; padding-top:16px; }
  .form { gap:10px; }
  .keyword { padding:10px 12px; }
  .submit { padding:10px 14px; }
}
</style>
