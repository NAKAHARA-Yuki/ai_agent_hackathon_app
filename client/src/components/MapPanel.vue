<script setup>
import { onMounted, ref, watch } from 'vue'

const props = defineProps({
  places: { type: Array, default: () => [] },
  // Google Routes APIのレスポンスオブジェクト、または従来の簡易配列([{from,to,mode,detail}])
  routeInfo: { type: [Array, Object], default: () => [] }
})

let map
const mapEl = ref(null)
const markers = []
const polylines = []
const status = ref('loading') // 'loading' | 'ready' | 'no-key' | 'load-error'
const showAttribution = ref(false)

// Google Encoded Polyline Algorithm の簡易デコーダ
function decodePolyline(str) {
  try {
    let index = 0, lat = 0, lng = 0, coordinates = []
    while (index < str.length) {
      let b, shift = 0, result = 0
      do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5 } while (b >= 0x20)
      const dlat = (result & 1) ? ~(result >> 1) : (result >> 1)
      lat += dlat

      shift = 0; result = 0
      do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5 } while (b >= 0x20)
      const dlng = (result & 1) ? ~(result >> 1) : (result >> 1)
      lng += dlng

      coordinates.push({ lat: lat / 1e5, lng: lng / 1e5 })
    }
    return coordinates
  } catch (e) {
    return []
  }
}

function clearMarkers() {
  while (markers.length) {
    const m = markers.pop()
    m.setMap(null)
  }
}

function clearPolylines() {
  while (polylines.length) {
    const pl = polylines.pop()
    pl.setMap(null)
  }
}

function addMarkers(list) {
  for (const p of list) {
    const marker = new window.google.maps.Marker({ position: { lat: p.lat, lng: p.lng }, map, title: p.name })
    const info = new window.google.maps.InfoWindow({ content: `<strong>${p.name ?? ''}</strong>${p.note ? '<br/>' + p.note : ''}` })
    marker.addListener('click', () => info.open({ anchor: marker, map }))
    markers.push(marker)
  }
}

function fitBounds(pointsOnlyPlaces = [], routePaths = []) {
  const hasPlaces = Array.isArray(pointsOnlyPlaces) && pointsOnlyPlaces.length
  const hasRoutes = Array.isArray(routePaths) && routePaths.length
  if (!hasPlaces && !hasRoutes) return
  const bounds = new window.google.maps.LatLngBounds()
  if (hasPlaces) {
    pointsOnlyPlaces.forEach(p => bounds.extend({ lat: p.lat, lng: p.lng }))
  }
  if (hasRoutes) {
    for (const path of routePaths) {
      for (const pt of path) bounds.extend(pt)
    }
  }
  map.fitBounds(bounds)
}

// Google Routes API 形式かどうか判定
function isGoogleRoutesFormat(data) {
  if (!data) return false
  if (Array.isArray(data)) {
    return data.length > 0 && typeof data[0] === 'object' && (data[0]?.polyline || data[0]?.legs || data[0]?.routeLabels || data[0]?.viewport)
  }
  if (typeof data === 'object' && Array.isArray(data.routes)) return true
  return false
}

// Google Routes APIレスポンスからpaths配列(LatLng[])を抽出
function extractPathsFromGoogleRoutes(data) {
  const routes = Array.isArray(data) ? data : (Array.isArray(data?.routes) ? data.routes : [])
  const paths = []
  for (const route of routes) {
    // ルート全体のポリライン
    const enc = route?.polyline?.encodedPolyline
    if (typeof enc === 'string' && enc) {
      const p = decodePolyline(enc)
      if (p?.length) paths.push(p)
      continue
    }
    // legs 単位
    if (Array.isArray(route?.legs)) {
      for (const leg of route.legs) {
        const legEnc = leg?.polyline?.encodedPolyline
        if (typeof legEnc === 'string' && legEnc) {
          const p = decodePolyline(legEnc)
          if (p?.length) paths.push(p)
          continue
        }
        if (Array.isArray(leg?.steps)) {
          for (const st of leg.steps) {
            const stEnc = st?.polyline?.encodedPolyline
            if (typeof stEnc === 'string' && stEnc) {
              const p = decodePolyline(stEnc)
              if (p?.length) paths.push(p)
            }
          }
        }
      }
    }
  }
  return paths
}

