import './index.css'
import { createApp, watch } from 'vue'
import router from './router'
import App from './App.vue'
import { createPinia } from 'pinia'
import dayjs from '@/utils/dayjs'
import { createDialog } from '@/utils/dialogs'
import translationPlugin from './translation'
import { usersStore } from './stores/user'
import { initSocket } from './socket'
import { FrappeUI, setConfig, frappeRequest, pageMetaPlugin } from 'frappe-ui'
import { telemetryPlugin } from 'frappe-ui/frappe'

let pinia = createPinia()
let app = createApp(App)
setConfig('resourceFetcher', frappeRequest)

app.use(FrappeUI)
app.use(pinia)
app.use(router)
app.use(translationPlugin)
app.use(pageMetaPlugin)
app.provide('$dayjs', dayjs)
app.provide('$socket', initSocket())
app.mount('#app')

const { userResource, allUsers } = usersStore()
app.provide('$user', userResource)
app.provide('$allUsers', allUsers)

watch(userResource, () => {
	if (userResource.data) {
		app.use(telemetryPlugin, { app_name: 'lms' })
	}
})

app.config.globalProperties.$user = userResource
app.config.globalProperties.$dialog = createDialog

if ('serviceWorker' in navigator) {
	const hadController = !!navigator.serviceWorker.controller
	let promptShown = false
	navigator.serviceWorker.addEventListener('controllerchange', () => {
		if (!hadController || promptShown) return
		promptShown = true
		showUpdateBanner()
	})
}

function showUpdateBanner() {
	const banner = document.createElement('div')
	banner.style.cssText = [
		'position:fixed', 'bottom:20px', 'left:50%',
		'transform:translateX(-50%)', 'background:#171717', 'color:#fff',
		'padding:12px 16px', 'border-radius:8px',
		'box-shadow:0 4px 12px rgba(0,0,0,0.15)', 'z-index:9999',
		'display:flex', 'align-items:center', 'gap:12px',
		'font:500 14px system-ui,-apple-system,sans-serif',
	].join(';')
	banner.innerHTML =
		'<span>A new version is available.</span>' +
		'<button data-act="reload" style="background:#fff;color:#171717;border:0;padding:6px 14px;border-radius:6px;font-weight:600;font-family:inherit;cursor:pointer">Reload</button>' +
		'<button data-act="dismiss" aria-label="Dismiss" style="background:transparent;color:#999;border:0;padding:4px;font:18px/1 inherit;cursor:pointer">×</button>'
	banner.querySelector('[data-act="reload"]').addEventListener('click', () => window.location.reload())
	banner.querySelector('[data-act="dismiss"]').addEventListener('click', () => banner.remove())
	document.body.appendChild(banner)
}
