<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'

const props = defineProps({
  places: { type: Array, default: () => [] },
  routeInfo: { type: Object, default: () => null }
})

const baseEmbed = 'https://www.google.com/maps?output=embed'
const iframeSrc = ref('')
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
}

function buildPlaceEmbed() {
  const first = (props.places || [])[0]
  if (!first) {
    iframeSrc.value = `${baseEmbed}&ll=35.68,139.77&z=5`
    return
  }
  const q = encodeURIComponent(first.name || `${first.lat},${first.lng}`)
  if (first.lat && first.lng) {
    iframeSrc.value = `${baseEmbed}&z=15&ll=${first.lat},${first.lng}&q=${q}`
  } else {
    iframeSrc.value = `${baseEmbed}&q=${q}`
  }
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
  for (const p of coords) {
    const marker = new google.maps.Marker({ position: { lat: p.lat, lng: p.lng }, map, title: p.name || '' })
    marker.addListener('click', () => {
      const name = p.name ? `<strong>${p.name}</strong>` : ''
      const note = p.note ? `<div style="color:#6b7280; margin-top:4px;">${p.note}</div>` : ''
      iw.setContent(`<div>${name}${note}</div>`)
      iw.open({ map, anchor: marker })
    })
    markers.push(marker)
    try { bounds.extend(marker.getPosition()) } catch {}
  }
  if (window.markerClusterer?.MarkerClusterer) {
    cluster = new window.markerClusterer.MarkerClusterer({ markers, map })
  }
  try { map.fitBounds(bounds) } catch {}
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
      await nextTick()
      renderJsMap()
      return
    }
  }
  // フォールバック: 埋め込み
  useJsMap.value = false
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
    <iframe v-if="!useJsMap" class="map-iframe" :src="iframeSrc" style="border:0;" allowfullscreen="false" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
    <div v-else ref="rootEl" class="map-div" aria-label="Google マップ"></div>
  </div>
</template>

<style scoped>
.wrap { position: absolute; inset: 0; }
.map-iframe, .map-div { width: 100%; height: 100%; }
</style>