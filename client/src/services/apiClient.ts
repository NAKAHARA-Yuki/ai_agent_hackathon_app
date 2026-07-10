// TypeScript-safe API client & mock layer for Izatabi Next.js app
const useMock = process.env.NEXT_PUBLIC_USE_MOCK === 'true';

function lsGet<T>(key: string, def: T): T {
  if (typeof window === 'undefined') return def;
  try {
    const val = localStorage.getItem(key);
    return val ? (JSON.parse(val) as T) : def;
  } catch {
    return def;
  }
}

function lsSet<T>(key: string, val: T): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify(val));
  } catch {}
}

function randomId(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export interface Place {
  name: string;
  lat: number | null;
  lng: number | null;
  note?: string;
}

export interface ItineraryItem {
  day: number;
  activities: {
    time: string;
    title: string;
    description: string;
    location?: string;
  }[];
}

export interface Plan {
  id: string;
  title: string;
  text?: string;
  places?: Place[];
  route_info?: any;
  summary?: string | null;
  suggestions?: any[];
  itinerary?: ItineraryItem[];
  image_base64?: string | null;
  image_mime_type?: string | null;
  image_url?: string | null;
  hero_image?: string | null;
  created_at: string;
  updated_at: string;
  status: string;
}

export interface MemoryImage {
  image_base64: string | null;
  image_mime_type: string;
}

export interface Memory {
  id: string;
  plan_id: string;
  images: MemoryImage[];
  video_jobs?: any[];
  primary_video_url?: string | null;
  video_urls?: string[];
  title?: string;
  trip_start_date?: string;
  trip_end_date?: string;
  itinerary?: any[];
  created_at: string;
  updated_at: string;
}

// ---- Mock Data Generators ----
function mockAgentReply(message: string) {
  const basePlaces = [
    { name: '浅草寺', lat: 35.7148, lng: 139.7967, note: '歴史的寺院' },
    { name: '東京スカイツリー', lat: 35.7100, lng: 139.8107, note: '展望台' },
    { name: '上野公園', lat: 35.7156, lng: 139.7745, note: '博物館や自然' },
    { name: '築地場外市場', lat: 35.6655, lng: 139.7708, note: 'グルメ' },
  ];
  const kw = (message || '').toLowerCase();
  let selected = basePlaces;
  if (kw.includes('温泉')) {
    selected = [
      { name: '草津温泉', lat: 36.6212, lng: 138.5962, note: '名湯' },
      { name: '四万温泉', lat: 36.6853, lng: 138.7797, note: '静かな雰囲気' },
    ];
  } else if (kw.includes('京都')) {
    selected = [
      { name: '清水寺', lat: 34.9949, lng: 135.7850, note: '有名寺院' },
      { name: '伏見稲荷大社', lat: 34.9671, lng: 135.7727, note: '千本鳥居' },
      { name: '祇園', lat: 35.0037, lng: 135.7782, note: '伝統的街並み' },
    ];
  }

  const reply =
    `以下は入力「${message}」に基づく簡易プランです。\n\n` +
    selected.map((p, i) => `${i + 1}. ${p.name} - ${p.note || ''}`).join('\n');

  return { reply, places: selected, route_info: null, citations: [] };
}

// ---- Real Fetch Helper ----
async function realFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const MAX_RETRIES = 3;
  const BASE_DELAY = 1000;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const resp = await fetch(url, options);

      if (resp.status === 401) {
        throw new Error('認証の有効期限が切れました。再度ログインしてください。');
      }

      if (resp.status === 503) {
        if (attempt >= MAX_RETRIES) {
          console.warn(`503 retry exhausted after ${MAX_RETRIES} attempts for ${url}`);
          throw new Error(`HTTP ${resp.status}`);
        }

        const delay = BASE_DELAY * 2 ** attempt + Math.random() * 1000;
        console.log(
          `503 error detected, retrying ${url} in ${delay.toFixed(0)}ms (attempt ${attempt + 1}/${
            MAX_RETRIES + 1
          })`
        );
        await new Promise((resolve) => setTimeout(resolve, delay));
        continue;
      }

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      return (await resp.json()) as T;
    } catch (error) {
      throw error;
    }
  }
  throw new Error('Failed to fetch after retries');
}

