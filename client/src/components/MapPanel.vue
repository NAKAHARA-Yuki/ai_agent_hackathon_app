<script setup>
import { onMounted, ref, watch } from 'vue'

const props = defineProps({
  places: { type: Array, default: () => [] }
})

let map
const mapEl = ref(null)
const markers = []
const status = ref('loading') // 'loading' | 'ready' | 'no-key' | 'load-error'

function clearMarkers() {
  while (markers.length) {
    const m = markers.pop()
    m.setMap(null)
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

function fitBounds(list) {
  if (!list.length) return
  const bounds = new window.google.maps.LatLngBounds()
  list.forEach(p => bounds.extend({ lat: p.lat, lng: p.lng }))
  map.fitBounds(bounds)
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
    if (pts.length > 0) {
      fitBounds(pts)
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

watch(() => props.places, (list) => {
  if (!map) return
  clearMarkers()
  const pts = (list || []).filter(p => typeof p?.lat === 'number' && typeof p?.lng === 'number')
  addMarkers(pts)
  if (pts.length > 0) {
    fitBounds(pts)
  } else {
    const japanBounds = new window.google.maps.LatLngBounds(
      { lat: 24.0, lng: 123.0 },
      { lat: 46.0, lng: 146.0 }
    )
    map.fitBounds(japanBounds)
  }
}, { deep: true })
</script>

<template>
  <div class="wrap">
    <div v-if="status==='ready'" ref="mapEl" class="map"></div>
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
.placeholder { position: absolute; inset: 0; display: grid; place-items: center; background: #f8fafc; color: #334155; }
.placeholder .msg { padding: 8px 12px; background: #e2e8f0; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.06); }
</style>
