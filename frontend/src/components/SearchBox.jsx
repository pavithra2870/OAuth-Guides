import { useId, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLibrary } from '../context/useLibrary.js'
import { findExact, matchGuides } from '../lib/library.js'
import { DifficultyBadge, Favicon } from './Badges.jsx'

/** One box for everything: pick a guide we have, or research a new app live. */
export default function SearchBox({ size = 'lg', autoFocus = false }) {
  const navigate = useNavigate()
  const { guides } = useLibrary()
  const listId = useId()
  const inputRef = useRef(null)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [cursor, setCursor] = useState(-1)
  const [hint, setHint] = useState('')

  const matches = useMemo(() => matchGuides(guides, query), [guides, query])
  const trimmed = query.trim()
  // Rows: matching guides, then (always) the option to research this exact input live.
  const rows = [...matches.map((g) => ({ type: 'guide', g })), ...(trimmed.length >= 2 ? [{ type: 'research' }] : [])]

  function go(row) {
    setOpen(false)
    if (row?.type === 'guide') return navigate(`/g/${row.g.slug}`)
    if (trimmed.length < 2) return setHint('Type at least 2 characters: an app name or website.')
    const exact = findExact(guides, trimmed)
    return navigate(exact ? `/g/${exact.slug}` : `/research?q=${encodeURIComponent(trimmed)}`)
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setCursor((c) => Math.min(c + 1, rows.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCursor((c) => Math.max(c - 1, -1))
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <form
      className={`search search-${size}`}
      role="search"
      onSubmit={(e) => {
        e.preventDefault()
        go(cursor >= 0 ? rows[cursor] : null)
      }}
    >
      <div className="search-field">
        <svg className="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          ref={inputRef}
          value={query}
          autoFocus={autoFocus}
          autoComplete="off"
          spellCheck="false"
          placeholder="Search an app or paste its website"
          aria-label="App name or website"
          role="combobox"
          aria-expanded={open && rows.length > 0}
          aria-controls={listId}
          aria-activedescendant={cursor >= 0 ? `${listId}-${cursor}` : undefined}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
            setCursor(-1)
            setHint('')
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
        />
        <button className="btn btn-solid" type="submit">
          Get the guide <span aria-hidden="true">→</span>
        </button>
      </div>

      {hint && <p className="search-hint">{hint}</p>}

      {open && rows.length > 0 && (
        <ul className="suggest" id={listId} role="listbox">
          {rows.map((row, i) => (
            <li
              key={row.type === 'guide' ? row.g.slug : 'research'}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={cursor === i}
              className={`suggest-row ${cursor === i ? 'is-cursor' : ''}`}
              onMouseDown={(e) => {
                e.preventDefault()
                go(row)
              }}
              onMouseEnter={() => setCursor(i)}
            >
              {row.type === 'guide' ? (
                <>
                  <Favicon domain={row.g.domain} name={row.g.app_name} size={28} />
                  <span className="suggest-name">{row.g.app_name}</span>
                  <DifficultyBadge level={row.g.difficulty} size="sm" />
                  <span className="suggest-meta">Ready</span>
                </>
              ) : (
                <>
                  <span className="suggest-live">AI</span>
                  <span className="suggest-name">
                    Research “{trimmed}” live
                  </span>
                  <span className="suggest-meta">~30 sec</span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </form>
  )
}