// ---- Public API ----
export async function agentChat({
  message,
  user_id,
  session_id,
  authHeader,
}: {
  message: string;
  user_id: string;
  session_id: string;
  authHeader?: Record<string, string>;
}) {
  if (!useMock) {
    const data = await realFetch<any>('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
      body: JSON.stringify({ message, user_id, session_id }),
    });
    return data;
  }
  await new Promise((r) => setTimeout(r, 500));
  return mockAgentReply(message);
}

export async function modifyPlan({
  plan,
  change_requests,
  constraints,
  context,
  session_id,
  authHeader,
}: {
  plan: any;
  change_requests: string;
  constraints?: any;
  context?: any;
  session_id: string;
  authHeader?: Record<string, string>;
}) {
  if (!useMock) {
    const scrub = (obj: any) => {
      try {
        if (!obj || typeof obj !== 'object') return obj;
        const clone = JSON.parse(JSON.stringify(obj));
        const dropKeys = [
          'image_base64',
          'imageBase64',
          'image_url',
          'imageUrl',
          'thumbnail',
          'photo',
          'photos',
          'hero_image',
          'heroImage',
        ];
        const walk = (v: any): any => {
          if (!v || typeof v !== 'object') return v;
          if (Array.isArray(v)) return v.map(walk);
          for (const k of Object.keys(v)) {
            const lk = k.toLowerCase();
            if (
              dropKeys.includes(k) ||
              lk.endsWith('_image') ||
              lk.endsWith('_images') ||
              lk.endsWith('_image_url') ||
              lk.includes('base64')
            ) {
              delete v[k];
            } else {
              v[k] = walk(v[k]);
            }
          }
          return v;
        };
        return walk(clone);
      } catch {
        return obj;
      }
    };

    const payload = {
      plan: scrub(plan),
      change_requests,
      constraints: scrub(constraints),
      context: scrub(context),
      session_id,
    };
    const data = await realFetch<any>('/api/agent/modify_plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
      body: JSON.stringify(payload),
    });
    return data;
  }

  await new Promise((r) => setTimeout(r, 500));
  const updated = JSON.parse(JSON.stringify(plan || {}));
  if (updated && typeof updated.title === 'string') {
    updated.title = `${updated.title} (修正案)`;
  }
  return {
    summary:
      typeof change_requests === 'string' ? `要望: ${change_requests}` : 'プランを更新しました',
    updated_plan: updated,
    diff: {
      added: [],
      removed: [],
      changed: [
        {
          field: 'title',
          from: plan?.title || '',
          to: updated.title || '',
          reason: 'ユーザー要望に基づく微調整',
        },
      ],
    },
  };
}

export async function dayAdvice({
  plan,
  user_message,
  current_context,
  session_id,
  authHeader,
}: {
  plan: any;
  user_message: string;
  current_context: any;
  session_id: string;
  authHeader?: Record<string, string>;
}) {
  if (!useMock) {
    const scrub = (obj: any) => {
      try {
        if (!obj || typeof obj !== 'object') return obj;
        const clone = JSON.parse(JSON.stringify(obj));
        const dropKeys = [
          'image_base64',
          'imageBase64',
          'image_url',
          'imageUrl',
          'thumbnail',
          'photo',
          'photos',
          'hero_image',
          'heroImage',
        ];
        const walk = (v: any): any => {
          if (!v || typeof v !== 'object') return v;
          if (Array.isArray(v)) return v.map(walk);
          for (const k of Object.keys(v)) {
            const lk = k.toLowerCase();
            if (
              dropKeys.includes(k) ||
              lk.endsWith('_image') ||
              lk.endsWith('_images') ||
              lk.endsWith('_image_url') ||
              lk.includes('base64')
            ) {
              delete v[k];
            } else {
              v[k] = walk(v[k]);
            }
          }
          return v;
        };
        return walk(clone);
      } catch {
        return obj;
      }
    };

    const payload = { plan: scrub(plan), user_message, current_context: scrub(current_context), session_id };
    const data = await realFetch<any>('/api/agent/day_advice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
      body: JSON.stringify(payload),
    });
    return data;
  }

  await new Promise((r) => setTimeout(r, 400));
  const firstPlace = (plan?.places || [])[0];
  return {
    response_type: 'advice',
    message: typeof user_message === 'string' ? user_message.slice(0, 80) : 'アドバイスを表示します',
    suggestions: firstPlace
      ? [
          {
            type: 'route',
            title: '最適ルート案',
            description: `${firstPlace.name} への移動を混雑回避ルートに変更`,
            priority: 'medium',
            estimated_time: null,
            location: { name: firstPlace.name, lat: firstPlace.lat || null, lng: firstPlace.lng || null },
          },
        ]
      : [],
    updated_schedule: null,
    route_info: null,
  };
}

