import axios from 'axios'

function resolveBackendBaseURL() {
  const rawUrl = import.meta.env.VITE_BACKEND_URL
  const rawPort = import.meta.env.VITE_BACKEND_PORT

  if (!rawUrl) {
    return ''
  }

  let normalized = String(rawUrl).trim()
  if (!normalized) {
    return ''
  }

  if (!/^https?:\/\//i.test(normalized)) {
    normalized = `http://${normalized}`
  }

  try {
    const url = new URL(normalized)
    if (rawPort) {
      url.port = String(rawPort)
    }
    // Mixed-content guard: an http:// API base on an https:// page gets
    // blocked by the browser, so fall back to same-origin requests (nginx
    // and the Vite dev server both proxy /api to the backend).
    if (
      typeof window !== 'undefined' &&
      window.location.protocol === 'https:' &&
      url.protocol === 'http:'
    ) {
      return ''
    }
    return url.origin
  } catch (error) {
    console.warn(
      'Invalid VITE_BACKEND_URL provided. Falling back to same-origin API requests.'
    )
    return ''
  }
}

const baseURL = resolveBackendBaseURL()

const apiClient = axios.create({
  baseURL: baseURL || undefined
})

export default apiClient
