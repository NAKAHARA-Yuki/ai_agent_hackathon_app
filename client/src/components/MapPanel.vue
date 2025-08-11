<script setup>
import { onMounted, ref, watch } from 'vue'

const props = defineProps({
  places: { type: Array, default: () => [] }
})

let map
const mapEl = ref(null)
const markers = []

function clearMarkers() {
  while (markers.length) {
    const m = markers.pop()
    m.setMap(null)
  }
}

function addMarkers(list) {
  for (const p of list) {
    const marker = new window.google.maps.Marker({ position: { lat: p.lat, lng: p.lng }, map, title: p.name })
    const info = new window.google.maps.InfoWindow({ content: `<strong>${p.name}</strong><br/>${p.note || ''}` })
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
  return new Promise((resolve, reject) => {
    if (window.google?.maps) return resolve()
    // 既に読み込み中なら待つ
    const cbName = '__onGoogleMapsLoaded'
    if (window[cbName]) {
      const iv = setInterval(() => { if (window.google?.maps) { clearInterval(iv); resolve() } }, 50)
      return
    }
    // スクリプトを挿入
    const key = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
    if (!key) {
      console.warn('VITE_GOOGLE_MAPS_API_KEY is not set.')
      return resolve() // キーなしでもクラッシュは避ける
    }
    window[cbName] = () => {}
    const s = document.createElement('script')
    s.src = `https://maps.googleapis.com/maps/api/js?key=${key}`
    s.async = true
    s.defer = true
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('Google Maps failed to load'))
    document.head.appendChild(s)
  })
}

onMounted(async () => {
  try {
    await ensureMapsReady()
    map = new window.google.maps.Map(mapEl.value, { center: { lat: 35.6804, lng: 139.7690 }, zoom: 5 })
    clearMarkers()
    addMarkers(props.places)
    fitBounds(props.places)
  } catch (e) {
    console.error(e)
  }
})

watch(() => props.places, (list) => {
  if (!map) return
  clearMarkers()
  addMarkers(list)
  fitBounds(list)
}, { deep: true })
</script>

<template>
  <div ref="mapEl" class="map"></div>
</template>

<style scoped>
.map { position:absolute; inset:0; }
</style>