export async function generalChat({
  message,
  user_id,
  session_id,
  location,
  authHeader,
}: {
  message: string;
  user_id: string;
  session_id: string;
  location?: { latitude: number; longitude: number };
  authHeader?: Record<string, string>;
}) {
  if (!useMock) {
    const payload: any = { message, user_id, session_id };
    if (location) {
      payload.location = location;
    }
    const data = await realFetch<any>('/api/agent/general_chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
      body: JSON.stringify(payload),
    });
    return data;
  }

  await new Promise((r) => setTimeout(r, 600));
  const locNote =
    location && location.latitude && location.longitude
      ? `（現在位置: lat=${location.latitude}, lng=${location.longitude}）`
      : '';
  const messageOut = `「${message}」についてのご案内です。${locNote}`.trim();
  return {
    message: messageOut,
    places: [],
    response_type: 'information',
    route_info: null,
    suggestions: [],
    trace_id: Math.random().toString(16).slice(2, 18),
    grounding_metadata: {
      search_entry_point: {
        rendered_content: `<div style="font-size:12px;color:#374151">検索結果の例: <a href="https://www.google.com/search?q=${encodeURIComponent(
          message
        )}" target="_blank" rel="noopener noreferrer">${message}</a></div>`,
      },
      grounding_chunks: [],
      grounding_supports: [],
      retrieval_queries: [],
    },
  };
}

export async function listPlans(authHeader?: Record<string, string>) {
  if (!useMock) {
    return await realFetch<{ items: Plan[] }>('/api/plans', {
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
    });
  }
  const data = lsGet<Plan[]>('mockPlans', []);
  return {
    items: data.map((p) => ({
      id: p.id,
      title: p.title,
      created_at: p.created_at,
      updated_at: p.updated_at,
      image_base64: p.image_base64 || null,
      image_mime_type: p.image_mime_type || null,
      image_url: p.image_url || null,
      hero_image: p.hero_image || null,
      status: p.status || 'confirmed',
    })),
  };
}

