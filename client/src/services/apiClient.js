// シンプルな API クライアント & モック層
// import.meta.env.VITE_USE_MOCK === 'true' のときバックエンド不在でも動作

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

function lsGet(key, def){
  try { return JSON.parse(localStorage.getItem(key) || 'null') ?? def } catch { return def }
}
function lsSet(key, val){
  try { localStorage.setItem(key, JSON.stringify(val)) } catch {}
}
function randomId(){
  return (crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2,10)}`)
}

// ---- Mock Data Generators ----
function mockAgentReply(message){
  const basePlaces = [
    { name: '浅草寺', lat: 35.7148, lng: 139.7967, note: '歴史的寺院' },
    { name: '東京スカイツリー', lat: 35.7100, lng: 139.8107, note: '展望台' },
    { name: '上野公園', lat: 35.7156, lng: 139.7745, note: '博物館や自然' },
    { name: '築地場外市場', lat: 35.6655, lng: 139.7708, note: 'グルメ' },
  ]
  // キーワードから簡易フィルタ
  const kw = (message||'').toLowerCase()
  let selected = basePlaces
  if (kw.includes('温泉')) selected = [{ name:'草津温泉', note:'名湯' }, { name:'四万温泉', note:'静かな雰囲気' }]
  else if (kw.includes('京都')) selected = [{ name:'清水寺', note:'有名寺院' }, { name:'伏見稲荷大社', note:'千本鳥居' }, { name:'祇園', note:'伝統的街並み' }]

  const reply = `以下は入力「${message}」に基づく簡易プランです。\n\n`+
    selected.map((p,i)=>`${i+1}. ${p.name} - ${p.note||''}`).join('\n')

  return { reply, places: selected, route_info: null, citations: [] }
}

// ---- Real Fetch Helper ----
async function realFetch(url, options) {
  const MAX_RETRIES = 3;
  const BASE_DELAY = 1000; // 1秒
  
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const resp = await fetch(url, options);
      
      // 401 レスポンスの場合は認証エラーを投げる（リトライなし）
      if (resp.status === 401) {
        throw new Error('認証の有効期限が切れました。再度ログインしてください。');
      }
      
      // 503の場合はリトライする
      if (resp.status === 503) {
        if (attempt >= MAX_RETRIES) {
          // 最大リトライ回数に達した場合
          console.warn(`503 retry exhausted after ${MAX_RETRIES} attempts for ${url}`);
          throw new Error(`HTTP ${resp.status}`);
        }
        
        // 指数バックオフで待機
        const delay = BASE_DELAY * (2 ** attempt) + Math.random() * 1000;
        console.log(`503 error detected, retrying ${url} in ${delay.toFixed(0)}ms (attempt ${attempt + 1}/${MAX_RETRIES + 1})`);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue; // リトライ
      }
      
      // その他のHTTPエラー
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      
      return resp.json();
    } catch (error) {
      // ネットワークエラーやJSONパースエラーなど、HTTPステータス以外のエラーはそのまま投げる
      throw error;
    }
  }
}

// ---- Public API ----
export async function agentChat({ message, user_id, session_id, authHeader }){
  if (!useMock) {
    const data = await realFetch('/api/agent/chat', { method:'POST', headers:{ 'Content-Type':'application/json', ...(authHeader||{}) }, body: JSON.stringify({ message, user_id, session_id }) })
    if (import.meta.env.DEV) {
      try { console.log('[agentChat response]', data) } catch {}
    }
    return data
  }
  // artificial latency
  await new Promise(r=>setTimeout(r, 500))
  return mockAgentReply(message)
}

export async function modifyPlan({ plan, change_requests, constraints, context, session_id, authHeader }){
  if (!useMock) {
    const payload = { plan, change_requests, constraints, context, session_id }
    const data = await realFetch('/api/agent/modify_plan', { 
      method:'POST', 
      headers:{ 'Content-Type':'application/json', ...(authHeader||{}) }, 
      body: JSON.stringify(payload) 
    })
    if (import.meta.env.DEV) {
      try { console.log('[modifyPlan response]', data) } catch {}
    }
    return data
  }
  // Mock mode: return a lightly modified plan
  await new Promise(r=>setTimeout(r, 500))
  const updated = JSON.parse(JSON.stringify(plan||{}))
  if (updated && typeof updated.title === 'string') updated.title = `${updated.title} (修正案)`
  return {
    summary: typeof change_requests === 'string' ? `要望: ${change_requests}` : 'プランを更新しました',
    updated_plan: updated,
    diff: { added: [], removed: [], changed: [{ field: 'title', from: plan?.title || '', to: updated.title || '', reason: 'ユーザー要望に基づく微調整' }] }
  }
}

export async function dayAdvice({ plan, user_message, current_context, session_id, authHeader }){
  if (!useMock) {
    const payload = { plan, user_message, current_context, session_id }
    const data = await realFetch('/api/agent/day_advice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader||{}) },
      body: JSON.stringify(payload)
    })
    if (import.meta.env.DEV) {
      try { console.log('[dayAdvice response]', data) } catch {}
    }
    return data
  }
  // Mock: Return simple advice with minor schedule tweak
  await new Promise(r=>setTimeout(r, 400))
  const firstPlace = (plan?.places||[])[0]
  return {
    response_type: 'advice',
    message: typeof user_message === 'string' ? user_message.slice(0, 80) : 'アドバイスを表示します',
    suggestions: firstPlace ? [{
      type: 'route', title: '最適ルート案', description: `${firstPlace.name} への移動を混雑回避ルートに変更`, priority:'medium', estimated_time: null,
      location: { name: firstPlace.name, lat: firstPlace.lat||null, lng: firstPlace.lng||null }
    }] : [],
    updated_schedule: null,
    route_info: null
  }
}

export async function listPlans(authHeader){
  if (!useMock) {
    try { return await realFetch('/api/plans', { headers:{ 'Content-Type':'application/json', ...(authHeader||{}) } }) } catch(e){ throw e }
  }
  const data = lsGet('mockPlans', [])
  return { items: data.map(p=>({ 
    id:p.id, title:p.title, created_at:p.created_at, updated_at:p.updated_at,
    // include image fields for UI parity
    image_base64: p.image_base64||null, image_mime_type: p.image_mime_type||null,
    image_url: p.image_url||null, hero_image: p.hero_image||null,
    status: p.status||'confirmed'
  })) }
}

export async function createPlan(payload, authHeader){
  if (!useMock) {
    const resp = await fetch('/api/plans', { method:'POST', headers:{ 'Content-Type':'application/json', ...(authHeader||{}) }, body: JSON.stringify(payload) })
    if(!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }
  const plans = lsGet('mockPlans', [])
  const now = new Date().toISOString()
  const doc = { 
    id: randomId(), 
    title: payload.title || '旅行プラン', 
    text: payload.text||'', 
    places: payload.places||[], 
    route_info: payload.route_info||null, 
    summary: payload.summary||null, 
    suggestions: payload.suggestions||[], 
    itinerary: payload.itinerary||[], 
    // hero image fields
    image_base64: payload.image_base64||null,
    image_mime_type: payload.image_mime_type||null,
    image_url: payload.image_url||null,
    hero_image: payload.hero_image||null,
    created_at: now, 
    updated_at: now, 
    status: payload.status || 'confirmed' 
  }
  plans.push(doc)
  lsSet('mockPlans', plans)
  return doc
}

export async function mapsKey(){
  if (!useMock) {
    try { return await realFetch('/api/maps-key') } catch { return { key:'', advanced:false, mapId:'' } }
  }
  return { key:'', advanced:false, mapId:'' }
}

export async function getActivePlan(authHeader){
  if (!useMock) {
    try { 
      return await realFetch('/api/active-plan', { headers:{ 'Content-Type':'application/json', ...(authHeader||{}) } })
    } catch(e) { 
      throw e 
    }
  }
  const active = lsGet('mockActivePlan', null)
  return { active_plan: active }
}

export async function setActivePlan(planId, authHeader){
  if (!useMock) {
    const resp = await fetch('/api/active-plan', { 
      method:'POST', 
      headers:{ 'Content-Type':'application/json', ...(authHeader||{}) }, 
      body: JSON.stringify({ plan_id: planId }) 
    })
    if(!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }
  const plans = lsGet('mockPlans', [])
  const plan = plans.find(p => p.id === planId)
  if (plan) {
    lsSet('mockActivePlan', plan)
    return { active_plan: plan, status: 'activated' }
  } else if (planId === null) {
    lsSet('mockActivePlan', null)
    return { active_plan: null, status: 'deactivated' }
  } else {
    throw new Error('Plan not found')
  }
}

export async function planDetail(planId, authHeader) {
  if (!useMock) {
    const data = await realFetch(`/api/plans/${planId}`, { headers:{ 'Content-Type':'application/json', ...(authHeader||{}) } })
    return data
  }
  // Mock mode - find plan in localStorage
  const plans = lsGet('mockPlans', [])
  const plan = plans.find(p => p.id === planId)
  if (!plan) {
    throw new Error('Plan not found')
  }
  return plan
}

export async function deletePlan(planId, authHeader) {
  if (!useMock) {
    const resp = await fetch(`/api/plans/${planId}`, { 
      method: 'DELETE', 
      headers: { 'Content-Type': 'application/json', ...(authHeader||{}) } 
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }
  // Mock mode - remove plan from localStorage
  const plans = lsGet('mockPlans', [])
  const updatedPlans = plans.filter(p => p.id !== planId)
  lsSet('mockPlans', updatedPlans)
  
  // Also clear active plan if it was the deleted one
  const activePlan = lsGet('mockActivePlan', null)
  if (activePlan && activePlan.id === planId) {
    lsSet('mockActivePlan', null)
  }
  
  return { status: 'deleted' }
}

export function isMock(){ return useMock }

// Generate image from a travel plan via server Vertex AI endpoint
export async function generatePlanImage({ plan, style, modelId, authHeader }){
  if (!useMock) {
    const payload = { plan, style, model_id: modelId }
    const data = await realFetch('/api/agent/generate_plan_image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader||{}) },
      body: JSON.stringify(payload)
    })
    if (import.meta.env.DEV) {
      try { console.log('[generatePlanImage response]', { mime: data.image_mime_type, text: data.text?.slice?.(0,120) }) } catch {}
    }
    return data
  }
  // Mock: return a tiny transparent PNG (1x1)
  const transparentPngB64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII='
  await new Promise(r=>setTimeout(r, 300))
  return { image_base64: transparentPngB64, image_mime_type: 'image/png', text: 'mock image', model_id: modelId||'mock' }
}
