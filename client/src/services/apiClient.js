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

  const reply = `以下は入力「${message}」に基づく簡易モックプランです。\n\n`+
    selected.map((p,i)=>`${i+1}. ${p.name} - ${p.note||''}`).join('\n')+
    `\n\n※ モックモード (VITE_USE_MOCK=true) で生成されています。`

  return { reply, places: selected, route_info: null, citations: [] }
}

// ---- Real Fetch Helper ----
async function realFetch(url, options){
  const resp = await fetch(url, options)
  
  // 401 レスポンスの場合は認証エラーを投げる
  if (resp.status === 401) {
    throw new Error('認証の有効期限が切れました。再度ログインしてください。')
  }
  
  if(!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
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

export async function listPlans(authHeader){
  if (!useMock) {
    try { return await realFetch('/api/plans', { headers:{ 'Content-Type':'application/json', ...(authHeader||{}) } }) } catch(e){ throw e }
  }
  const data = lsGet('mockPlans', [])
  return { items: data.map(p=>({ id:p.id, title:p.title, created_at:p.created_at, updated_at:p.updated_at })) }
}

export async function createPlan(payload, authHeader){
  if (!useMock) {
    const resp = await fetch('/api/plans', { method:'POST', headers:{ 'Content-Type':'application/json', ...(authHeader||{}) }, body: JSON.stringify(payload) })
    if(!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }
  const plans = lsGet('mockPlans', [])
  const now = new Date().toISOString()
  const doc = { id: randomId(), title: payload.title || '旅行プラン', text: payload.text||'', places: payload.places||[], route_info: payload.route_info||null, summary: payload.summary||null, suggestions: payload.suggestions||[], itinerary: payload.itinerary||[], created_at: now, updated_at: now, status: payload.status || 'confirmed' }
  plans.push(doc)
  lsSet('mockPlans', plans)
  return doc
}

export async function deletePlan(planId, authHeader){
  if (!useMock) {
    const resp = await fetch(`/api/plans/${planId}`, { method:'DELETE', headers:{ 'Content-Type':'application/json', ...(authHeader||{}) } })
    if(!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }
  // Mock: remove from localStorage
  const plans = lsGet('mockPlans', [])
  const filtered = plans.filter(p => p.id !== planId)
  lsSet('mockPlans', filtered)
  return { status: 'deleted' }
}

export async function mapsKey(){
  if (!useMock) {
    try { return await realFetch('/api/maps-key') } catch { return { key:'', advanced:false, mapId:'' } }
  }
  return { key:'', advanced:false, mapId:'' }
}

export function isMock(){ return useMock }
