import { Link } from 'react-router-dom'
import { formatRange, totalSpan } from '../lib/format.js'
import { DifficultyBadge, Favicon } from './Badges.jsx'
import JourneyStrip from './JourneyStrip.jsx'

export default function AppCard({ guide, selected, onToggleCompare, index = 0 }) {
  const total = totalSpan({ hands_on: guide.hands_on, waiting: guide.waiting })
  const managed = guide.composio === 'managed'

  return (
    <article className={`app-card rise ${selected ? 'is-selected' : ''}`} style={{ '--i': Math.min(index, 8) }}>
      <Link to={`/g/${guide.slug}`} className="app-card-link" aria-label={`${guide.app_name} guide`}>
        <header className="app-card-head">
          <Favicon domain={guide.domain} name={guide.app_name} size={36} />
          <div className="app-card-title">
            <h3>{guide.app_name}</h3>
            <span className="label">{guide.domain || ''}</span>
          </div>
          <DifficultyBadge level={guide.difficulty} size="sm" />
        </header>

        <JourneyStrip segments={guide.segments} compact />

        <dl className="app-card-stats">
          <div>
            <dt className="label">Total</dt>
            <dd>{formatRange(total.min_minutes, total.max_minutes)}</dd>
          </div>
          <div>
            <dt className="label">Waiting</dt>
            <dd>{formatRange(guide.waiting.min_minutes, guide.waiting.max_minutes)}</dd>
          </div>
        </dl>

        <p className="app-card-note">
          {managed ? (
            <span className="note-managed">Composio-managed: you can skip registration</span>
          ) : (
            <span className="muted">{guide.headline}</span>
          )}
        </p>
      </Link>

      {onToggleCompare && (
        <label className="compare-toggle">
          <input type="checkbox" checked={selected} onChange={() => onToggleCompare(guide.slug)} />
          <span>Compare</span>
        </label>
      )}
    </article>
  )
}
