import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { DifficultyBadge, Favicon } from '../components/Badges.jsx'
import { ServerNotice } from '../components/Chrome.jsx'
import JourneyStrip, { StripLegend } from '../components/JourneyStrip.jsx'
import { useLibrary } from '../context/useLibrary.js'
import { useDocumentTitle } from '../hooks/hooks.js'
import { formatRange, totalSpan } from '../lib/format.js'
import { totalWeight } from '../lib/strip.js'

export default function Compare() {
  useDocumentTitle('Compare launch plans')
  const { guides, phase, error, reload } = useLibrary()
  const [params, setParams] = useSearchParams()
  const slugs = useMemo(() => (params.get('apps') || '').split(',').filter(Boolean), [params])
  const chosen = useMemo(() => slugs.map((s) => guides.find((g) => g.slug === s)).filter(Boolean), [slugs, guides])

  const toggle = (slug) => {
    const next = slugs.includes(slug) ? slugs.filter((s) => s !== slug) : [...slugs, slug].slice(-6)
    setParams(next.length ? { apps: next.join(',') } : {}, { replace: true })
  }

  const scale = chosen.length ? Math.max(...chosen.map((g) => totalWeight(g.segments))) : 1
  const byWait = [...chosen].sort((a, b) => b.waiting.max_minutes - a.waiting.max_minutes)
  const bottleneck = byWait[0]?.waiting.max_minutes ? byWait[0] : null
  const slowest = [...chosen].sort((a, b) => totalSpan(b).max_minutes - totalSpan(a).max_minutes)[0]

  return (
    <main className="page compare">
      <p className="label rise">Plan my launch</p>
      <h1 className="rise" style={{ '--i': 1 }}>
        Which app is your <span className="accent">critical path?</span>
      </h1>
      <p className="muted lede rise" style={{ '--i': 2 }}>
        Pick the apps you need to connect. We’ll put their journeys on one scale so you can see what blocks your launch, and what to start first.
      </p>

      <ServerNotice phase={phase} error={error} onRetry={reload} />

      <div className="picker rise" style={{ '--i': 3 }} role="group" aria-label="Choose apps to compare">
        {guides.map((g) => (
          <button key={g.slug} type="button" className={`chip chip-pick ${slugs.includes(g.slug) ? 'is-on' : ''}`} onClick={() => toggle(g.slug)} aria-pressed={slugs.includes(g.slug)}>
            <Favicon domain={g.domain} name={g.app_name} size={18} />
            {g.app_name}
          </button>
        ))}
      </div>

      {chosen.length < 2 ? (
        <div className="card empty">
          <h3>Pick at least two apps</h3>
          <p className="muted">Try a quick one and a slow one together to see the difference.</p>
        </div>
      ) : (
        <>
          <aside className={`callout ${bottleneck ? 'callout-warn' : 'callout-good'} rise`}>
            <span className="callout-tag">Critical path</span>
            <div>
              {bottleneck ? (
                <>
                  <h3>
                    {bottleneck.app_name} sets your launch date: {formatRange(bottleneck.waiting.min_minutes, bottleneck.waiting.max_minutes)} of waiting
                  </h3>
                  <p>
                    Start its review first. The other apps can be finished while you wait, so together you can launch in roughly{' '}
                    <strong>{formatRange(totalSpan(slowest).min_minutes, totalSpan(slowest).max_minutes)}</strong> instead of the sum of all of them.
                  </p>
                </>
              ) : (
                <>
                  <h3>No approval waits in this set</h3>
                  <p>None of these need a provider review, so you can launch as fast as you can do the work.</p>
                </>
              )}
            </div>
          </aside>

          <section className="card compare-chart rise">
            <header>
              <span className="label">Journeys on one scale</span>
              <StripLegend />
            </header>
            <ul>
              {[...chosen]
                .sort((a, b) => totalSpan(b).max_minutes - totalSpan(a).max_minutes)
                .map((g) => {
                  const total = totalSpan(g)
                  return (
                    <li key={g.slug} className="compare-row">
                      <Link to={`/g/${g.slug}`} className="compare-name">
                        <Favicon domain={g.domain} name={g.app_name} size={24} />
                        {g.app_name}
                      </Link>
                      <div className="compare-strip">
                        <JourneyStrip segments={g.segments} compact scaleTo={scale} />
                      </div>
                      <span className="compare-time">{formatRange(total.min_minutes, total.max_minutes)}</span>
                    </li>
                  )
                })}
            </ul>
          </section>

          <section className="card table-card rise">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>App</th>
                    <th>Difficulty</th>
                    <th>Hands-on</th>
                    <th>Waiting</th>
                    <th>AI can draft</th>
                    <th>Composio</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {byWait.map((g) => (
                    <tr key={g.slug}>
                      <th scope="row">
                        <Link to={`/g/${g.slug}`}>{g.app_name}</Link>
                      </th>
                      <td>
                        <DifficultyBadge level={g.difficulty} size="sm" />
                      </td>
                      <td>{formatRange(g.hands_on.min_minutes, g.hands_on.max_minutes)}</td>
                      <td>{formatRange(g.waiting.min_minutes, g.waiting.max_minutes)}</td>
                      <td>{Math.round(g.agent_share * 100)}% of hands-on time</td>
                      <td>{g.composio === 'managed' ? 'Managed: skip registration' : g.composio === 'byo' ? 'Bring your own app' : 'Not listed'}</td>
                      <td className={`conf-text conf-${g.confidence}`}>{g.confidence}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="order rise">
            <span className="label">Suggested order</span>
            <ol>
              {byWait.map((g, i) => (
                <li key={g.slug}>
                  <span className="order-n">{i + 1}</span>
                  <div>
                    <Link to={`/g/${g.slug}`}>
                      <strong>{g.app_name}</strong>
                    </Link>
                    <span className="muted">
                      {g.waiting.max_minutes ? ` · starts a ${formatRange(g.waiting.min_minutes, g.waiting.max_minutes)} wait` : ' · no waiting, do it any time'}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </>
      )}
    </main>
  )
}
