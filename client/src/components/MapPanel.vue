<script setup>
import { computed } from 'vue'

const props = defineProps({
  places: { type: Array, default: () => [] },
  routeInfo: { type: Object, default: () => null }
})

const mapSrc = computed(() => {
  const base = 'https://www.google.com/maps?output=embed'
  // ルート情報があれば優先
  if (props.routeInfo && props.routeInfo.origin && props.routeInfo.destination) {
    const origin = encodeURIComponent(props.routeInfo.origin)
    const destination = encodeURIComponent(props.routeInfo.destination)
    return `${base}&saddr=${origin}&daddr=${destination}`
  }
  // 場所情報があれば表示
  if (props.places && props.places.length > 0) {
    const place = props.places[0]
    const query = encodeURIComponent(place.name)
    if (place.lat && place.lng) {
      return `${base}&ll=${place.lat},${place.lng}&q=${query}&z=15`
    }
    return `${base}&q=${query}`
  }
  // デフォルトは日本全体
  return `${base}&ll=35.68,139.77&z=5`
})

function refresh() {
  // iframeなので特に何もしないが、インターフェースとして残す
}

defineExpose({ refresh })

</script>

<template>
  <div class="wrap">
    <iframe
      class="map-iframe"
      :src="mapSrc"
      style="border:0;"
      allowfullscreen="false"
      loading="lazy"
      referrerpolicy="no-referrer-when-downgrade">
    </iframe>
  </div>
</template>

<style scoped>
.wrap { position: absolute; inset: 0; }
.map-iframe { width: 100%; height: 100%; }
</style>