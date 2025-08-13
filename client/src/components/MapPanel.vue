<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'

const props = defineProps({
  places: { type: Array, default: () => [] },
  routeInfo: { type: Object, default: () => null }
})

const baseEmbed = 'https://www.google.com/maps?output=embed'
const iframeSrc = ref('')
const staticImgSrc = ref('')
const useJsMap = ref(false)
const mapsApiKey = ref('')
const rootEl = ref(null)
let map = null
let markers = []
let cluster = null

const hasRoute = computed(() => !!(props.routeInfo && props.routeInfo.origin && props.routeInfo.destination))
const placesWithCoords = computed(() => (props.places || []).filter(p => typeof p?.lat === 'number' && typeof p?.lng === 'number'))

async function fetchMapsKey() {
  try {
    const r = await fetch('/api/maps-key')
    if (r.ok) {
      const j = await r.json()
      mapsApiKey.value = j.key || ''
    }
  } catch {}
}

function buildRouteEmbed() {
  const origin = encodeURIComponent(props.routeInfo.origin)
  const destination = encodeURIComponent(props.routeInfo.destination)
  iframeSrc.value = `${baseEmbed}&saddr=${origin}&daddr=${destination}`
  staticImgSrc.value = ''
}

function buildPlaceEmbed() {
  const first = (props.places || [])[0]
  if (!first) {
    iframeSrc.value = `${baseEmbed}&ll=35.68,139.77&z=5`
    staticImgSrc.value = ''
    return
  }
  const q = encodeURIComponent(first.name || `${first.lat},${first.lng}`)
  if (first.lat && first.lng) {
    iframeSrc.value = `${baseEmbed}&z=15&ll=${first.lat},${first.lng}&q=${q}`
  } else {
    iframeSrc.value = `${baseEmbed}&q=${q}`
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
  const src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(mapsApiKey.value)}&v=weekly&language=ja`
  await injectScript(src)
  return !!window.google?.maps
}

async function ensureClusterer() {
  if (window.markerClusterer?.MarkerClusterer) return true
  await injectScript('https://unpkg.com/@googlemaps/markerclusterer/dist/index.min.js')
  return !!window.markerClusterer?.MarkerClusterer
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
        ${link ? `<a href="${link}" target="_blank" rel="noopener" style="color:#111827;text-decoration:none;">${name}</a>` : name}
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

function renderJsMap() {
  if (!rootEl.value) return
  const coords = placesWithCoords.value
  if (!coords.length) return
  if (!map) {
    map = new google.maps.Map(rootEl.value, { center: { lat: coords[0].lat, lng: coords[0].lng }, zoom: 12, mapTypeControl: false })
  }
  clearMap()
  const bounds = new google.maps.LatLngBounds()
  const iw = new google.maps.InfoWindow({ content: '' })
  coords.forEach((p, idx) => {
    const color = p.color || colorForIndex(idx)
    const labelText = p.label || letterForIndex(idx)
    const icon = p.iconUrl ? { url: p.iconUrl, scaledSize: new google.maps.Size(28, 28), anchor: new google.maps.Point(14, 28) } : buildMarkerIcon(color)
    const marker = new google.maps.Marker({
      position: { lat: p.lat, lng: p.lng },
      map,
      title: p.name || '',
      icon,
      label: { text: labelText, color: '#ffffff', fontWeight: '700', fontSize: '12px' }
    })
    marker.addListener('click', () => {
      iw.setContent(infoHtml(p, idx))
      iw.open({ map, anchor: marker })
    })
    markers.push(marker)
    try { bounds.extend(marker.getPosition()) } catch {}
  })
  if (window.markerClusterer?.MarkerClusterer) {
    cluster = new window.markerClusterer.MarkerClusterer({ markers, map })
  }
  try { map.fitBounds(bounds) } catch {}
}

// ---- Static Maps (APIレス) フォールバック（OSM） ----
function buildOsmStaticUrl(points) {
  // 例: https://staticmap.openstreetmap.de/staticmap.php?size=800x600&markers=lat,lng,lightblue1|lat,lng,red1
  const size = '800x600'
  const colorKeys = ['lightblue1','red1','yellow1','green1','purple1','blue1','orange1','black1']
  const markersParam = points.map((p, i) => `${p.lat},${p.lng},${colorKeys[i % colorKeys.length]}`).join('|')
  const params = new URLSearchParams()
  params.set('size', size)
  params.set('maptype', 'mapnik')
  params.set('markers', markersParam)
  return `https://staticmap.openstreetmap.de/staticmap.php?${params.toString()}`
}

async function updateMap() {
  // ルートがあれば埋め込み優先
  if (hasRoute.value) {
    useJsMap.value = false
    buildRouteEmbed()
    return
  }
  const coordsCount = placesWithCoords.value.length
  if (coordsCount >= 2 && mapsApiKey.value) {
    const ok = await ensureMapsJs()
    const ok2 = await ensureClusterer()
    if (ok && ok2) {
      useJsMap.value = true
      iframeSrc.value = ''
      staticImgSrc.value = ''
      await nextTick()
      renderJsMap()
      return
    }
  }
  // フォールバック
  useJsMap.value = false
  if (coordsCount >= 2) {
    // APIキーなしでも複数マーカー表示できる静的マップ（OSM）を使用
    iframeSrc.value = ''
    staticImgSrc.value = buildOsmStaticUrl(placesWithCoords.value)
  } else {
    // 単一地点/未指定は従来のGoogle埋め込み
    staticImgSrc.value = ''
    buildPlaceEmbed()
  }
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
  <div v-if="!useJsMap && staticImgSrc" class="attrib">© OpenStreetMap contributors</div>
  <div v-else ref="rootEl" class="map-div" aria-label="Google マップ"></div>
  </div>
</template>

<style scoped>
.wrap { position: absolute; inset: 0; }
.map-iframe, .map-div, .map-img { width: 100%; height: 100%; }
.map-img { object-fit: cover; }
.attrib { position: absolute; right: 8px; bottom: 6px; background: rgba(255,255,255,0.8); border-radius: 4px; padding: 2px 6px; font-size: 11px; color: #374151; }
</style>