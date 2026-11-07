// Minimal Server-Sent Events client built on fetch (supports abort, and POST later).
//
//   const stop = streamSSE('/stream-test', { onEvent: (name, data) => {...}, onError, onClose })
//   stop()  // cancel
//
// Fails with a timeout if nothing (not even a heartbeat) arrives for `idleMs`.

import { API_URL } from './api.js'

export function streamSSE(path, { onEvent, onError, onClose, idleMs = 30000, init = {} } = {}) {
  const controller = new AbortController()
  let idleTimer
  let finished = false

  const finish = (err) => {
    if (finished) return
    finished = true
    clearTimeout(idleTimer)
    if (err) onError?.(err)
    else onClose?.()
  }

  const armIdle = () => {
    clearTimeout(idleTimer)
    idleTimer = setTimeout(() => {
      controller.abort('idle')
    }, idleMs)
  }

  ;(async () => {
    try {
      armIdle()
      const res = await fetch(`${API_URL}${path}`, {
        ...init,
        headers: { Accept: 'text/event-stream', ...init.headers },
        signal: controller.signal,
      })
      if (!res.ok || !res.body) throw new Error(`Stream failed (${res.status})`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        armIdle()
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split(/\r?\n\r?\n/)
        buffer = frames.pop()
        for (const frame of frames) {
          let event = 'message'
          const data = []
          for (const line of frame.split(/\r?\n/)) {
            if (line.startsWith(':')) continue // heartbeat comment
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
          }
          if (!data.length) continue
          let payload = data.join('\n')
          try {
            payload = JSON.parse(payload)
          } catch {
            /* keep raw text */
          }
          onEvent?.(event, payload)
        }
      }
      finish()
    } catch (err) {
      if (controller.signal.aborted && controller.signal.reason !== 'idle') return finish() // cancelled by caller
      const message = controller.signal.reason === 'idle' ? 'The connection went quiet.' : err.message
      finish(new Error(message))
    }
  })()

  return () => {
    clearTimeout(idleTimer)
    finished = true
    controller.abort('cancel')
  }
}
