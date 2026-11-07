import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import AppCard from '../components/AppCard.jsx'
import { ServerNotice } from '../components/Chrome.jsx'
import JourneyStrip, { StripLegend } from '../components/JourneyStrip.jsx'
import SearchBox from '../components/SearchBox.jsx'
import { useLibrary } from '../context/useLibrary.js'
import { useDocumentTitle } from '../hooks/hooks.js'
import { DIFFICULTY, formatRange, totalSpan } from '../lib/format.js'
import { totalWeight } from '../lib/strip.js'

const FILTERS = ['all', 'easy', 'medium', 'hard', 'gated']
const SORTS = {
  name: { label: 'A–Z', fn: (a, b) => a.app_name.localeCompare(b.app_name) },
  fastest: { label: 'Fastest', fn: (a, b) => totalSpan(a).max_minutes - totalSpan(b).max_minutes },
  slowest: { label: 'Slowest', fn: (a, b) => totalSpan(b).max_minutes - totalSpan(a).max_minutes },
}

const HOW = [
  { n: '01', title: 'Look up an app', body: 'Pick one from the library, or type any app or website. If we haven’t seen it, an agent researches it live in about 30 seconds.' },
  { n: '02', title: 'See the whole path', body: 'How hard it is, how long it takes, what blocks approval, and which steps are waiting on the provider, in one strip.' },
  { n: '03', title: 'Know who does what', body: 'Every step says whether AI can draft it or only you can do it. Copy a ready-made prompt, or share the guide with your team.' },
]

function Showcase({ guides }) {
  // Spread across the range, quickest to slowest, so the contrast is the point.
  const picks = useMemo(() => {
    const sorted = [...guides].sort((a, b) => totalSpan(a).max_minutes - totalSpan(b).max_minutes)
    const count = Math.min(4, sorted.length)
    if (count < 2) return sorted
    return Array.from({ length: count }, (_, i) => sorted[Math.round((i * (sorted.length - 1)) / (count - 1))])
  }, [guides])
  if (!picks.length) return null
  const scale = Math.max(...picks.map((g) => totalWeight(g.segments)))

  return (
    <div className="showcase card rise" style={{ '--i': 3 }}>
      <header>
        <span className="label">Same job, very different journeys</span>
        <StripLegend />
      </header>
      <ul>
        {picks.map((g) => {
          const total = totalSpan(g)
          return (
            <li key={g.slug}>
              <Link to={`/g/${g.slug}`} className="showcase-row">
                <span className="showcase-name">{g.app_name}</span>
                <div className="showcase-strip">
                  <JourneyStrip segments={g.segments} compact scaleTo={scale} />
                </div>
                <span className="showcase-time">{formatRange(total.min_minutes, total.max_minutes)}</span>
              </Link>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default function Home() {
  useDocumentTitle('')
  const { guides, phase, error, reload } = useLibrary()
  const navigate = useNavigate()
  const { hash } = useLocation()
  const [difficulty, setDifficulty] = useState('all')
  const [sort, setSort] = useState('name')
  const [needsOwnApp, setNeedsOwnApp] = useState(false)
  const [selected, setSelected] = useState([])

  useEffect(() => {
    if (hash === '#search') document.querySelector('.search input')?.focus()
  }, [hash])

  const visible = useMemo(
    () =>
      guides
        .filter((g) => difficulty === 'all' || g.difficulty === difficulty)
        .filter((g) => !needsOwnApp || g.composio !== 'managed')
        .sort(SORTS[sort].fn),
    [guides, difficulty, sort, needsOwnApp],
  )

  const counts = useMemo(() => Object.fromEntries(FILTERS.map((f) => [f, f === 'all' ? guides.length : guides.filter((g) => g.difficulty === f).length])), [guides])

  const toggleCompare = (slug) => setSelected((s) => (s.includes(slug) ? s.filter((x) => x !== slug) : [...s, slug].slice(-4)))

  return (
    <main>
      <section className="hero">
        <div className="hero-bars hero-bars-l" aria-hidden="true" />
        <div className="hero-bars hero-bars-r" aria-hidden="true" />
        <div className="page hero-inner">
          <p className="label rise">OAuth app setup guides for agent builders</p>
          <h1 className="rise" style={{ '--i': 1 }}>
            Know the path <span className="mark">before you build</span>
          </h1>
          <p className="hero-sub rise" style={{ '--i': 2 }}>
            Your users can’t connect an app until you have its OAuth app, and getting one can take an hour or a quarter. See how hard it is, how long it takes,
            and what to do next.
          </p>
          <div id="search" className="rise" style={{ '--i': 3 }}>
            <SearchBox />
          </div>
          {guides.length > 0 && (
            <p className="try rise" style={{ '--i': 4 }}>
              <span className="label">Try</span>
              {guides.slice(0, 5).map((g) => (
                <Link key={g.slug} to={`/g/${g.slug}`} className="chip">
                  {g.app_name}
                </Link>
              ))}
            </p>
          )}
        </div>
      </section>

      <div className="page">
        <ServerNotice phase={phase} error={error} onRetry={reload} />
        {phase === 'ready' && <Showcase guides={guides} />}
      </div>

      <section className="page library" id="library">
        <header className="library-head">
          <div>
            <span className="label">The library</span>
            <h2>
              Guides ready to <span className="accent">use</span>
            </h2>
          </div>
          <div className="controls">
            <div className="seg-control" role="group" aria-label="Filter by difficulty">
              {FILTERS.map((f) => (
                <button key={f} type="button" className={difficulty === f ? 'is-on' : ''} onClick={() => setDifficulty(f)} aria-pressed={difficulty === f}>
                  {f === 'all' ? 'All' : DIFFICULTY[f].label}
                  <span>{counts[f]}</span>
                </button>
              ))}
            </div>
            <label className="check">
              <input type="checkbox" checked={needsOwnApp} onChange={(e) => setNeedsOwnApp(e.target.checked)} />
              Needs my own OAuth app
            </label>
            <label className="select">
              <span className="label">Sort</span>
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                {Object.entries(SORTS).map(([key, s]) => (
                  <option key={key} value={key}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </header>

        {phase === 'ready' && visible.length === 0 && (
          <div className="card empty">
            <h3>{guides.length === 0 ? 'No guides yet' : 'Nothing matches those filters'}</h3>
            <p className="muted">Search for any app above and an agent will research it for you.</p>
          </div>
        )}

        {phase !== 'ready' && (
          <div className="grid">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton sk-card" />
            ))}
          </div>
        )}

        <div className="grid">
          {visible.map((g, i) => (
            <AppCard key={g.slug} guide={g} index={i} selected={selected.includes(g.slug)} onToggleCompare={toggleCompare} />
          ))}
        </div>
      </section>

      <section className="page how">
        <span className="label">How it works</span>
        <h2>
          From “which apps?” to <span className="accent">“what’s next?”</span>
        </h2>
        <ol className="how-grid">
          {HOW.map((h) => (
            <li key={h.n} className="card">
              <span className="label">{h.n}</span>
              <h3>{h.title}</h3>
              <p className="muted">{h.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {selected.length > 0 && (
        <div className="compare-bar" role="region" aria-label="Compare selected apps">
          <span>
            {selected.length} selected{selected.length < 2 ? ': pick one more' : ''}
          </span>
          <button className="btn" type="button" onClick={() => setSelected([])}>
            Clear
          </button>
          <button className="btn btn-solid" type="button" disabled={selected.length < 2} onClick={() => navigate(`/compare?apps=${selected.join(',')}`)}>
            Compare launch plans →
          </button>
        </div>
      )}
    </main>
  )
}
