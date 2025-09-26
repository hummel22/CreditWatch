import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

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
    plugins: [vue()],
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
