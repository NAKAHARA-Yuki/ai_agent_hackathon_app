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
function generateUUID() {
  if (crypto.randomUUID) {
    return crypto.randomUUID()
  }
  // Fallback: Generate proper UUID v4
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

sessionId.value = generateUUID()

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

function formatPlanContext(plan, userMessage) {
  const summarySection = plan.summary ? `概要: ${plan.summary}` : ''
  
  const itinerarySection = plan.itinerary?.length ? 
    '現在の日程:\n' + plan.itinerary.map((day, i) => 
      `Day ${day.day || i+1}:\n` + 
      (day.items || []).map(item => `- ${item.time || ''} ${item.title}`).join('\n')
    ).join('\n\n') : ''
  
  return `現在のプラン「${plan.title}」について相談があります。

${summarySection}

${itinerarySection}

ユーザーの要望: ${userMessage}

上記のプランを改善した新しいプランを提案してください。できれば places 配列と itinerary も含めて JSON 形式で返してください。`
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
    const contextMessage = formatPlanContext(currentPlan.value, userMessage)

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
    
    // Update current plan with new data while preserving existing data
    if (response.summary || response.plans?.length || response.itinerary?.length || response.places?.length) {
      const updatedPlan = { ...currentPlan.value }
      
      if (response.summary) updatedPlan.summary = response.summary
      if (response.plans?.length) {
        // Use first plan from suggestions
        const firstPlan = response.plans[0]
        if (firstPlan.title) updatedPlan.title = firstPlan.title
        if (firstPlan.itinerary?.length) updatedPlan.itinerary = firstPlan.itinerary
        if (firstPlan.places?.length) updatedPlan.places = firstPlan.places
      }
      if (response.itinerary?.length) updatedPlan.itinerary = response.itinerary
      if (response.places?.length) updatedPlan.places = response.places
      if (response.suggestions?.length) updatedPlan.suggestions = response.suggestions
      
      // Ensure itinerary is never lost - preserve from original if not in response
      if (!updatedPlan.itinerary || updatedPlan.itinerary.length === 0) {
        updatedPlan.itinerary = originalPlan.value.itinerary || []
      }
      
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
    // Ensure itinerary is preserved from either current or original plan
    const preservedItinerary = currentPlan.value.itinerary || originalPlan.value.itinerary || []
    
    const planData = {
      title: currentPlan.value.title + ' (改善版)',
      text: currentPlan.value.text || currentPlan.value.summary || '',
      summary: currentPlan.value.summary,
      itinerary: preservedItinerary,
      places: currentPlan.value.places || originalPlan.value.places || [],
      route_info: currentPlan.value.route_info || originalPlan.value.route_info,
      suggestions: currentPlan.value.suggestions || originalPlan.value.suggestions || [],
      status: 'confirmed'
    }
    
    await createPlan(planData, auth.authHeader())
    
    // Redirect to plans list
    router.push('/plans')
  } catch (error) {
    console.error('Save error:', error)
    messages.value.push({
      id: Date.now() + 1,
      type: 'error',
      content: '保存に失敗しました。もう一度お試しください。',
      timestamp: new Date()
    })
    scrollToBottom()
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

// Modal state for detailed view
const showDetailModal = ref(false)

function openDetailModal() {
  showDetailModal.value = true
}

function closeDetailModal() {
  showDetailModal.value = false
}

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

    <!-- Current Plan Preview - Clickable Card -->
    <div v-if="currentPlan" class="plan-preview" @click="openDetailModal">
      <div class="plan-header">
        <h2>{{ currentPlan.title }}</h2>
        <div class="header-right">
          <span v-if="hasChanges" class="modified-badge">更新済み</span>
          <svg class="tap-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 18l6-6-6-6"/>
          </svg>
        </div>
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
      
      <div class="tap-hint">タップして詳細を表示</div>
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

    <!-- Detailed Plan Modal -->
    <div v-if="showDetailModal" class="modal-overlay" @click="closeDetailModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>{{ currentPlan?.title }}</h2>
          <button class="close-btn" @click="closeDetailModal" aria-label="閉じる">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
        
        <div class="modal-body">
          <div v-if="currentPlan">
            <div v-if="hasChanges" class="update-notice">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 12l2 2 4-4"/>
                <circle cx="12" cy="12" r="10"/>
              </svg>
              このプランはブラッシュアップにより更新されました
            </div>
            
            <p v-if="currentPlan.summary" class="summary">{{ currentPlan.summary }}</p>
            
            <div v-if="currentPlan.suggestions && currentPlan.suggestions.length" class="suggestions">
              <h3>候補</h3>
              <ul>
                <li v-for="(s,i) in currentPlan.suggestions" :key="i">
                  <strong>{{ s.title }}</strong>
                  <span v-if="s.tags && s.tags.length" class="tags"> — {{ s.tags.join(' / ') }}</span>
                  <span v-if="s.brief" class="brief"> {{ s.brief }}</span>
                </li>
              </ul>
            </div>
            
            <div v-if="currentPlan.itinerary && currentPlan.itinerary.length" class="itinerary">
              <h3>日程</h3>
              <div v-for="(d,idx) in currentPlan.itinerary" :key="idx" class="day">
                <h4>Day {{ d.day || (idx+1) }}</h4>
                <ul class="items">
                  <li v-for="(it,i2) in d.items" :key="i2">
                    <span class="time" v-if="it.time">{{ it.time }}</span>
                    <span class="item-title">{{ it.title }}</span>
                    <span class="item-detail" v-if="it.detail"> — {{ it.detail }}</span>
                  </li>
                </ul>
              </div>
            </div>
            
            <div v-if="currentPlan.places && currentPlan.places.length" class="places">
              <h3>場所</h3>
              <ul>
                <li v-for="(p,i) in currentPlan.places" :key="i">{{ p.name }}<small v-if="p.note"> — {{ p.note }}</small></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plan-chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100vh;
  background: #f8fafc;
  overflow: hidden;
}

/* Header */
.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: calc(16px + env(safe-area-inset-top)) 16px 16px;
  background: white;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  position: sticky;
  top: 0;
  z-index: 100;
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

/* Plan Preview - Enhanced as clickable card */
.plan-preview {
  background: white;
  margin: 4px 16px 8px 16px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  flex-shrink: 0;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.plan-preview:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  border-color: #3b82f6;
}

.plan-preview:active {
  transform: translateY(-1px);
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
  flex: 1;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.modified-badge {
  background: #10b981;
  color: white;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.tap-icon {
  width: 18px;
  height: 18px;
  color: #64748b;
  transition: color 0.2s;
}

.plan-preview:hover .tap-icon {
  color: #3b82f6;
}

.mini-itinerary {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.mini-day {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mini-day strong {
  font-size: 13px;
  color: #475569;
  font-weight: 600;
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
  padding: 3px 8px;
  border-radius: 8px;
  font-weight: 500;
}

.more-days {
  font-size: 12px;
  color: #64748b;
  text-align: center;
  padding: 6px;
  background: #f8fafc;
  border-radius: 8px;
  font-weight: 500;
}

.tap-hint {
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
  padding: 4px;
  border-top: 1px solid #f1f5f9;
  margin-top: 8px;
  padding-top: 8px;
}

.plan-preview:hover .tap-hint {
  color: #3b82f6;
}

/* Chat Container - Optimized for single screen */
.chat-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 16px;
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

/* Chat Input - Compact for better screen usage */
.chat-input {
  background: white;
  border-top: 1px solid #e2e8f0;
  padding: 8px 16px;
  padding-bottom: calc(8px + env(safe-area-inset-bottom));
  flex-shrink: 0;
}

.input-container {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  margin-bottom: 6px;
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

/* Enhanced mobile optimizations */
@media (max-width: 480px) {
  .chat-header {
    padding: 12px 16px;
  }
  
  .chat-header h1 {
    font-size: 16px;
  }
  
  .plan-preview {
    margin: 4px 12px 8px 12px;
    padding: 14px;
    border-radius: 14px;
  }
  
  .plan-header h2 {
    font-size: 15px;
  }
  
  .mini-day strong {
    font-size: 12px;
  }
  
  .mini-item, .more {
    font-size: 10px;
    padding: 2px 6px;
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
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: white;
  border-radius: 20px;
  max-width: 90vw;
  max-height: 90vh;
  width: 100%;
  box-shadow: 0 20px 40px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Enhanced mobile modal optimization */
@media (max-width: 480px) {
  .modal-overlay {
    padding: 12px;
  }
  
  .modal-content {
    max-width: 95vw;
    max-height: 90vh;
    border-radius: 16px;
  }
  
  .modal-header {
    padding: 16px 20px;
  }
  
  .modal-body {
    padding: 20px;
  }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.modal-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  flex: 1;
}

.close-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: #f1f5f9;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #64748b;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #e2e8f0;
  color: #475569;
}

.close-btn svg {
  width: 18px;
  height: 18px;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}

.update-notice {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #dcfce7;
  color: #166534;
  padding: 12px 16px;
  border-radius: 12px;
  margin-bottom: 20px;
  font-size: 14px;
  font-weight: 500;
  border: 1px solid #bbf7d0;
}

.update-notice svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.modal-body .summary {
  margin: 0 0 20px;
  font-size: 14px;
  color: #475569;
  line-height: 1.6;
  background: #f8fafc;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.modal-body .suggestions,
.modal-body .itinerary,
.modal-body .places {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.modal-body h3 {
  font-size: 16px;
  margin: 0 0 12px;
  font-weight: 600;
  color: #334155;
}

.modal-body h4 {
  font-size: 14px;
  margin: 0 0 8px;
  font-weight: 600;
  color: #0f172a;
}

.modal-body .suggestions ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.modal-body .suggestions li {
  font-size: 14px;
  line-height: 1.5;
  color: #475569;
  padding: 8px;
  background: #f8fafc;
  border-radius: 8px;
}

.modal-body .suggestions .tags {
  color: #64748b;
  font-size: 12px;
}

.modal-body .suggestions .brief {
  color: #475569;
  font-size: 12px;
}

.modal-body .itinerary .day {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  margin: 12px 0;
}

.modal-body .itinerary .day:last-child {
  margin-bottom: 0;
}

.modal-body .items {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.modal-body .items li {
  font-size: 14px;
  line-height: 1.4;
  color: #475569;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 4px 0;
}

.modal-body .items .time {
  font-weight: 600;
  min-width: 60px;
  color: #0f172a;
}

.modal-body .items .item-title {
  font-weight: 500;
  color: #1e293b;
}

.modal-body .items .item-detail {
  color: #64748b;
}

.modal-body .places ul {
  list-style: disc;
  padding-left: 20px;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
  color: #475569;
}

.modal-body .places li small {
  color: #64748b;
  margin-left: 4px;
}

@media (min-width: 640px) {
  .modal-content {
    max-width: 600px;
  }
}
</style>