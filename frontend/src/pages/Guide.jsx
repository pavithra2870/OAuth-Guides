import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { Favicon, DifficultyBadge, EvidenceBadge } from '../components/Badges.jsx'
import { ComposioNotice, ConfidencePanel, Handoff, Provenance, ShareBar, SourceList } from '../components/GuideParts.jsx'
import JourneyStrip, { StripLegend } from '../components/JourneyStrip.jsx'
import StepList from '../components/StepList.jsx'
import { useChecklist, useDocumentTitle, useScrollSpy } from '../hooks/hooks.js'
import { ApiError, getJSON, wakeServer } from '../lib/api.js'
import { DIFFICULTY, formatRange, hostOf, stepRange, totalSpan } from '../lib/format.js'

function useGuide(slug) {
  const { state: routeState } = useLocation()
  const handed = routeState?.guide?.slug === slug ? routeState : null
  const [state, setState] = useState(
    handed ? { phase: 'ready', guide: handed.guide, origin: handed.origin ?? 'generated' } : { phase: 'loading', guide: null, origin: 'generated' },
  )

  useEffect(() => {
    if (handed) return undefined
    const controller = new AbortController()
    const { signal } = controller
    async function load() {
      try {
        await wakeServer({ signal })
        const data = await getJSON(`/api/guides/${encodeURIComponent(slug)}`, { signal })
        setState({ phase: 'ready', guide: data.guide, origin: data.origin })
      } catch (err) {
        if (err.name === 'AbortError') return
        setState({ phase: err instanceof ApiError && err.status === 404 ? 'missing' : 'error', guide: null, origin: 'generated', error: err.message })
      }
    }
    load()
    return () => controller.abort()
  }, [slug, handed])

  return state
}

function flash(id) {
  const el = document.getElementById(id)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.classList.add('flash')
  setTimeout(() => el.classList.remove('flash'), 1400)
}

function Section({ id, title, kicker, children }) {
  return (
    <section id={id} className="section">
      <header className="section-head">
        {kicker && <span className="label">{kicker}</span>}
        <h2>{title}</h2>
      </header>
      {children}
    </section>
  )
}

function Skeleton() {
  return (
    <main className="page guide" aria-busy="true">
      <div className="skeleton sk-title" />
      <div className="skeleton sk-hero" />
      <div className="skeleton sk-line" />
      <div className="skeleton sk-line short" />
    </main>
  )
}

