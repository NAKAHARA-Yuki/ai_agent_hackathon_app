<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { agentChat, createPlan } from '@/services/apiClient'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const originalPlan = ref(null)
const currentPlan = ref(null)
const messages = ref([])
const inputMessage = ref('')
const loading = ref(false)
const chatContainer = ref(null)
const sessionId = ref('')
const saving = ref(false)

// Generate session ID for this chat
sessionId.value = crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`

async function loadPlan() {
  try {
    const planId = route.params.id
    const resp = await fetch(`/api/plans/${planId}`, { 
      headers: { 'Content-Type': 'application/json', ...(auth.authHeader() || {}) } 
    })
    if (!resp.ok) throw new Error('Plan not found')
    
    const plan = await resp.json()
    originalPlan.value = plan
    currentPlan.value = { ...plan }
    
    // Add initial system message
    messages.value.push({
      id: Date.now(),
      type: 'system',
      content: `こんにちは！「${plan.title}」のプランをより良くするお手伝いをします。どのような変更をご希望ですか？`,
      timestamp: new Date()
    })
  } catch (e) {
    console.error('Failed to load plan:', e)
    router.push('/plans')
  }
}

async function sendMessage() {
  if (!inputMessage.value.trim() || loading.value) return
  
  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  
  // Add user message
  const userMsg = {
    id: Date.now(),
    type: 'user',
    content: userMessage,
    timestamp: new Date()
  }
  messages.value.push(userMsg)
  
  // Scroll to bottom
  scrollToBottom()
  
  loading.value = true
  
  try {
    // Create context message with current plan details
    const contextMessage = `現在のプラン「${currentPlan.value.title}」について相談があります。

${currentPlan.value.summary ? `概要: ${currentPlan.value.summary}` : ''}

${currentPlan.value.itinerary?.length ? 
  '現在の日程:\n' + currentPlan.value.itinerary.map((day, i) => 
    `Day ${day.day || i+1}:\n` + 
    (day.items || []).map(item => `- ${item.time || ''} ${item.title}`).join('\n')
  ).join('\n\n') : ''
}

ユーザーの要望: ${userMessage}

