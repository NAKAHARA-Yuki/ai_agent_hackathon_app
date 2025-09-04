<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'

// Advanced Marker の利用可否フラグと mapId はサーバー設定から取得
const ENABLE_ADVANCED_MARKER = ref(false) // server hint; we'll still prefer AdvancedMarker if available at runtime
const MAP_ID = ref('')

const props = defineProps({
  places: { type: Array, default: () => [] },
  routeInfo: { type: Object, default: () => null }
})

// Google Maps の埋め込みは www.google.com を使用
const baseEmbed = 'https://www.google.com/maps?output=embed'
const iframeSrc = ref('')
const staticImgSrc = ref('')
const useJsMap = ref(false)
const mapsApiKey = ref('')
const rootEl = ref(null)
let map = null
let markers = []
let cluster = null
let directionsService = null
let directionsRenderer = null

const hasRoute = computed(() => !!(props.routeInfo && props.routeInfo.origin && props.routeInfo.destination))
const placesWithCoords = computed(() => (props.places || []).filter(p => Number.isFinite(p?.lat) && Number.isFinite(p?.lng)))

async function fetchMapsKey() {
  try {
    const r = await fetch('/api/maps-key')
    if (r.ok) {
      const j = await r.json()
  mapsApiKey.value = j.key || ''
  ENABLE_ADVANCED_MARKER.value = !!j.advanced
  MAP_ID.value = j.mapId || ''
    }
  } catch {}
}

function buildRouteEmbed() {
  const originStr = String(props.routeInfo.origin || '')
  const destStr = String(props.routeInfo.destination || '')
  const wps = Array.isArray(props.routeInfo.waypoints) ? props.routeInfo.waypoints.filter(Boolean) : []
  const mode = (props.routeInfo.mode || '').toLowerCase()

  // キー不要の q=dir 形式を常に使用（キー不正でも確実に表示）
  const parts = [`dir:${originStr}`]
  for (const w of wps) parts.push(`to:${w}`)
  parts.push(`to:${destStr}`)
  const q = encodeURIComponent(parts.join(' '))
  const params = new URLSearchParams({ q })
  if (['driving','walking','bicycling','transit'].includes(mode)) params.set('travelmode', mode)
  iframeSrc.value = `https://www.google.com/maps?output=embed&${params.toString()}`
  staticImgSrc.value = ''
}

function buildPlaceEmbed() {
  const first = (props.places || [])[0]
  if (!first) {
  // 日本付近にズームしたデフォルトビュー
  iframeSrc.value = `${baseEmbed}&ll=35.68,139.77&z=5`
    staticImgSrc.value = ''
    return
  }
  const hasCoords = Number.isFinite(first?.lat) && Number.isFinite(first?.lng)
  const q = encodeURIComponent(hasCoords ? `${first.lat},${first.lng}` : (first.name || ''))
  if (hasCoords) {
  // 座標がある場合は ll + q(lat,lng) で確実にピンを出す
  iframeSrc.value = `${baseEmbed}&z=15&ll=${first.lat},${first.lng}&q=${q}`
  } else {
  // 座標が無い場合は検索埋め込みの互換フォーマット
  // 例: https://www.google.com/maps?q=嬉野温泉&t=&z=13&ie=UTF8&iwloc=&output=embed
  iframeSrc.value = `https://www.google.com/maps?q=${q}&t=&z=13&ie=UTF8&iwloc=&output=embed`
  }
  staticImgSrc.value = ''
}

function injectScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve()
    const s = document.createElement('script')
    s.src = src
    s.async = true
    s.onload = () => resolve()
    s.onerror = reject
    document.head.appendChild(s)
  })
}

