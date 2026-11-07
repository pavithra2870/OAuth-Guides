import { useCallback, useEffect, useState } from 'react'

export function useDocumentTitle(title) {
  useEffect(() => {
    const previous = document.title
    document.title = title ? `${title} · OAuth Guides` : 'OAuth Guides'
    return () => {
      document.title = previous
    }
  }, [title])
}

/** Per-guide checklist, remembered in this browser only. Works fine if storage is blocked. */
export function useChecklist(slug) {
  const key = `oauth-guides:checks:${slug}`
  const [done, setDone] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(key) || '[]'))
    } catch {
      return new Set()
    }
  })

  const toggle = useCallback(
    (id) => {
      setDone((prev) => {
        const next = new Set(prev)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        try {
          localStorage.setItem(key, JSON.stringify([...next]))
        } catch {
          /* storage unavailable: keep in memory */
        }
        return next
      })
    },
    [key],
  )

  return [done, toggle]
}

/** Which section id is currently in view (for the sticky contents list). */
export function useScrollSpy(ids) {
  const [active, setActive] = useState(ids[0])
  const joined = ids.join('|')

  useEffect(() => {
    const elements = joined
      .split('|')
      .map((id) => document.getElementById(id))
      .filter(Boolean)
    if (!elements.length || !('IntersectionObserver' in window)) return undefined
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) setActive(visible[0].target.id)
      },
      { rootMargin: '-20% 0px -65% 0px' },
    )
    elements.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [joined])

  return active
}

export function useCopy() {
  const [copied, setCopied] = useState(null)
  const copy = useCallback(async (text, tag = 'text') => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(tag)
      setTimeout(() => setCopied((c) => (c === tag ? null : c)), 1800)
      return true
    } catch {
      return false
    }
  }, [])
  return [copied, copy]
}
