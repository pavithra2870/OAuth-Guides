import { useCallback, useEffect, useMemo, useState } from 'react'
import { getJSON, wakeServer } from '../lib/api.js'
import { LibraryContext } from './useLibrary.js'

export function LibraryProvider({ children }) {
  const [state, setState] = useState({ phase: 'waking', guides: [], error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller

    async function load() {
      try {
        if (!(await wakeServer({ signal }))) throw new Error('The server is taking a while to wake up.')
        setState((s) => ({ ...s, phase: 'loading' }))
        const { guides } = await getJSON('/api/guides', { signal })
        setState({ phase: 'ready', guides, error: null })
      } catch (err) {
        if (err.name === 'AbortError') return
        setState({ phase: 'error', guides: [], error: err.message })
      }
    }

    load()
    return () => controller.abort()
  }, [attempt])

  const reload = useCallback(() => {
    setState({ phase: 'waking', guides: [], error: null })
    setAttempt((n) => n + 1)
  }, [])

  // A freshly generated guide joins the library without a refetch.
  const add = useCallback((summary) => {
    setState((s) => ({ ...s, guides: [...s.guides.filter((g) => g.slug !== summary.slug), summary] }))
  }, [])

  const value = useMemo(() => ({ ...state, reload, add }), [state, reload, add])
  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>
}
