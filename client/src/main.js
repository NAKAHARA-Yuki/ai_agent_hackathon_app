import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import VIcon from './components/v-icon.vue'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.component('v-icon', VIcon)

app.mount('#app')
