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
