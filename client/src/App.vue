<script setup>
import { RouterView } from 'vue-router'
</script>

<template>
  <div id="app-container">
    <RouterView />
  </div>
</template>

<style scoped>
#app-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
</style>
