<script setup>
import { useQuizStore } from '@/stores/quizStore'
const store = useQuizStore()
</script>

<template>
  <div class="progress-container">
    <div class="progress-bar" :style="{ width: store.progress + '%' }"></div>
  </div>
</template>

<style scoped>
.progress-container {
  width: 100%;
  background-color: #e0e0e0;
  border-radius: 10px;
  margin-bottom: 20px;
  height: 10px;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background-color: #007bff;
  border-radius: 10px;
  transition: width 0.5s ease-in-out;
}
</style>
