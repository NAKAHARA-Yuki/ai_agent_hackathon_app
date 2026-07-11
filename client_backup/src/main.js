// パッチ: `/api/` へのアクセスを、サブパスホスト環境（/izatabi/）に合わせて自動的に補正する
const originalFetch = window.fetch;
window.fetch = function (resource, options) {
  let url = typeof resource === 'string' ? resource : resource.url;
  
  if (url.startsWith('/api/')) {
    const baseUrl = import.meta.env.BASE_URL || '/';
    if (baseUrl !== '/') {
      const prefix = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
      url = prefix + url;
    }
  }
  
  if (typeof resource === 'string') {
    return originalFetch(url, options);
  } else {
    try {
      const newRequest = new Request(url, resource);
      return originalFetch(newRequest, options);
    } catch (e) {
      return originalFetch(url, options);
    }
  }
};

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