function Verdict({ guide, done }) {
  const { timeline } = guide
  const total = totalSpan(timeline)
  const waitShare = total.max_minutes ? timeline.waiting.max_minutes / total.max_minutes : 0
  const next = guide.steps.find((s) => s.owner !== 'provider' && !done.has(s.id))
  const doable = guide.steps.filter((s) => s.owner !== 'provider')
  // An agent "helps" with a step if it does it outright, or can draft what the developer pastes in.
  const agentSteps = doable.filter((s) => s.owner === 'agent' || s.agent_assist).length

  const sentence =
    timeline.waiting.max_minutes === 0
      ? 'No approval wait. Your own work is the only clock.'
      : waitShare > 0.6
        ? `Most of that is waiting on ${guide.app_name}’s review.`
        : `About ${formatRange(timeline.hands_on.min_minutes, timeline.hands_on.max_minutes)} is hands-on work.`

  return (
    <section className="verdict card">
      <span className="label">The verdict</span>
      <h2 className="verdict-title">
        Plan for <span className="mark">{formatRange(total.min_minutes, total.max_minutes)}</span>
      </h2>
      <p className="verdict-sub">
        {sentence} {guide.difficulty.headline}
      </p>

      <div className="verdict-strip">
        <JourneyStrip segments={timeline.segments} onSelect={(id) => flash(`step-${id}`)} />
        <StripLegend />
      </div>

      <dl className="stats">
        <div>
          <dt className="label">Hands-on</dt>
          <dd>{formatRange(timeline.hands_on.min_minutes, timeline.hands_on.max_minutes)}</dd>
          <span className="muted">the work that’s yours</span>
        </div>
        <div>
          <dt className="label">Waiting</dt>
          <dd>{formatRange(timeline.waiting.min_minutes, timeline.waiting.max_minutes)}</dd>
          <span className="muted">{timeline.waiting.max_minutes ? 'on the provider' : 'no approval needed'}</span>
        </div>
        <div>
          <dt className="label">AI can draft for</dt>
          <dd>
            {agentSteps} of {doable.length} steps
          </dd>
          <span className="muted">you log in, submit, decide</span>
        </div>
        <div>
          <dt className="label">Confidence</dt>
          <dd className={`conf-text conf-${guide.stats.confidence}`}>{guide.stats.confidence}</dd>
          <a href="#trust" className="muted">
            how we checked ↓
          </a>
        </div>
      </dl>

      {next && (
        <div className="start-here">
          <div>
            <span className="label">Start here</span>
            <h3>{next.title}</h3>
            <p className="muted">
              {next.owner === 'agent' ? 'AI can draft this' : 'You do this one'} · {stepRange(next)}
            </p>
          </div>
          <div className="start-actions">
            {next.link && (
              <a className="btn btn-solid" href={next.link} target="_blank" rel="noreferrer noopener">
                Open {hostOf(next.link)} ↗
              </a>
            )}
            <button className="btn" type="button" onClick={() => flash(`step-${next.id}`)}>
              Jump to step
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

export default function Guide() {
  const { slug } = useParams()
  // Keyed by slug so navigating between guides starts from a clean loading state.
  return <GuideView key={slug} slug={slug} />
}

function GuideView({ slug }) {
  const { phase, guide, origin, error } = useGuide(slug)
  const [done, toggle] = useChecklist(slug)
  useDocumentTitle(guide ? `${guide.app_name} OAuth setup` : 'Guide')

  const sections = useMemo(() => {
    if (!guide) return []
    return [
      { id: 'path', label: 'The path' },
      { id: 'handoff', label: 'AI or you?' },
      { id: 'rating', label: `Why ${DIFFICULTY[guide.difficulty.level].label.toLowerCase()}` },
      { id: 'before', label: 'Before approval' },
      guide.requirements.length && { id: 'requirements', label: 'Requirements' },
      guide.gotchas.length && { id: 'gotchas', label: 'Gotchas' },
      guide.blockers.length && { id: 'stuck', label: 'If you get stuck' },
      { id: 'trust', label: 'How much to trust this' },
      { id: 'sources', label: 'Sources' },
    ].filter(Boolean)
  }, [guide])
  const active = useScrollSpy(sections.map((s) => s.id))

  const jump = useCallback((id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), [])

  if (phase === 'loading') return <Skeleton />

  if (phase === 'missing' || phase === 'error') {
    return (
      <main className="page narrow">
        <Link to="/" className="back label">
          ← Library
        </Link>
        <div className="card empty">
          <h1>{phase === 'missing' ? 'No guide for this app yet' : 'Couldn’t load this guide'}</h1>
          <p className="muted">
            {phase === 'missing' ? 'Our agent can research it now. It takes about 30 seconds.' : error}
          </p>
          {phase === 'missing' && (
            <Link className="btn btn-solid" to={`/research?q=${encodeURIComponent(slug)}`}>
              Research “{slug}” live →
            </Link>
          )}
        </div>
      </main>
    )
  }

  const level = DIFFICULTY[guide.difficulty.level]

  return (
    <main className="page guide">
      <Link to="/" className="back label">
        ← Library
      </Link>

      <header className="guide-head rise">
        <Favicon domain={guide.domain} name={guide.app_name} size={56} />
        <div className="guide-title">
          <h1>{guide.app_name}</h1>
          <Provenance guide={guide} origin={origin} />
        </div>
        <DifficultyBadge level={guide.difficulty.level} size="lg" />
        <ShareBar guide={guide} />
      </header>

      <Verdict guide={guide} done={done} />
      <ComposioNotice composio={guide.composio} appName={guide.app_name} />

      <div className="guide-grid">
        <nav className="toc" aria-label="On this page">
          <span className="label">On this page</span>
          <ul>
            {sections.map((s) => (
              <li key={s.id}>
                <button type="button" className={active === s.id ? 'is-active' : ''} onClick={() => jump(s.id)}>
                  {s.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="guide-main">
          <Section id="path" kicker="Do this" title="The path, step by step">
            <p className="lede">{guide.summary}</p>
            <StepList guide={guide} done={done} onToggle={toggle} />
          </Section>

          <Section id="handoff" kicker="Hand-off" title="What AI can draft, and what only you can do">
            <p className="lede safe-note">We never ask for your logins or secrets. You do every step on the provider’s own site.</p>
            <Handoff guide={guide} />
          </Section>

          <Section id="rating" kicker="Difficulty" title={`Why this is rated ${level.label.toLowerCase()}`}>
            <p className="lede">{level.blurb}.</p>
            <ul className="factors">
              {guide.difficulty.factors.map((f) => (
                <li key={f.label} className={`factor factor-${f.severity}`}>
                  <span className={`sev sev-${f.severity}`}>{f.severity}</span>
                  <div>
                    <h3>{f.label}</h3>
                    <p>{f.detail}</p>
                    <EvidenceBadge evidence={f.evidence} sources={guide.sources} />
                  </div>
                </li>
              ))}
            </ul>
          </Section>

          <Section id="before" kicker="While you wait" title="What you can do before approval">
            <div className={`before before-${guide.can_test_before_approval.answer}`}>
              <span className="before-answer">
                {{ yes: 'Yes, mostly', partly: 'Partly', no: 'No' }[guide.can_test_before_approval.answer]}
              </span>
              <p>{guide.can_test_before_approval.detail}</p>
              <EvidenceBadge evidence={guide.can_test_before_approval.evidence} sources={guide.sources} />
            </div>
          </Section>

          {guide.requirements.length > 0 && (
            <Section id="requirements" kicker="Have ready" title="Requirements">
              <ul className="requirements">
                {guide.requirements.map((r) => (
                  <li key={r.label}>
                    <span className={`tag ${r.required ? 'tag-req' : 'tag-opt'}`}>{r.required ? 'Required' : 'Optional'}</span>
                    <div>
                      <h3>{r.label}</h3>
                      <p>{r.detail}</p>
                      <EvidenceBadge evidence={r.evidence} sources={guide.sources} />
                    </div>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {guide.gotchas.length > 0 && (
            <Section id="gotchas" kicker="Watch out" title="Gotchas that catch people">
              <div className="cards-2">
                {guide.gotchas.map((g) => (
                  <article key={g.title} className="mini-card">
                    <h3>{g.title}</h3>
                    <p>{g.detail}</p>
                    <EvidenceBadge evidence={g.evidence} sources={guide.sources} />
                  </article>
                ))}
              </div>
            </Section>
          )}

          {guide.blockers.length > 0 && (
            <Section id="stuck" kicker="Blocked?" title="If you get stuck">
              <ul className="blockers">
                {guide.blockers.map((b) => (
                  <li key={b.problem}>
                    <h3>{b.problem}</h3>
                    {b.why && <p className="muted">{b.why}</p>}
                    <p className="fix">
                      <span className="label">Fix</span> {b.fix}
                    </p>
                    <EvidenceBadge evidence={b.evidence} sources={guide.sources} />
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section id="trust" kicker="Evidence" title="How much to trust this">
            <ConfidencePanel guide={guide} />
          </Section>

          <Section id="sources" kicker="Receipts" title={`Sources (${guide.sources.length})`}>
            <SourceList sources={guide.sources} guide={guide} />
          </Section>
        </div>
      </div>
    </main>
  )
}
