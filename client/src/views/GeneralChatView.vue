<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { generalChat } from '@/services/apiClient'

const router = useRouter()
const auth = useAuthStore()

const messages = ref([])
const inputMessage = ref('')
const loading = ref(false)
const chatContainer = ref(null)
const sessionId = ref('')
const locationEnabled = ref(false)
const currentLocation = ref(null)
const locationLoading = ref(false)

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

sessionId.value = generateUUID()

// Geolocation functions
async function getCurrentLocation() {
  if (!navigator.geolocation) {
    throw new Error('位置情報サービスがサポートされていません。')
  }

  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy
        })
      },
      (error) => {
        let message = '位置情報の取得に失敗しました。'
        switch(error.code) {
          case error.PERMISSION_DENIED:
            message = '位置情報の利用が拒否されました。ブラウザの設定を確認してください。'
            break
          case error.POSITION_UNAVAILABLE:
            message = '位置情報が利用できません。'
            break
          case error.TIMEOUT:
            message = '位置情報の取得がタイムアウトしました。'
            break
        }
        reject(new Error(message))
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000 // 5 minutes
      }
    )
  })
}

async function enableLocation() {
  locationLoading.value = true
  try {
    const location = await getCurrentLocation()
    currentLocation.value = location
    locationEnabled.value = true
    
    // Add confirmation message
    messages.value.push({
      id: Date.now(),
      type: 'system',
      content: `位置情報を有効にしました。現在地周辺の情報を含めた案内ができます。`,
      timestamp: new Date()
    })
    scrollToBottom()
  } catch (error) {
    console.error('Location error:', error)
    messages.value.push({
      id: Date.now(),
      type: 'error',
      content: error.message,
      timestamp: new Date()
    })
    scrollToBottom()
  } finally {
    locationLoading.value = false
  }
}

function disableLocation() {
  locationEnabled.value = false
  currentLocation.value = null
  messages.value.push({
    id: Date.now(),
    type: 'system',
    content: '位置情報を無効にしました。',
    timestamp: new Date()
  })
  scrollToBottom()
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
    // Prepare location data if enabled
    let location = null
    if (locationEnabled.value && currentLocation.value) {
      location = {
        latitude: currentLocation.value.latitude,
        longitude: currentLocation.value.longitude
      }
    }
    
  const response = await generalChat({
      message: userMessage,
      user_id: auth.user?.id || 'u_local',
      session_id: sessionId.value,
      location: location,
      authHeader: auth.authHeader()
    })
    
    // Add assistant response (prefer new JSON schema: message, with fallback to reply)
    // Extract renderedContent if available
    let renderedContent = null
    try {
      const gm = response.grounding_metadata || response.groundingMetadata || {}
      const sep = gm.search_entry_point || gm.searchEntryPoint || {}
      renderedContent = sep.rendered_content || sep.renderedContent || null
    } catch (e) { /* noop */ }

    messages.value.push({
      id: Date.now() + 1,
      type: 'assistant',
      content: response.message || response.reply || 'すみません、応答を生成できませんでした。',
      timestamp: new Date(),
      // keep optional fields if present
      suggestions: response.suggestions || [],
      places: response.places || [],
      route_info: response.route_info || null,
      citations: response.citations || [],
      grounding_html: response.grounding_html || null,
      rendered_content: renderedContent
    })
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
  router.push('/main')
}

const quickSuggestions = [
  '近くのカフェを教えて',
  '観光スポットを探したい',
  '美味しいランチのお店は？', 
  '最寄り駅への行き方は？',
  '周辺のコンビニはある？',
  '今日の天気はどう？'
]

function sendQuickMessage(message) {
  inputMessage.value = message
  sendMessage()
}

onMounted(() => {
  // Add welcome message
  messages.value.push({
    id: Date.now(),
    type: 'system',
    content: 'こんにちは！何かお手伝いできることはありますか？\n\n位置情報を有効にすると、現在地周辺の情報を含めた案内ができます。',
    timestamp: new Date()
  })
})
</script>

