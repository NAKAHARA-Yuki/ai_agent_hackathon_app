<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useActivePlanStore } from '@/stores/activePlanStore'
import { agentChat, dayAdvice } from '@/services/apiClient'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const activePlanStore = useActivePlanStore()

// Constants for UI display limits
const SESSION_ID_PREFIX = 'travel-day-'
const MAX_DISPLAYED_PLACES = 5
const MAX_DISPLAYED_CITATIONS = 3

const plan = ref(null)
const messages = ref([])
const inputMessage = ref('')
const loading = ref(false)
const chatContainer = ref(null)
const sessionId = ref('')

// Generate session ID for this chat
function generateUUID() {
  if (crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

sessionId.value = SESSION_ID_PREFIX + generateUUID()

async function loadPlan() {
  try {
    const planId = route.params.id
    
    // First check if this plan is the active plan
    await activePlanStore.fetchActivePlan()
    if (activePlanStore.activePlanId !== planId) {
      // If not active, try to activate it
      await activePlanStore.activatePlan(planId)
    }
    
    plan.value = activePlanStore.activePlan
    
    if (!plan.value) {
      throw new Error('Plan not found or could not be activated')
    }
    
    // Add initial system message
    messages.value.push({
      id: Date.now(),
      type: 'system',
      content: `こんにちは！旅行当日モードです。「${plan.value.title}」のプランを参考に、現地での質問やお困りごとにお答えします。\n\n例：「空いた時間にカフェを探したい」「雨が降ってきたので代替プランを教えて」など、お気軽にご相談ください。`,
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
  
  scrollToBottom()
  
  loading.value = true
  
  try {
    // Primary: Use day_advice endpoint with current plan context
    let response
    try {
      response = await dayAdvice({
        plan: plan.value,
        user_message: userMessage,
        current_context: {},
        session_id: sessionId.value,
        authHeader: auth.authHeader()
      })
    } catch (e) {
      // Fallback: standard chat if day_advice fails
      response = await agentChat({
        message: userMessage,
        user_id: auth.user?.id || 'u_local',
        session_id: sessionId.value,
        authHeader: auth.authHeader()
      })
    }

    // Add AI response
    const aiMsg = {
      id: Date.now() + 1,
      type: 'assistant',
      content: (response && (response.message || response.reply)) || 'お答えできませんでした。',
      timestamp: new Date(),
      places: response.places,
      citations: response.citations,
      route_info: response.route_info,
      suggestions: response.suggestions
    }
    messages.value.push(aiMsg)

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

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function goBack() {
  router.push('/plans')
}

const quickSuggestions = [
  '近くのカフェを教えて',
  '雨の日の代替プランは？',
  '美味しいランチのお店を探して',
  '次の目的地への行き方は？',
  '周辺の観光スポットを教えて',
  '空いた時間の過ごし方は？'
]

function sendQuickMessage(message) {
  inputMessage.value = message
  sendMessage()
}

onMounted(loadPlan)
</script>

<template>
  <div class="travel-day-chat">
    <!-- Header -->
    <div class="chat-header">
      <button class="back-btn" @click="goBack" aria-label="戻る">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6"/>
        </svg>
      </button>
      <div class="header-content">
        <h1>旅行当日モード</h1>
        <p v-if="plan">{{ plan.title }}</p>
      </div>
      <div class="travel-day-badge">
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
        </svg>
      </div>
    </div>

    <!-- Chat Messages -->
    <div ref="chatContainer" class="chat-container">
      <div class="messages">
        <div v-for="message in messages" :key="message.id" class="message" :class="message.type">
          <div class="message-content">
            <div class="message-text">{{ message.content }}</div>
            
            <!-- Suggestions if provided (day_advice) -->
            <div v-if="message.suggestions && message.suggestions.length" class="message-suggestions">
              <h4>提案</h4>
              <ul class="suggestions-list">
                <li v-for="(s,i) in message.suggestions" :key="i">
                  <strong>{{ s.title || s.type }}</strong>
                  <span v-if="s.description" class="suggestion-desc"> — {{ s.description }}</span>
                </li>
              </ul>
            </div>

            <!-- Places if provided -->
            <div v-if="message.places && message.places.length" class="message-places">
              <h4>おすすめスポット</h4>
              <div class="places-list">
                <div v-for="(place, i) in message.places.slice(0, MAX_DISPLAYED_PLACES)" :key="i" class="place-item">
                  <strong>{{ place.name }}</strong>
                  <span v-if="place.note" class="place-note">{{ place.note }}</span>
                </div>
              </div>
            </div>
            
            <!-- Citations if provided -->
            <div v-if="message.citations && message.citations.length" class="message-citations">
              <details>
                <summary>参考情報 ({{ message.citations.length }}件)</summary>
                <div class="citations-list">
                  <a v-for="citation in message.citations.slice(0, MAX_DISPLAYED_CITATIONS)" 
                     :key="citation.index" 
                     :href="citation.uri" 
                     target="_blank" 
                     rel="noopener"
                     class="citation-link">
                    [{{ citation.index }}] {{ citation.title }}
                  </a>
                </div>
              </details>
            </div>
            
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

    <!-- Quick Suggestions -->
    <div v-if="messages.length <= 2" class="quick-suggestions">
      <h3>よくある質問</h3>
      <div class="suggestions-grid">
        <button 
          v-for="suggestion in quickSuggestions" 
          :key="suggestion"
          @click="sendQuickMessage(suggestion)"
          class="suggestion-btn"
          :disabled="loading"
        >
          {{ suggestion }}
        </button>
      </div>
    </div>

    <!-- Chat Input -->
    <div class="chat-input">
      <div class="input-container">
        <textarea
          v-model="inputMessage"
          placeholder="旅行中のご質問をどうぞ..."
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
    </div>
  </div>
</template>

<style scoped>
.travel-day-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100vh;
  background: linear-gradient(135deg, #f0fdf4, #f8fafc);
  overflow: hidden;
}

/* Header */
.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
}

.back-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: white;
  transition: background 0.2s;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.header-content {
  flex: 1;
}

.header-content h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.header-content p {
  margin: 2px 0 0;
  font-size: 14px;
  opacity: 0.9;
}

.travel-day-badge {
  width: 32px;
  height: 32px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.travel-day-badge svg {
  width: 18px;
  height: 18px;
}

/* Chat Container */
.chat-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  padding-bottom: 8px;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
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
  background: #10b981;
  color: white;
  border-bottom-right-radius: 6px;
}

.message.assistant .message-content, .message.system .message-content {
  background: white;
  color: #1e293b;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.message.system .message-content {
  background: #f0f9ff;
  border-color: #bae6fd;
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
  margin-bottom: 8px;
}

.message-places {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.message-places h4 {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 8px;
  color: #374151;
}

.places-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.place-item {
  font-size: 13px;
  padding: 6px 10px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.place-item strong {
  color: #1e293b;
  margin-right: 6px;
}

.place-note {
  color: #64748b;
  font-size: 12px;
}

.message-citations {
  margin-top: 8px;
  font-size: 12px;
}

.message-citations details {
  color: #64748b;
}

.citations-list {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.citation-link {
  color: #2563eb;
  text-decoration: none;
  font-size: 11px;
}

.citation-link:hover {
  text-decoration: underline;
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

/* Quick Suggestions */
.quick-suggestions {
  background: white;
  margin: 8px 16px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.quick-suggestions h3 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px;
  color: #374151;
}

.suggestions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
}

.suggestion-btn {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 8px 12px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.suggestion-btn:hover:not(:disabled) {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #334155;
}

.suggestion-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Chat Input */
.chat-input {
  background: white;
  border-top: 1px solid #e2e8f0;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  flex-shrink: 0;
}

.input-container {
  display: flex;
  align-items: flex-end;
  gap: 8px;
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
  border-color: #10b981;
  background: white;
}

.send-btn {
  width: 44px;
  height: 44px;
  background: #10b981;
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
  background: #059669;
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

/* Responsive */
@media (min-width: 640px) {
  .travel-day-chat {
    max-width: 800px;
    margin: 0 auto;
  }
  
  .message-content {
    max-width: 70%;
  }
  
  .suggestions-grid {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }
}

@media (max-width: 480px) {
  .chat-header {
    padding: 12px 16px;
  }
  
  .header-content h1 {
    font-size: 16px;
  }
  
  .message-content {
    max-width: 90%;
    padding: 10px 14px;
  }
  
  .message-text {
    font-size: 13px;
  }
  
  .chat-input {
    padding: 8px 12px;
  }
  
  .message-input {
    font-size: 16px; /* Prevents zoom on iOS */
    padding: 10px 14px;
  }
  
  .suggestions-grid {
    grid-template-columns: 1fr 1fr;
  }
  
  .suggestion-btn {
    font-size: 12px;
    padding: 6px 10px;
  }
}
</style>