async function ensureMapsJs() {
  if (!mapsApiKey.value) return false
  if (window.google?.maps) return true
  const src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(mapsApiKey.value)}&v=weekly&language=ja&libraries=marker&loading=async`
  await injectScript(src)
  return !!window.google?.maps
}

async function ensureClusterer() {
  try {
    if (window.markerClusterer?.MarkerClusterer) return true
    await injectScript('https://unpkg.com/@googlemaps/markerclusterer/dist/index.min.js')
    return !!window.markerClusterer?.MarkerClusterer
  } catch {
    return false // クラスタリングは任意
  }
}

function clearMap() {
  if (markers) {
    for (const m of markers) try { m.setMap(null) } catch {}
  }
  markers = []
  if (cluster && cluster.clearMarkers) {
    try { cluster.clearMarkers() } catch {}
  }
  cluster = null
  if (directionsRenderer) {
    try { directionsRenderer.setMap(null) } catch {}
  }
  directionsRenderer = null
}

// ---- カスタムピン/テンプレ補助関数 ----
const PIN_SVG_PATH = 'M12 2C8.134 2 5 5.134 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.866-3.134-7-7-7zm0 11.5A2.5 2.5 0 1 1 12 8a2.5 2.5 0 0 1 0 5.5z'
const COLORS = ['#4285F4','#DB4437','#F4B400','#0F9D58','#AB47BC','#00ACC1','#FF7043','#9E9D24']
function colorForIndex(i) { return COLORS[i % COLORS.length] }
function letterForIndex(i) { return String.fromCharCode(65 + (i % 26)) }
function buildMarkerIcon(color) {
  // Material pin path with white stroke
  return {
    path: PIN_SVG_PATH,
    fillColor: color,
    fillOpacity: 1,
    strokeColor: '#ffffff',
    strokeWeight: 2,
    scale: 1.2,
    anchor: new google.maps.Point(12, 24),
    labelOrigin: new google.maps.Point(12, 12)
  }
}
function placeToGMapsLink(p) {
  const q = p?.name ? p.name : (typeof p?.lat === 'number' && typeof p?.lng === 'number' ? `${p.lat},${p.lng}` : '')
  if (!q) return ''
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`
}
function infoHtml(p, idx) {
  const name = p?.name || '場所'
  const link = placeToGMapsLink(p)
  const subtitle = p?.address || p?.note || ''
  const label = letterForIndex(idx)
  const hasImg = !!p?.imageUrl
  const dest = p?.name ? p.name : (typeof p?.lat === 'number' && typeof p?.lng === 'number' ? `${p.lat},${p.lng}` : '')
  const dirLink = dest ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(dest)}` : ''
  return `
  <div style="max-width:240px; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji';">
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
      <div style="width:22px;height:22px;border-radius:50%;background:${colorForIndex(idx)};color:#fff;font-weight:700;font-size:12px;display:flex;align-items:center;justify-content:center;">${label}</div>
      <div style="font-weight:600; font-size:14px; line-height:1.2;">
  ${link ? `<a href="${link}" target="_blank" rel="noopener" style="color:var(--color-text);text-decoration:none;">${name}</a>` : name}
      </div>
    </div>
    ${subtitle ? `<div style="color:#6B7280;font-size:12px;">${subtitle}</div>` : ''}
    ${hasImg ? `<img src="${p.imageUrl}" alt="${name}" style="width:100%;height:auto;border-radius:8px;margin-top:6px;"/>` : ''}
    <div style="display:flex;gap:10px;margin-top:8px;">
      ${link ? `<a href="${link}" target="_blank" rel="noopener" style="color:#2563EB;font-size:12px;">Googleで開く</a>` : ''}
      ${dirLink ? `<a href="${dirLink}" target="_blank" rel="noopener" style="color:#2563EB;font-size:12px;">経路</a>` : ''}
    </div>
  </div>`
}

// OSM フォールバックは使用しない（Google のみ）

function renderJsMap() {
  if (!rootEl.value) return false
  const coords = placesWithCoords.value
  if (!coords.length) return false
  if (!map) {
    try {
      const options = { center: { lat: coords[0].lat, lng: coords[0].lng }, zoom: 12, mapTypeControl: false }
      // mapId があれば常に付与（AdvancedMarker 利用時の警告回避）
      if (MAP_ID.value) { options.mapId = MAP_ID.value }
      map = new google.maps.Map(rootEl.value, options)
    } catch (e) {
      return false
    }
  }
  clearMap()
  const bounds = new google.maps.LatLngBounds()
  const iw = new google.maps.InfoWindow({ content: '' })
  // AdvancedMarker は mapId が設定されている場合のみ使用
  const hasAdvanced = !!google.maps.marker?.AdvancedMarkerElement && !!MAP_ID.value
  try {
    coords.forEach((p, idx) => {
      const color = p.color || colorForIndex(idx)
      const labelText = p.label || letterForIndex(idx)
      const icon = p.iconUrl ? { url: p.iconUrl, scaledSize: new google.maps.Size(28, 28), anchor: new google.maps.Point(14, 28) } : buildMarkerIcon(color)

  if (hasAdvanced) {
        const el = document.createElement('div')
        el.style.width = '28px'
        el.style.height = '28px'
        el.style.borderRadius = '50%'
        el.style.background = color
        el.style.color = '#fff'
        el.style.display = 'flex'
        el.style.alignItems = 'center'
        el.style.justifyContent = 'center'
        el.style.fontWeight = '700'
        el.style.fontSize = '12px'
        el.textContent = labelText
  const marker = new google.maps.marker.AdvancedMarkerElement({ position: { lat: p.lat, lng: p.lng }, map, title: p.name || '', content: el })
        marker.addListener('gmp-click', () => { iw.setContent(infoHtml(p, idx)); iw.open({ map, anchor: marker }) })
        markers.push(marker)
        try { bounds.extend(marker.position) } catch {}
      } else {
        const marker = new google.maps.Marker({ position: { lat: p.lat, lng: p.lng }, map, title: p.name || '', icon, label: { text: labelText, color: '#ffffff', fontWeight: '700', fontSize: '12px' } })
        marker.addListener('click', () => { iw.setContent(infoHtml(p, idx)); iw.open({ map, anchor: marker }) })
        markers.push(marker)
        try { bounds.extend(marker.getPosition()) } catch {}
      }
    })
  } catch (e) {
    // マーカー生成でエラー（無効キーなど）の場合はフォールバック
    clearMap()
    return false
  }
  // AdvancedMarker はクラスタ対象外。通常マーカーのときだけ有効
  if (window.markerClusterer?.MarkerClusterer && markers.length && typeof markers[0].getPosition === 'function') {
    try { cluster = new window.markerClusterer.MarkerClusterer({ markers, map }) } catch {}
  }
  try {
    if (coords.length === 1) {
      map.setCenter({ lat: coords[0].lat, lng: coords[0].lng })
      map.setZoom(15)
    } else {
      map.fitBounds(bounds)
    }
  } catch {}
  return true
}

async function renderJsRoute() {
  if (!rootEl.value) return false
  const ri = props.routeInfo || {}
  const origin = ri.origin
  const destination = ri.destination
  if (!origin || !destination) return false
  // 初期化
  if (!map) {
    try {
      const options = { center: { lat: 35.68, lng: 139.77 }, zoom: 6, mapTypeControl: false }
      // ルート描画時も mapId があれば必ず付与
      if (MAP_ID.value) options.mapId = MAP_ID.value
      map = new google.maps.Map(rootEl.value, options)
    } catch (e) {
      return false
    }
  }
  clearMap()
  try {
    if (!directionsService) directionsService = new google.maps.DirectionsService()
    if (!directionsRenderer) directionsRenderer = new google.maps.DirectionsRenderer({ suppressMarkers: false, preserveViewport: false })
    directionsRenderer.setMap(map)
    const mode = (ri.mode || '').toLowerCase()
    const travelMode = ['driving','walking','bicycling','transit'].includes(mode) ? mode.toUpperCase() : 'DRIVING'
    const wps = Array.isArray(ri.waypoints) ? ri.waypoints.filter(Boolean).map(w => ({ location: w, stopover: true })) : undefined
    const req = { origin, destination, travelMode, waypoints: wps }
    await new Promise((resolve, reject) => {
      directionsService.route(req, (result, status) => {
        try {
          if (status === 'OK' && result) {
            directionsRenderer.setDirections(result)
            resolve()
          } else {
            reject(new Error(String(status)))
          }
        } catch (e) { reject(e) }
      })
    })
    return true
  } catch (e) {
    // Directions 失敗時はフォールバック
    try { directionsRenderer && directionsRenderer.setMap(null) } catch {}
    directionsRenderer = null
    return false
  }
}

async function updateMap() {
  // ルートがあれば: キーがあればJSで描画、無ければ埋め込み（q=dir）
  if (hasRoute.value) {
    if (mapsApiKey.value) {
      const ok = await ensureMapsJs()
      if (ok) {
        useJsMap.value = true
        iframeSrc.value = ''
        staticImgSrc.value = ''
        await nextTick()
        const success = await renderJsRoute()
        if (success) return
        // JS失敗時は埋め込みへ
        useJsMap.value = false
      }
    }
    // フォールバック: 埋め込み（キー不要）
    useJsMap.value = false
    buildRouteEmbed()
    return
  }
  const coordsCount = placesWithCoords.value.length
  // 座標が1件以上でもJSでマーカーを表示（クラスタは任意）
  if (coordsCount >= 1 && mapsApiKey.value) {
    const ok = await ensureMapsJs()
    if (ok) {
      // クラスタは背景で読み込み（失敗しても描画は続行）
      ensureClusterer()
      useJsMap.value = true
      iframeSrc.value = ''
      staticImgSrc.value = ''
      await nextTick()
      const success = renderJsMap()
      if (success) return
      // 失敗したらフォールバックへ
      useJsMap.value = false
      map = null
    }
  }
  // フォールバック（Google の埋め込みのみ使用）
  useJsMap.value = false
  staticImgSrc.value = ''
  buildPlaceEmbed()
}

function refresh() {
  if (useJsMap.value && map) {
    try {
      const bounds = new google.maps.LatLngBounds()
      for (const m of markers) try { bounds.extend(m.getPosition()) } catch {}
      map.fitBounds(bounds)
    } catch {}
  }
}

defineExpose({ refresh })

onMounted(async () => {
  await fetchMapsKey()
  updateMap()
})

watch(() => [props.routeInfo, props.places, mapsApiKey.value], () => { updateMap() }, { deep: true })

</script>

<template>
  <div class="wrap">
    <iframe v-if="!useJsMap && iframeSrc" class="map-iframe" :src="iframeSrc" style="border:0;" allowfullscreen="false" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
    <img v-else-if="!useJsMap && staticImgSrc" class="map-img" :src="staticImgSrc" alt="静的マップ" loading="lazy" />
    <div v-else ref="rootEl" class="map-div" aria-label="Google マップ"></div>
    <slot name="overlay"></slot>
  </div>
</template>

<style scoped>
.wrap { position: absolute; inset: 0; }
.map-iframe, .map-div, .map-img { width: 100%; height: 100%; }
.map-img { object-fit: cover; }
.attrib { position: absolute; right: 8px; bottom: 6px; background: rgba(255,255,255,0.8); border-radius: 4px; padding: 2px 6px; font-size: 11px; color: #374151; }
/* タップ領域拡大用ユーティリティ（利用側で slot に配置） */
.map-touch-btn { min-width:48px; min-height:48px; display:inline-flex; align-items:center; justify-content:center; padding:10px 14px; font-size:14px; font-weight:600; border-radius:14px; background: var(--color-text); color:#fff; border:none; box-shadow:0 4px 14px rgba(0,0,0,0.25); }
.map-touch-btn:active { transform: translateY(1px); }
</style>