function drawRoutes(places, routes) {
  // Google Routes API形式のとき
  if (isGoogleRoutesFormat(routes)) {
    const routePaths = extractPathsFromGoogleRoutes(routes)
    const defaultColors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2']
    let colorIdx = 0
    for (const path of routePaths) {
      const strokeColor = defaultColors[colorIdx++ % defaultColors.length]
      const pl = new window.google.maps.Polyline({
        path,
        geodesic: true,
        strokeColor,
        strokeOpacity: 0.9,
        strokeWeight: 5,
        map
      })
      polylines.push(pl)
    }
    return { paths: routePaths }
  }

  // 従来の簡易セグメント形式
  if (!Array.isArray(routes) || !routes.length) return { paths: [] }
  // 索引用: 名前→座標
  const index = new Map()
  for (const p of places) {
    if (p?.name && typeof p.lat === 'number' && typeof p.lng === 'number') {
      index.set(p.name, { lat: p.lat, lng: p.lng })
    }
  }
  const modeColors = {
    WALKING: '#16a34a', walking: '#16a34a', 徒歩: '#16a34a',
    DRIVING: '#2563eb', driving: '#2563eb', 車: '#2563eb',
    TRANSIT: '#9333ea', transit: '#9333ea', 電車: '#9333ea', バス: '#9333ea',
    BICYCLING: '#ea580c', bicycling: '#ea580c', 自転車: '#ea580c'
  }
  const defaultColors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2']
  let colorIdx = 0
  const drawnPaths = []

  for (const seg of routes) {
    if (!seg) continue
    let path = []
    // 1) Google Directions の encoded polyline
    if (typeof seg.polyline === 'string' && seg.polyline.length > 0) {
      path = decodePolyline(seg.polyline)
    }
    // 2) steps に polyline がある場合
    if ((!path || path.length === 0) && Array.isArray(seg.steps)) {
      for (const st of seg.steps) {
        if (typeof st?.polyline === 'string' && st.polyline) {
          const pts = decodePolyline(st.polyline)
          if (pts.length) path.push(...pts)
        } else if (Array.isArray(st?.path)) {
          for (const pt of st.path) {
            if (Array.isArray(pt) && pt.length >= 2) path.push({ lat: +pt[0], lng: +pt[1] })
            else if (pt && typeof pt.lat === 'number' && typeof pt.lng === 'number') path.push({ lat: pt.lat, lng: pt.lng })
          }
        }
      }
    }
    // 3) 直接 path 指定
    if ((!path || path.length === 0) && Array.isArray(seg.path)) {
      for (const pt of seg.path) {
        if (Array.isArray(pt) && pt.length >= 2) path.push({ lat: +pt[0], lng: +pt[1] })
        else if (pt && typeof pt.lat === 'number' && typeof pt.lng === 'number') path.push({ lat: pt.lat, lng: pt.lng })
      }
    }
    // 4) from/to 名称のみの場合は直線で結ぶ
    if ((!path || path.length < 2) && (seg.from || seg.to)) {
      const a = index.get(seg.from)
      const b = index.get(seg.to)
      if (a && b) path = [a, b]
    }
    // 5) from/to 座標が直接ある場合
    if ((!path || path.length < 2) && seg.from_coords && seg.to_coords) {
      const a = seg.from_coords
      const b = seg.to_coords
      if (a && b && typeof a.lat === 'number' && typeof a.lng === 'number' && typeof b.lat === 'number' && typeof b.lng === 'number') {
        path = [ { lat: a.lat, lng: a.lng }, { lat: b.lat, lng: b.lng } ]
      }
    }

    if (!path || path.length < 2) continue

    // 色決定
    const mode = seg.mode || seg.travel_mode || seg.transport
    const strokeColor = (mode && modeColors[mode]) || defaultColors[colorIdx++ % defaultColors.length]

    const pl = new window.google.maps.Polyline({
      path,
      geodesic: true,
      strokeColor,
      strokeOpacity: 0.9,
      strokeWeight: 4,
      map
    })
    polylines.push(pl)
    drawnPaths.push(path)
  }

  return { paths: drawnPaths }
}

