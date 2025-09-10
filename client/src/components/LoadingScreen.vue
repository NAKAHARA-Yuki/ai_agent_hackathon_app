<template>
  <div class="wizard-screen flex flex-col items-center justify-center h-full text-slate-700 p-6 pb-safe">
    <div class="text-lg font-semibold mb-2 tracking-tight">AIが旅行プランを生成中...</div>
    <div class="text-xs text-slate-500 mb-10">最適なプランを考えています。少しお待ちください。</div>
    
    <!-- AI Thinking Animation -->
    <div class="ai-thinking-container">
      <!-- Background glow effect -->
      <div class="bg-glow"></div>
      
      <!-- Neural network nodes -->
      <div class="neural-node node-1"></div>
      <div class="neural-node node-2"></div>
      <div class="neural-node node-3"></div>
      <div class="neural-node node-4"></div>
      <div class="neural-node node-5"></div>
      <div class="neural-node node-6"></div>
      <div class="neural-node node-7"></div>
      
      <!-- Connecting lines -->
      <div class="connection line-1"></div>
      <div class="connection line-2"></div>
      <div class="connection line-3"></div>
      <div class="connection line-4"></div>
      
      <!-- Central brain icon -->
      <div class="brain-center">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" role="img" aria-label="AI brain thinking">
          <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.5A2.5 2.5 0 0 1 2 17.5V9A2.5 2.5 0 0 1 4.5 6.5h1.75a2.5 2.5 0 0 1 2.5-2.5h.75z"/>
          <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.5A2.5 2.5 0 0 0 22 17.5V9a2.5 2.5 0 0 0-2.5-2.5h-1.75a2.5 2.5 0 0 0-2.5-2.5h-.75z"/>
        </svg>
      </div>
    </div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.ai-thinking-container {
  position: relative;
  width: 200px;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Background glow effect */
.bg-glow {
  position: absolute;
  width: 180px;
  height: 180px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 50%, transparent 100%);
  border-radius: 50%;
  animation: glow-pulse 3s ease-in-out infinite;
  will-change: transform, opacity;
}

/* Neural network nodes */
.neural-node {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.3);
  will-change: transform, opacity;
}

.node-1 {
  width: 12px;
  height: 12px;
  top: 20px;
  left: 70px;
  animation: float-1 4s ease-in-out infinite;
}

.node-2 {
  width: 8px;
  height: 8px;
  top: 40px;
  right: 30px;
  animation: float-2 3.5s ease-in-out infinite 0.5s;
}

.node-3 {
  width: 10px;
  height: 10px;
  bottom: 30px;
  right: 50px;
  animation: float-3 4.5s ease-in-out infinite 1s;
}

.node-4 {
  width: 14px;
  height: 14px;
  bottom: 40px;
  left: 40px;
  animation: float-4 3.8s ease-in-out infinite 0.8s;
}

.node-5 {
  width: 6px;
  height: 6px;
  top: 60px;
  left: 30px;
  animation: float-5 3.2s ease-in-out infinite 1.2s;
}

.node-6 {
  width: 9px;
  height: 9px;
  top: 80px;
  right: 45px;
  animation: float-6 4.2s ease-in-out infinite 0.3s;
}

.node-7 {
  width: 11px;
  height: 11px;
  bottom: 70px;
  left: 80px;
  animation: float-7 3.7s ease-in-out infinite 1.5s;
}

/* Connecting lines */
.connection {
  position: absolute;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.6), transparent);
  border-radius: 1px;
  transform-origin: left center;
  will-change: transform, opacity;
}

.line-1 {
  width: 60px;
  top: 50px;
  left: 60px;
  transform: rotate(25deg);
  animation: pulse-line 2s ease-in-out infinite;
}

.line-2 {
  width: 50px;
  top: 110px;
  left: 70px;
  transform: rotate(-30deg);
  animation: pulse-line 2.5s ease-in-out infinite 0.5s;
}

.line-3 {
  width: 45px;
  top: 80px;
  right: 50px;
  transform: rotate(60deg);
  animation: pulse-line 2.2s ease-in-out infinite 1s;
}

.line-4 {
  width: 55px;
  bottom: 60px;
  left: 50px;
  transform: rotate(-45deg);
  animation: pulse-line 2.8s ease-in-out infinite 1.3s;
}

/* Central brain icon */
.brain-center {
  position: absolute;
  width: 40px;
  height: 40px;
  color: #3b82f6;
  animation: brain-pulse 2s ease-in-out infinite;
  will-change: transform, opacity;
}

.brain-center svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.3));
}

/* Animations */
@keyframes glow-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.6;
  }
  50% {
    transform: scale(1.1);
    opacity: 0.8;
  }
}

@keyframes brain-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.7;
  }
  50% {
    transform: scale(1.1);
    opacity: 1;
  }
}

@keyframes float-1 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.7;
  }
  25% {
    transform: translate(10px, -8px) scale(1.1);
    opacity: 1;
  }
  50% {
    transform: translate(-5px, -15px) scale(0.9);
    opacity: 0.8;
  }
  75% {
    transform: translate(-12px, -5px) scale(1.05);
    opacity: 0.9;
  }
}

@keyframes float-2 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.6;
  }
  33% {
    transform: translate(-8px, 12px) scale(1.2);
    opacity: 1;
  }
  66% {
    transform: translate(6px, -8px) scale(0.8);
    opacity: 0.7;
  }
}

@keyframes float-3 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.8;
  }
  30% {
    transform: translate(-10px, -10px) scale(1.15);
    opacity: 1;
  }
  70% {
    transform: translate(8px, 5px) scale(0.85);
    opacity: 0.6;
  }
}

@keyframes float-4 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.7;
  }
  40% {
    transform: translate(12px, -6px) scale(1.1);
    opacity: 1;
  }
  80% {
    transform: translate(-6px, 10px) scale(0.9);
    opacity: 0.8;
  }
}

@keyframes float-5 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.5;
  }
  50% {
    transform: translate(-15px, 8px) scale(1.3);
    opacity: 1;
  }
}

@keyframes float-6 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.6;
  }
  35% {
    transform: translate(8px, -12px) scale(1.2);
    opacity: 1;
  }
  65% {
    transform: translate(-10px, 6px) scale(0.8);
    opacity: 0.7;
  }
}

@keyframes float-7 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.8;
  }
  45% {
    transform: translate(-8px, -8px) scale(1.1);
    opacity: 1;
  }
  85% {
    transform: translate(10px, 12px) scale(0.9);
    opacity: 0.6;
  }
}

@keyframes pulse-line {
  0%, 100% {
    opacity: 0;
    transform: scaleX(0) scaleY(1);
  }
  20% {
    opacity: 0.6;
    transform: scaleX(0.3) scaleY(1);
  }
  50% {
    opacity: 1;
    transform: scaleX(1) scaleY(1.5);
  }
  80% {
    opacity: 0.4;
    transform: scaleX(0.7) scaleY(1);
  }
}

/* Responsive adjustments */
@media (max-width: 480px) {
  .ai-thinking-container {
    width: 160px;
    height: 160px;
  }
  
  .bg-glow {
    width: 140px;
    height: 140px;
  }
  
  .brain-center {
    width: 32px;
    height: 32px;
  }
}
</style>