<template>
  <div class="general-chat">
    <!-- Header -->
    <div class="chat-header">
      <button class="back-btn" @click="goBack" aria-label="戻る">
        <v-icon name="chevron-left" :size="20" color="#ffffff" aria-label="戻る" />
      </button>
      <div class="header-content">
        <h1>チャット</h1>
      </div>
    </div>

    <!-- Chat Messages -->
    <div ref="chatContainer" class="chat-container">
      <div class="messages">
        <div v-for="message in messages" :key="message.id" class="message" :class="message.type">
          <div class="message-content">
            <div class="message-text">{{ message.content }}</div>
            <!-- Rendered content from GroundingMetadata (safe HTML assumed from Google SearchEntryPoint) -->
            <div v-if="message.rendered_content" class="rendered-content" v-html="message.rendered_content"></div>
            
            <!-- Citations if provided -->
            <div v-if="message.citations && message.citations.length" class="message-citations">
              <p class="citations-label">参考情報:</p>
              <ul>
                <li v-for="(citation, idx) in message.citations" :key="idx">{{ citation }}</li>
              </ul>
            </div>
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
    <div v-if="messages.length <= 1" class="quick-suggestions">
      <p class="suggestions-label">よくある質問:</p>
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
          placeholder="メッセージを入力してください..."
          @keydown.enter.prevent="!loading && sendMessage()"
          rows="1"
          class="message-input"
        ></textarea>
        <button 
          v-if="!locationEnabled"
          @click="enableLocation"
          :disabled="locationLoading"
          class="location-btn enable"
          aria-label="位置情報を有効にする"
        >
          <v-icon name="crosshairs-gps" :size="18" color="#6b7280" aria-label="位置情報" />
        </button>
        <button 
          v-else
          @click="disableLocation"
          class="location-btn enabled"
          aria-label="位置情報を無効にする"
        >
          <v-icon name="map-marker" :size="18" color="#16a34a" aria-label="位置情報有効" />
        </button>
        <button 
          @click="sendMessage" 
          :disabled="loading || !inputMessage.trim()"
          class="send-btn"
          aria-label="送信"
        >
          <v-icon name="send" :size="20" aria-label="送信" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.general-chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8fafc;
  overflow: hidden;
}

/* Header */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: white;
  padding: 8px 16px;
  padding-top: calc(8px + env(safe-area-inset-top));
  min-height: 48px;
  flex-shrink: 0;
}

.back-btn {
  background: rgba(255,255,255,0.2);
  border: none;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.back-btn:hover {
  background: rgba(255,255,255,0.3);
}

.header-content {
  flex: 1;
  text-align: center;
  margin: 0 16px;
}

.header-content h1 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
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

.message.assistant, .message.system, .message.error {
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

.message.assistant .message-content {
  background: white;
  color: #1f2937;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 6px;
}

.message.system .message-content {
  background: #f3f4f6;
  color: #6b7280;
  border-radius: 12px;
  text-align: center;
  max-width: 100%;
}

.message.error .message-content {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
  border-bottom-left-radius: 6px;
}

.message-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.5;
}

.message-citations {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0,0,0,0.1);
}

.citations-label {
  font-size: 12px;
  font-weight: 600;
  margin: 0 0 4px;
  opacity: 0.8;
}

.message-citations ul {
  margin: 0;
  padding-left: 16px;
  list-style-type: disc;
}

.message-citations li {
  font-size: 12px;
  opacity: 0.8;
  margin: 2px 0;
}

.rendered-content {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0,0,0,0.08);
  font-size: 12px;
  color: #374151;
}

/* Loading Animation */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #9ca3af;
  animation: typing 1.4s infinite ease-in-out;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes typing {
  0%, 80%, 100% { 
    transform: scale(0);
    opacity: 0.5;
  }
  40% { 
    transform: scale(1);
    opacity: 1;
  }
}

/* Quick Suggestions */
.quick-suggestions {
  padding: 16px;
  background: white;
  border-top: 1px solid #e5e7eb;
}

.suggestions-label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin: 0 0 12px;
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
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.suggestion-btn:hover:not(:disabled) {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.suggestion-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Chat Input */
.chat-input {
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: white;
  border-top: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.input-container {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.message-input {
  flex: 1;
  min-height: 36px;
  max-height: 100px;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 18px;
  font-size: 14px;
  resize: none;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
}

.message-input:focus {
  border-color: #3b82f6;
}

.location-btn {
  background: transparent;
  border: 1px solid #d1d5db;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.location-btn:hover:not(:disabled) {
  border-color: #9ca3af;
  background: #f9fafb;
}

.location-btn.enabled {
  border-color: #16a34a;
  background: #f0fdf4;
}

.location-btn.enabled:hover {
  background: #dcfce7;
}

.location-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send-btn {
  background: #3b82f6;
  border: none;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: #2563eb;
}

.send-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

/* Mobile Optimizations */
@media (max-width: 768px) {
  .chat-header {
    padding: 6px 12px;
    padding-top: calc(6px + env(safe-area-inset-top));
    min-height: 44px;
  }
  
  .header-content h1 {
    font-size: 15px;
  }
  
  .chat-container {
    padding: 12px;
  }
  
  .message-content {
    max-width: 90%;
    padding: 10px 14px;
  }
  
  .quick-suggestions {
    padding: 12px;
  }
  
  .suggestions-grid {
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 6px;
  }
  
  .suggestion-btn {
    padding: 6px 10px;
    font-size: 11px;
  }
  
  .chat-input {
    padding: 8px 12px;
    padding-bottom: calc(8px + env(safe-area-inset-bottom));
  }
}
</style>