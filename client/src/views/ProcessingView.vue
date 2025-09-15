<script setup>
import { computed } from 'vue'
import { useQuizStore } from '@/stores/quizStore'
import BackButton from '@/components/BackButton.vue'

const store = useQuizStore()

const stageText = computed(() => {
  switch (store.processingStage) {
    case 'analyzing': return 'AIが回答全体を解析しています…'
    case 'scoring': return 'スコアを集計しています…'
    case 'parallel': return 'おすすめプラン生成とプロフィール保存を実行中…'
    case 'done': return '完了しました。結果を表示します…'
    case 'error': return '一部処理に失敗しましたが、結果を表示します…'
    default: return '準備中…'
  }
})
</script>

<template>
  <main class="processing">
    <section class="panel">
  <BackButton />
      <h1>診断中</h1>

      <div class="progress">
        <div class="bar" :style="{ width: store.processingPercent + '%' }"></div>
      </div>
      <p class="stage">{{ stageText }}</p>

      <ul class="steps">
        <li :class="{active: store.processingStage==='analyzing' || store.processingStage==='scoring' || store.processingStage==='parallel' || store.processingStage==='done'}">1. 回答解析</li>
        <li :class="{active: store.processingStage==='scoring' || store.processingStage==='parallel' || store.processingStage==='done'}">2. スコア集計</li>
        <li :class="{active: store.processingStage==='parallel' || store.processingStage==='done'}">3. プラン生成・保存</li>
      </ul>

      <div class="spinner"></div>
    </section>
  </main>
  
</template>

<style scoped>
.processing { display:grid; place-items:center; height:100%; padding:24px; overflow:auto; flex: 1 1 auto; width: 100%; }
.panel { width:min(680px, 100%); background:white; border-radius:16px; padding:24px; box-shadow:0 10px 30px rgba(0,0,0,0.08); text-align:center; }
.progress { height:10px; background:#eef2f7; border-radius:8px; overflow:hidden; margin: 10px 0 8px; }
.bar { height:100%; background:linear-gradient(90deg, #2d7ef7, #6aa6ff); transition: width .3s ease; }
.stage { color:#5a6b86; margin: 8px 0 16px; }
.steps { list-style:none; display:flex; gap:10px; justify-content:center; padding:0; margin:0 0 10px; flex-wrap:wrap; }
.steps li { padding:6px 10px; border-radius:999px; background:#f6f8fb; color:#6b7280; border:1px solid #e5e7eb; font-size:13px; }
.steps li.active { background:#e8f0ff; color:#2d7ef7; border-color:#cfe0ff; }
.spinner { border: 5px solid rgba(0, 0, 0, 0.1); width: 40px; height: 40px; border-radius: 50%; border-left-color: #2d7ef7; margin: 12px auto 0; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* モバイルでの全画面対応 */
@media (max-width: 768px) {
  .processing { 
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
    box-sizing: border-box;
  }
}
</style>
