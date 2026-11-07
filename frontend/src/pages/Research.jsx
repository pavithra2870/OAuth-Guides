import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Favicon } from '../components/Badges.jsx'
import { useLibrary } from '../context/useLibrary.js'
import { useDocumentTitle } from '../hooks/hooks.js'
import { wakeServer } from '../lib/api.js'
import { hostOf } from '../lib/format.js'
import { summarize } from '../lib/library.js'
import { streamSSE } from '../lib/sse.js'

const STAGES = [
  { id: 'resolve', label: 'Identify the app' },
  { id: 'search', label: 'Search official docs and developer forums' },
  { id: 'read', label: 'Read the pages' },
  { id: 'write', label: 'Work out the path, timing and blockers' },
  { id: 'verify', label: 'Check every claim against its source' },
]

function clock(seconds) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

/** One research run. Mounted fresh (via `key`) for every query and every retry, so state never needs resetting. */
function ResearchRun({ query, onRetry }) {
  const navigate = useNavigate()
  const { add } = useLibrary()
  const [name, setName] = useState(query)
  const [stages, setStages] = useState({})
  const [sources, setSources] = useState([])
  const [error, setError] = useState(null)
  const [ready, setReady] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const startedAt = useRef(0)
  useDocumentTitle(`Researching ${name}`)

  useEffect(() => {
    const controller = new AbortController()
    let stop = () => {}
    startedAt.current = Date.now()

    async function run() {
      let awake = false
      try {
        awake = await wakeServer({ signal: controller.signal })
      } catch (err) {
        if (err.name === 'AbortError') return // left the page while waiting
        throw err
      }
      if (!awake) {
        setError({ message: 'The server is taking too long to wake up. Please try again in a moment.' })
        return
      }
      stop = streamSSE('/api/generate', {
        idleMs: 45000,
        init: { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query }) },
        onEvent: (event, data) => {
          if (event === 'resolved') setName(data.name)
          if (event === 'progress') setStages((s) => ({ ...s, [data.stage]: { status: data.status, message: data.message } }))
          if (event === 'source') setSources((list) => (list.some((x) => x.id === data.id) ? list : [...list, data]))
          if (event === 'error') setError(data)
          if (event === 'guide') {
            setReady(true)
            add(summarize(data, 'generated'))
            setTimeout(() => navigate(`/g/${data.slug}`, { replace: true, state: { guide: data, origin: 'generated' } }), 900)
          }
        },
        onError: (err) => setError({ message: err.message }),
      })
    }

    run()
    return () => {
      controller.abort()
      stop()
    }
  }, [query, navigate, add])

  useEffect(() => {
    if (error || ready) return undefined
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt.current) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [error, ready])

  return (
    <main className="page narrow research">
      <Link to="/" className="back label">
        ← Library
      </Link>

      <p className="label rise">Live research</p>
      <h1 className="rise" style={{ '--i': 1 }}>
        {ready ? 'Guide ready for ' : 'Researching '}
        <span className="accent">{name}</span>
      </h1>
      <p className="muted rise" style={{ '--i': 2 }}>
        An agent is reading the provider’s own documentation and checking what it finds. This usually takes 30–60 seconds.
      </p>

      {error ? (
        <div className="card empty rise" role="alert">
          <h2>{error.code === 'rate_limited' ? 'Live research limit reached' : 'We couldn’t finish this one'}</h2>
          <p className="muted">{error.message}</p>
          <div className="row">
            {error.code !== 'rate_limited' && (
              <button className="btn btn-solid" onClick={onRetry}>
                Try again
              </button>
            )}
            <Link className="btn" to="/">
              Browse the library
            </Link>
          </div>
        </div>
      ) : (
        <div className="research-grid rise" style={{ '--i': 3 }}>
          <ol className="stages card" aria-live="polite">
            {STAGES.map((stage) => {
              const info = stages[stage.id]
              const status = info?.status ?? 'pending'
              return (
                <li key={stage.id} className={`stage stage-${status}`}>
                  <span className="stage-mark" aria-hidden="true">
                    {status === 'done' ? '✓' : status === 'running' ? <span className="spinner" /> : ''}
                  </span>
                  <div>
                    <strong>{stage.label}</strong>
                    {info?.message && status !== 'pending' && <p className="muted">{info.message}</p>}
                  </div>
                </li>
              )
            })}
            <li className="stage-clock label">{ready ? 'Opening your guide…' : `Elapsed ${clock(elapsed)}`}</li>
          </ol>

          <section className="feed card" aria-live="polite">
            <header className="feed-head">
              <span className="label">Pages the agent is reading</span>
              <span className="label">{sources.length}</span>
            </header>
            {sources.length === 0 ? (
              <p className="muted">Sources will appear here as they’re found.</p>
            ) : (
              <ul>
                {sources.map((s, i) => (
                  <li key={s.id} className="feed-item" style={{ '--i': i }}>
                    <Favicon domain={hostOf(s.url)} name={s.title || hostOf(s.url)} size={22} />
                    <div>
                      <a href={s.url} target="_blank" rel="noreferrer noopener">
                        {s.title || hostOf(s.url)}
                      </a>
                      <span className="muted feed-host">{hostOf(s.url)}</span>
                    </div>
                    <span className={`tag tag-kind-${s.kind}`}>{s.kind === 'official' ? 'Official' : 'Community'}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </main>
  )
}

export default function Research() {
  const [params] = useSearchParams()
  const query = (params.get('q') || '').trim()
  const navigate = useNavigate()
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (query.length < 2) navigate('/', { replace: true })
  }, [query, navigate])

  if (query.length < 2) return null
  return <ResearchRun key={`${query}:${attempt}`} query={query} onRetry={() => setAttempt((n) => n + 1)} />
}