上記のプランを改善した新しいプランを提案してください。できれば places 配列と itinerary も含めて JSON 形式で返してください。`

    const response = await agentChat({
      message: contextMessage,
      user_id: auth.user?.id || 'u_local',
      session_id: sessionId.value,
      authHeader: auth.authHeader()
    })
    
    // Add AI response
    const aiMsg = {
      id: Date.now() + 1,
      type: 'assistant',
      content: response.reply || 'プランを更新しました。',
      timestamp: new Date(),
      plan: response
    }
    messages.value.push(aiMsg)
    
    // Update current plan with new data
    if (response.summary || response.plans?.length || response.itinerary?.length || response.places?.length) {
      const updatedPlan = { ...currentPlan.value }
      
      if (response.summary) updatedPlan.summary = response.summary
      if (response.plans?.length) {
        // Use first plan from suggestions
        const firstPlan = response.plans[0]
        if (firstPlan.title) updatedPlan.title = firstPlan.title
        if (firstPlan.itinerary) updatedPlan.itinerary = firstPlan.itinerary
        if (firstPlan.places) updatedPlan.places = firstPlan.places
      }
      if (response.itinerary?.length) updatedPlan.itinerary = response.itinerary
      if (response.places?.length) updatedPlan.places = response.places
      if (response.suggestions?.length) updatedPlan.suggestions = response.suggestions
      
      currentPlan.value = updatedPlan
    }
    
  } catch (error) {
    console.error('Chat error:', error)
    messages.value.push({
      id: Date.now() + 1,
      type: 'error',
      content: 'エラーが発生しました。もう一度お試しください。',
      timestamp: new Date()
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function savePlan() {
  if (saving.value) return
  
  saving.value = true
  try {
    const planData = {
      title: currentPlan.value.title + ' (改善版)',
      text: currentPlan.value.text || currentPlan.value.summary || '',
      summary: currentPlan.value.summary,
      itinerary: currentPlan.value.itinerary || [],
      places: currentPlan.value.places || [],
      route_info: currentPlan.value.route_info,
      suggestions: currentPlan.value.suggestions || [],
      status: 'confirmed'
    }
    
    await createPlan(planData, auth.authHeader())
    
    // Redirect to plans list
    router.push('/plans')
  } catch (error) {
    console.error('Save error:', error)
    alert('保存に失敗しました。もう一度お試しください。')
  } finally {
    saving.value = false
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function goBack() {
  router.back()
}

const hasChanges = computed(() => {
  return JSON.stringify(currentPlan.value) !== JSON.stringify(originalPlan.value)
})

onMounted(loadPlan)
</script>

<template>
  <div class="plan-chat-view">
    <!-- Header -->
    <div class="chat-header">
      <button class="back-btn" @click="goBack" aria-label="戻る">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6"/>
        </svg>
      </button>
      <div class="header-content">
        <h1>プランをブラッシュアップ</h1>
        <p v-if="originalPlan">{{ originalPlan.title }}</p>
      </div>
    </div>

    <!-- Current Plan Preview -->
    <div v-if="currentPlan" class="plan-preview">
      <div class="plan-header">
        <h2>{{ currentPlan.title }}</h2>
        <span v-if="hasChanges" class="modified-badge">更新済み</span>
      </div>
      
      <div v-if="currentPlan.itinerary?.length" class="mini-itinerary">
        <div v-for="(day, idx) in currentPlan.itinerary.slice(0, 2)" :key="idx" class="mini-day">
          <strong>Day {{ day.day || (idx+1) }}</strong>
          <div class="mini-items">
            <span v-for="(item, i) in (day.items || []).slice(0, 3)" :key="i" class="mini-item">
              {{ item.title }}
            </span>
            <span v-if="day.items?.length > 3" class="more">+{{ day.items.length - 3 }}件</span>
          </div>
        </div>
        <div v-if="currentPlan.itinerary.length > 2" class="more-days">
          +{{ currentPlan.itinerary.length - 2 }}日間
        </div>
      </div>
    </div>

    <!-- Chat Messages -->
    <div ref="chatContainer" class="chat-container">
      <div class="messages">
        <div v-for="message in messages" :key="message.id" class="message" :class="message.type">
          <div class="message-content">
            <div class="message-text">{{ message.content }}</div>
            <div class="message-time">{{ message.timestamp.toLocaleTimeString() }}</div>
          </div>
        </div>
        
        <!-- Loading indicator -->
        <div v-if="loading" class="message assistant">
          <div class="message-content">
            <div class="typing-indicator">
              <div class="dot"></div>
              <div class="dot"></div>
              <div class="dot"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Chat Input -->
    <div class="chat-input">
      <div class="input-container">
        <textarea
          v-model="inputMessage"
          placeholder="プランの改善点を教えてください..."
          @keydown.enter.prevent="!loading && sendMessage()"
          rows="1"
          class="message-input"
        ></textarea>
        <button 
          @click="sendMessage" 
          :disabled="loading || !inputMessage.trim()"
          class="send-btn"
          aria-label="送信"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M2 12l20-8-8 8-12 0z"/>
            <path d="M14 12l8-8-8 8z"/>
          </svg>
        </button>
      </div>
      
      <!-- Action Buttons -->
      <div class="action-buttons">
        <button 
          v-if="hasChanges"
          @click="savePlan" 
          :disabled="saving"
          class="save-btn"
        >
          {{ saving ? '保存中...' : 'プランを保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plan-chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8fafc;
}

/* Header */
.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: white;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.back-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: #f1f5f9;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #64748b;
}

.back-btn:hover {
  background: #e2e8f0;
  color: #475569;
}

.header-content h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}

.header-content p {
  margin: 2px 0 0;
  font-size: 14px;
  color: #64748b;
}

/* Plan Preview */
.plan-preview {
  background: white;
  margin: 8px 16px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.plan-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.plan-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.modified-badge {
  background: #10b981;
  color: white;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.mini-itinerary {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mini-day {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mini-day strong {
  font-size: 12px;
  color: #475569;
}

.mini-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mini-item, .more {
  background: #f1f5f9;
  color: #475569;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 6px;
}

.more-days {
  font-size: 11px;
  color: #64748b;
  text-align: center;
  padding: 4px;
}

/* Chat Container */
.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  padding-bottom: 8px;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 100%;
}

.message {
  display: flex;
  align-items: flex-end;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant, .message.system {
  justify-content: flex-start;
}

.message-content {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 18px;
  position: relative;
}

.message.user .message-content {
  background: #3b82f6;
  color: white;
  border-bottom-right-radius: 6px;
}

.message.assistant .message-content, .message.system .message-content {
  background: white;
  color: #1e293b;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 6px;
}

.message.error .message-content {
  background: #fee2e2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.message-text {
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.message-time {
  font-size: 11px;
  opacity: 0.7;
  margin-top: 4px;
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  align-items: center;
}

.typing-indicator .dot {
  width: 6px;
  height: 6px;
  background: #94a3b8;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* Chat Input */
.chat-input {
  background: white;
  border-top: 1px solid #e2e8f0;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}

.input-container {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  margin-bottom: 8px;
}

.message-input {
  flex: 1;
  min-height: 44px;
  max-height: 120px;
  padding: 12px 16px;
  border: 1px solid #d1d5db;
  border-radius: 22px;
  font-size: 14px;
  resize: none;
  outline: none;
  background: #f9fafb;
}

.message-input:focus {
  border-color: #3b82f6;
  background: white;
}

.send-btn {
  width: 44px;
  height: 44px;
  background: #3b82f6;
  border: none;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: white;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #2563eb;
  transform: translateY(-1px);
}

.send-btn:disabled {
  background: #d1d5db;
  cursor: not-allowed;
}

.send-btn svg {
  width: 18px;
  height: 18px;
}

/* Action Buttons */
.action-buttons {
  display: flex;
  justify-content: center;
}

.save-btn {
  background: #10b981;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.save-btn:hover:not(:disabled) {
  background: #059669;
  transform: translateY(-1px);
}

.save-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

/* Responsive */
@media (min-width: 640px) {
  .plan-chat-view {
    max-width: 800px;
    margin: 0 auto;
  }
  
  .message-content {
    max-width: 70%;
  }
}
</style>