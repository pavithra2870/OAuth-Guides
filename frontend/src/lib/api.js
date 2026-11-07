// Thin API client: base URL, JSON requests with a hard timeout, and wake-up retries.

export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, { status, timedOut } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.timedOut = Boolean(timedOut)
  }
}

export async function getJSON(path, { timeoutMs = 20000, signal } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort('timeout'), timeoutMs)
  signal?.addEventListener('abort', () => controller.abort(signal.reason))
  try {
    const res = await fetch(`${API_URL}${path}`, { signal: controller.signal })
    if (!res.ok) throw new ApiError(`Request failed (${res.status})`, { status: res.status })
    return await res.json()
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (controller.signal.aborted && controller.signal.reason === 'timeout') {
      throw new ApiError('The server took too long to respond.', { timedOut: true })
    }
    if (err.name === 'AbortError') throw err
    throw new ApiError('Could not reach the server.')
  } finally {
    clearTimeout(timer)
  }
}

// Free hosting can put the backend to sleep. Ping /health until it answers.
export async function wakeServer({ attempts = 6, signal } = {}) {
  for (let i = 0; i < attempts; i++) {
    try {
      await getJSON('/health', { timeoutMs: 15000, signal })
      return true
    } catch (err) {
      if (err.name === 'AbortError') throw err
    }
  }
  return false
}
