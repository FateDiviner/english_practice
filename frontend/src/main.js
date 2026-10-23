import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { pinia } from './stores'
import './styles/tokens.css'
import './styles/base.css'
import './styles/controls.css'
import './styles/data.css'

createApp(App).use(pinia).use(router).mount('#app')