export async function createPlan(payload: any, authHeader?: Record<string, string>) {
  if (!useMock) {
    const resp = await fetch('/api/plans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return (await resp.json()) as Plan;
  }
  const plans = lsGet<Plan[]>('mockPlans', []);
  const now = new Date().toISOString();
  const doc: Plan = {
    id: randomId(),
    title: payload.title || '旅行プラン',
    text: payload.text || '',
    places: payload.places || [],
    route_info: payload.route_info || null,
    summary: payload.summary || null,
    suggestions: payload.suggestions || [],
    itinerary: payload.itinerary || [],
    image_base64: payload.image_base64 || null,
    image_mime_type: payload.image_mime_type || null,
    image_url: payload.image_url || null,
    hero_image: payload.hero_image || null,
    created_at: now,
    updated_at: now,
    status: payload.status || 'confirmed',
  };
  plans.push(doc);
  lsSet('mockPlans', plans);
  return doc;
}

export async function getActivePlan(authHeader?: Record<string, string>) {
  if (!useMock) {
    return await realFetch<{ active_plan: Plan | null }>('/api/active-plan', {
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
    });
  }
  const active = lsGet<Plan | null>('mockActivePlan', null);
  return { active_plan: active };
}

export async function setActivePlan(planId: string | null, authHeader?: Record<string, string>) {
  if (!useMock) {
    const resp = await fetch('/api/active-plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
      body: JSON.stringify({ plan_id: planId }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return (await resp.json()) as { active_plan: Plan | null; status: string };
  }
  const plans = lsGet<Plan[]>('mockPlans', []);
  const plan = plans.find((p) => p.id === planId);
  if (plan) {
    lsSet('mockActivePlan', plan);
    return { active_plan: plan, status: 'activated' };
  } else if (planId === null) {
    lsSet('mockActivePlan', null);
    return { active_plan: null, status: 'deactivated' };
  } else {
    throw new Error('Plan not found');
  }
}

export async function planDetail(planId: string, authHeader?: Record<string, string>) {
  if (!useMock) {
    return await realFetch<Plan>(`/api/plans/${planId}`, {
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
    });
  }
  const plans = lsGet<Plan[]>('mockPlans', []);
  const plan = plans.find((p) => p.id === planId);
  if (!plan) {
    throw new Error('Plan not found');
  }
  return plan;
}

export async function listMemories(authHeader?: Record<string, string>) {
  if (!useMock) {
    return await realFetch<{ items: Memory[] }>('/api/memories', {
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
    });
  }
  const data = lsGet<Memory[]>('mockMemories', []);
  return { items: data };
}

export async function createMemory(payload: any, authHeader?: Record<string, string>) {
  if (!useMock) {
    const resp = await fetch('/api/memories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return (await resp.json()) as Memory;
  }
  const items = lsGet<Memory[]>('mockMemories', []);
  const now = new Date().toISOString();
  const images = Array.isArray(payload.images)
    ? payload.images.slice(0, 3).map((img: any) => ({
        image_base64: img.image_base64 || null,
        image_mime_type: img.image_mime_type || 'image/png',
      }))
    : [];
  const doc: Memory = {
    id: randomId(),
    plan_id: payload.plan_id,
    images,
    created_at: now,
    updated_at: now,
  };
  items.push(doc);
  lsSet('mockMemories', items);
  return doc;
}

export async function getMemory(id: string, authHeader?: Record<string, string>) {
  if (!useMock) {
    return await realFetch<Memory>(`/api/memories/${id}`, {
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
    });
  }
  const items = lsGet<Memory[]>('mockMemories', []);
  const m = items.find((x) => x.id === id);
  if (!m) throw new Error('Not found');
  return m;
}

export async function getMemoryVideoStatus(id: string, authHeader?: Record<string, string>) {
  if (!useMock) {
    return await realFetch<any>(`/api/memories/${id}/video-status`, {
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
    });
  }
  const items = lsGet<Memory[]>('mockMemories', []);
  const idx = items.findIndex((x) => x.id === id);
  if (idx === -1) return { video_jobs: [], all_done: true };
  const jobs = (items[idx].video_jobs || []).map((j: any) => ({ ...j, done: true }));
  items[idx].video_jobs = jobs;
  lsSet('mockMemories', items);
  return { video_jobs: jobs, all_done: true };
}

export async function deletePlan(planId: string, authHeader?: Record<string, string>) {
  if (!useMock) {
    const resp = await fetch(`/api/plans/${planId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return (await resp.json()) as { status: string };
  }
  const plans = lsGet<Plan[]>('mockPlans', []);
  const updatedPlans = plans.filter((p) => p.id !== planId);
  lsSet('mockPlans', updatedPlans);

  const activePlan = lsGet<Plan | null>('mockActivePlan', null);
  if (activePlan && activePlan.id === planId) {
    lsSet('mockActivePlan', null);
  }

  return { status: 'deleted' };
}

export function isMock(): boolean {
  return useMock;
}

export async function generatePlanImage({
  plan,
  style,
  modelId,
  authHeader,
}: {
  plan: any;
  style?: string;
  modelId?: string;
  authHeader?: Record<string, string>;
}) {
  if (!useMock) {
    const payload = { plan, style, model_id: modelId };
    const data = await realFetch<any>('/api/agent/generate_plan_image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(authHeader || {}) },
      body: JSON.stringify(payload),
    });
    return data;
  }
  const transparentPngB64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=';
  await new Promise((r) => setTimeout(r, 300));
  return {
    image_base64: transparentPngB64,
    image_mime_type: 'image/png',
    text: 'mock image',
    model_id: modelId || 'mock',
  };
}
