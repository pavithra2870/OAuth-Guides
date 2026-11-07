import { useMemo } from 'react'
import { useCopy } from '../hooks/hooks.js'
import { EVIDENCE, OWNER, formatDate, hostOf, stepRange } from '../lib/format.js'
import { guideToMarkdown } from '../lib/markdown.js'

/** Who does what: the agent's share vs. where the developer must take over. */
export function Handoff({ guide }) {
  const groups = useMemo(
    () => ({
      agent: guide.steps.filter((s) => s.owner === 'agent'),
      you: guide.steps.filter((s) => s.owner === 'you'),
      provider: guide.steps.filter((s) => s.owner === 'provider'),
    }),
    [guide],
  )

  return (
    <div className="handoff">
      {['agent', 'you', 'provider'].map((owner) => (
        <div key={owner} className={`handoff-col handoff-${owner}`}>
          <header>
            <span className={`swatch seg-${owner}`} />
            <h3>{OWNER[owner].label}</h3>
            <span className="handoff-count">{groups[owner].length}</span>
          </header>
          <p className="label">{OWNER[owner].verb}</p>
          {groups[owner].length ? (
            <ul>
              {groups[owner].map((s) => (
                <li key={s.id}>
                  <a href={`#step-${s.id}`}>{s.title}</a>
                  <span className="muted">{stepRange(s)}</span>
                  {owner === 'you' && s.agent_assist && (
                    <span className="handoff-assist">
                      <strong>AI drafts:</strong> {s.agent_assist}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing in this guide.</p>
          )}
        </div>
      ))}
    </div>
  )
}

/** Does Composio already provide this OAuth app? The very first question. */
export function ComposioNotice({ composio, appName }) {
  if (composio.status === 'managed') {
    return (
      <aside className="callout callout-good">
        <span className="callout-tag">Step zero</span>
        <div>
          <h3>You may not need to do any of this</h3>
          <p>
            Composio already provides an OAuth app for {composio.name || appName}. Use it and your users can connect today, with no registration and no
            review. Register your own app (the steps below) only if you need your own branding on the consent screen, custom scopes, or dedicated rate
            limits.{' '}
            <a href="https://docs.composio.dev/docs/authentication/custom-app-vs-managed-app" target="_blank" rel="noreferrer noopener">
              Managed vs custom auth ↗
            </a>
          </p>
        </div>
      </aside>
    )
  }
  if (composio.status === 'byo') {
    return (
      <aside className="callout callout-warn">
        <span className="callout-tag">Step zero</span>
        <div>
          <h3>Composio can’t do this one for you</h3>
          <p>
            {composio.name || appName} has no Composio-managed OAuth app. You register your own app with the provider, then paste its client ID and secret into a
            Composio auth config. That’s what this guide walks through.
            {composio.related?.length > 0 && (
              <>
                {' '}
                Related: {composio.related.map((r) => `${r.name} (${r.status === 'managed' ? 'managed' : 'bring your own'})`).join(', ')}.
              </>
            )}
          </p>
        </div>
      </aside>
    )
  }
  return (
    <aside className="callout">
      <span className="callout-tag">Step zero</span>
      <div>
        <h3>Not in Composio’s OAuth directory</h3>
        <p>
          We couldn’t find {appName} in Composio’s list of OAuth toolkits, so we can’t say whether a managed app exists. Check the toolkit catalog before
          registering your own.
        </p>
      </div>
    </aside>
  )
}

/** Honest account of how well the guide is backed, and what we could not confirm. */
export function ConfidencePanel({ guide }) {
  const { counts, confidence, unverified } = guide.stats
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1
  const levels = ['tested', 'documented', 'reported', 'inferred']

  return (
    <div className="confidence">
      <div className="confidence-head">
        <span className={`conf conf-${confidence}`}>{confidence} confidence</span>
        <p className="muted">
          {total} claims checked. Each quote was matched word for word against the page we fetched. A match shows the claim is quoted from that page;
          it doesn’t prove the page is current, so confirm anything that matters before you submit.
        </p>
      </div>

      <div className="stacked" role="img" aria-label="Share of claims by evidence level">
        {levels.map((level) =>
          counts[level] ? <span key={level} className={`stacked-${level}`} style={{ flexGrow: counts[level] }} title={`${EVIDENCE[level].label}: ${counts[level]}`} /> : null,
        )}
      </div>
      <ul className="stacked-legend">
        {levels.map((level) => (
          <li key={level}>
            <span className={`ev-dot ev-${level}`} /> {EVIDENCE[level].label} <strong>{counts[level] || 0}</strong>
          </li>
        ))}
      </ul>

      {!counts.tested && (
        <p className="honest">
          <strong>Not tested hands-on.</strong> No one has completed this registration for this guide yet. It reflects what the provider’s documentation says.
        </p>
      )}

      {(unverified.length > 0 || guide.uncertain.length > 0) && (
        <div className="unverified">
          <h3>What we couldn’t confirm</h3>
          <ul>
            {guide.uncertain.map((u) => (
              <li key={u}>{u}</li>
            ))}
            {unverified.map((u) => (
              <li key={u}>
                {u} <span className="muted">(no source states this directly)</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function SourceList({ sources, guide }) {
  const cited = useMemo(() => {
    const counts = {}
    const bump = (ev) => ev?.source_ids.forEach((id) => (counts[id] = (counts[id] || 0) + 1))
    guide.steps.forEach((x) => bump(x.evidence))
    guide.requirements.forEach((x) => bump(x.evidence))
    guide.gotchas.forEach((x) => bump(x.evidence))
    guide.blockers.forEach((x) => bump(x.evidence))
    guide.difficulty.factors.forEach((x) => bump(x.evidence))
    bump(guide.can_test_before_approval.evidence)
    return counts
  }, [guide])

  return (
    <ul className="sources">
      {sources.map((s) => (
        <li key={s.id}>
          <span className="source-id label">{s.id}</span>
          <a href={s.url} target="_blank" rel="noreferrer noopener">
            {s.title || hostOf(s.url)}
          </a>
          <span className="muted source-host">{hostOf(s.url)}</span>
          <span className={`tag tag-kind-${s.kind}`}>{s.kind === 'official' ? 'Official' : 'Community'}</span>
          <span className="muted source-cites">{cited[s.id] ? `cited ${cited[s.id]}×` : 'read, not cited'}</span>
        </li>
      ))}
    </ul>
  )
}

export function ShareBar({ guide }) {
  const [copied, copy] = useCopy()
  const url = window.location.href
  return (
    <div className="share">
      <button className="btn" type="button" onClick={() => copy(url, 'link')}>
        {copied === 'link' ? 'Link copied ✓' : 'Copy link'}
      </button>
      <button className="btn" type="button" onClick={() => copy(guideToMarkdown(guide, url), 'md')}>
        {copied === 'md' ? 'Markdown copied ✓' : 'Copy as Markdown'}
      </button>
    </div>
  )
}

export function Provenance({ guide, origin }) {
  return (
    <p className="label provenance">
      {origin === 'curated' ? 'Curated and checked' : 'Researched by an AI agent'} · {formatDate(guide.meta.researched_at)} · {guide.meta.pages_read} pages read
    </p>
  )
}
