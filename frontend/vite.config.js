import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

function resolveBackendProxyTarget(env) {
  const rawUrl = env.VITE_BACKEND_URL || 'http://creditwatch'
  const rawPort = env.VITE_BACKEND_PORT || '8010'

  let normalized = String(rawUrl).trim()
  if (!/^https?:\/\//i.test(normalized)) {
    normalized = `http://${normalized}`
  }

  try {
    const url = new URL(normalized)
    if (rawPort) {
      url.port = String(rawPort)
    }
    return url.origin
  } catch (error) {
    console.warn(
      'Invalid VITE_BACKEND_URL for Vite proxy target. Falling back to http://creditwatch:8010.'
    )
    return 'http://creditwatch:8010'
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = resolveBackendProxyTarget(env)
  const devPort = Number(env.VITE_DEV_SERVER_PORT || 5173)

  return {
    plugins: [
      vue(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['icons/icon-192x192.png', 'icons/icon-512x512.png'],
        manifest: {
          name: 'CreditWatch',
          short_name: 'CreditWatch',
          description: 'Monitor credit card benefits and annual fee value in one dashboard.',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          background_color: '#f5f7fb',
          theme_color: '#0b3d91',
          icons: [
            {
              src: '/icons/icon-192x192.png',
              sizes: '192x192',
              type: 'image/png'
            },
            {
              src: '/icons/icon-512x512.png',
              sizes: '512x512',
              type: 'image/png'
            },
            {
              src: '/icons/icon-512x512-maskable.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable any'
            }
          ]
        }
      })
    ],
    server: {
      host: '0.0.0.0',
      port: Number.isNaN(devPort) ? 5173 : devPort,
      proxy: {
        '/api': {
          target,
          changeOrigin: true
        }
      }
    }
  }
})
