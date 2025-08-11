<script setup>
import { onMounted, ref, watch, onBeforeUnmount } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// Fix default icon paths for Vite
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const props = defineProps({
  places: { type: Array, default: () => [] }
})

const wrapEl = ref(null)
let map
let markers = []
let ro

function initMap() {
  if (map) return
  const el = wrapEl.value
  if (!el) return
  map = L.map(el, { zoomControl: true })
  // OSM tile layer
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map)
  // 初期は日本全体
  const japanBounds = L.latLngBounds([24.0, 123.0], [46.0, 146.0])
  map.fitBounds(japanBounds)
}

function clearMarkers() {
  markers.forEach(m => m.remove())
  markers = []
}

function renderMarkers() {
  if (!map) return
  const pts = (props.places || []).filter(p => typeof p?.lat === 'number' && typeof p?.lng === 'number').slice(0, 200)
  clearMarkers()
  if (pts.length === 0) {
    // 日本全体
    const japanBounds = L.latLngBounds([24.0, 123.0], [46.0, 146.0])
    map.fitBounds(japanBounds)
    return
  }
  const group = []
  for (const p of pts) {
    const marker = L.marker([p.lat, p.lng])
    const html = `<strong>${p.name ?? ''}</strong>${p.note ? '<br/>' + p.note : ''}`
    marker.bindPopup(html)
    marker.addTo(map)
    markers.push(marker)
    group.push([p.lat, p.lng])
  }
  const bounds = L.latLngBounds(group)
  map.fitBounds(bounds, { padding: [12, 12] })
}

onMounted(() => {
  initMap()
  renderMarkers()
  // Resize handling
  const el = wrapEl.value
  if (el) {
    ro = new ResizeObserver(() => {
      if (map) map.invalidateSize()
    })
    ro.observe(el)
  }
})

onBeforeUnmount(() => {
  if (ro && wrapEl.value) ro.unobserve(wrapEl.value)
  if (map) {
    map.remove()
    map = null
  }
})

watch(() => props.places, () => {
  renderMarkers()
}, { deep: true })
</script>

<template>
  <div ref="wrapEl" class="wrap"></div>
</template>

<style scoped>
.wrap { position:absolute; inset:0; }
</style>