function ensureMapsReady() {
  return new Promise(async (resolve) => {
    if (window.google?.maps) {
      status.value = 'ready'
      return resolve(true)
    }
    // 既に読み込み中なら待つ
    const cbName = '__onGoogleMapsLoaded'
    if (window[cbName]) {
      const iv = setInterval(() => {
        if (window.google?.maps) {
          clearInterval(iv)
          status.value = 'ready'
          resolve(true)
        }
      }, 50)
      return
    }
    // サーバーからキー取得
    let key = ''
    try {
      const r = await fetch('/api/maps-key')
      if (r.ok) {
        const j = await r.json()
        key = j.key || ''
      }
    } catch (_) {}
    if (!key) {
      status.value = 'no-key'
      return resolve(false)
    }
    window[cbName] = () => {}
    const s = document.createElement('script')
    s.src = `https://maps.googleapis.com/maps/api/js?key=${key}`
    s.async = true
    s.defer = true
    s.onload = () => { status.value = 'ready'; resolve(true) }
    s.onerror = () => { status.value = 'load-error'; resolve(false) }
    document.head.appendChild(s)
  })
}

onMounted(async () => {
  const ok = await ensureMapsReady()
  if (!ok || !window.google?.maps) return
  try {
    map = new window.google.maps.Map(mapEl.value, { center: { lat: 35.6804, lng: 139.7690 }, zoom: 5 })
    clearMarkers()
    const pts = (props.places || []).filter(p => typeof p?.lat === 'number' && typeof p?.lng === 'number')
    addMarkers(pts)
    clearPolylines()
  const { paths } = drawRoutes(pts, props.routeInfo)
  showAttribution.value = isGoogleRoutesFormat(props.routeInfo) && (paths?.length > 0)
    if (pts.length > 0 || (paths && paths.length)) {
      fitBounds(pts, paths)
    } else {
      const japanBounds = new window.google.maps.LatLngBounds(
        { lat: 24.0, lng: 123.0 },
        { lat: 46.0, lng: 146.0 }
      )
      map.fitBounds(japanBounds)
    }
  } catch (e) {
    console.error(e)
  }
})

function refresh() {
  if (!map) return
  clearMarkers()
  const pts = (props.places || []).filter(p => typeof p?.lat === 'number' && typeof p?.lng === 'number')
  addMarkers(pts)
  clearPolylines()
  const { paths } = drawRoutes(pts, props.routeInfo)
  showAttribution.value = isGoogleRoutesFormat(props.routeInfo) && (paths?.length > 0)
  if (pts.length > 0 || (paths && paths.length)) {
    fitBounds(pts, paths)
  } else {
    const japanBounds = new window.google.maps.LatLngBounds(
      { lat: 24.0, lng: 123.0 },
      { lat: 46.0, lng: 146.0 }
    )
    map.fitBounds(japanBounds)
  }
}

watch(() => props.places, () => refresh(), { deep: true })
watch(() => props.routeInfo, () => refresh(), { deep: true })

// 親からの明示的なリフレッシュ呼び出し用（オーバーレイ開閉時など）
defineExpose({ refresh })
</script>

<template>
  <div class="wrap">
    <div v-if="status==='ready'" ref="mapEl" class="map">
      <div v-if="showAttribution" class="attribution">Powered by Google, ©{{ new Date().getFullYear() }} Google</div>
    </div>
    <div v-else class="placeholder">
      <div class="msg">
        <template v-if="status==='loading'">地図を読み込んでいます…</template>
        <template v-else-if="status==='no-key'">地図キーがサーバーに未設定です（server/.env を確認してください）。</template>
        <template v-else-if="status==='load-error'">地図の読み込みに失敗しました。リロードしてください。</template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wrap { position: absolute; inset: 0; }
.map { position:absolute; inset:0; }
.map .attribution { position: absolute; left: 8px; bottom: 8px; font-size: 12px; color: #334155; background: rgba(255,255,255,.8); padding: 2px 6px; border-radius: 4px; }
.placeholder { position: absolute; inset: 0; display: grid; place-items: center; background: #f8fafc; color: #334155; }
.placeholder .msg { padding: 8px 12px; background: #e2e8f0; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.06); }
</style>
