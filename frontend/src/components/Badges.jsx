import { useState } from 'react'
import { DIFFICULTY, EVIDENCE, hostOf } from '../lib/format.js'

export function DifficultyBadge({ level, size = 'md' }) {
  const meta = DIFFICULTY[level] ?? DIFFICULTY.medium
  return (
    <span className={`badge badge-${meta.tone} badge-${size}`}>
      <span className="badge-dot" />
      {meta.label}
    </span>
  )
}

export function Favicon({ domain, name, size = 40 }) {
  const [failed, setFailed] = useState(false)
  const style = { width: size, height: size, borderRadius: Math.round(size / 4) }
  if (!domain || failed) {
    return (
      <span className="favicon favicon-fallback" style={{ ...style, fontSize: size * 0.45 }} aria-hidden="true">
        {(name || '?').charAt(0).toUpperCase()}
      </span>
    )
  }
  return (
    <img
      className="favicon"
      style={style}
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=64`}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}

/**
 * Shows how well a claim is backed. Expands to reveal the exact quote and its source,
 * or says plainly that no source states it.
 */
export function EvidenceBadge({ evidence, sources = [] }) {
  const [open, setOpen] = useState(false)
  if (!evidence) return null
  const meta = EVIDENCE[evidence.level] ?? EVIDENCE.inferred
  const cited = evidence.source_ids.map((id) => sources.find((s) => s.id === id)).filter(Boolean)

  return (
    <span className="evidence">
      <button
        type="button"
        className={`ev ev-${evidence.level}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        title={meta.hint}
      >
        <span className="ev-dot" />
        {meta.label}
      </button>
      {open && (
        <span className="ev-panel rise">
          {evidence.quote ? <q>{evidence.quote}</q> : <span className="muted">{meta.hint}</span>}
          {cited.map((s) => (
            <a key={s.id} href={s.url} target="_blank" rel="noreferrer noopener" className="ev-source">
              {s.id} · {hostOf(s.url)} ↗
            </a>
          ))}
        </span>
      )}
    </span>
  )
}
