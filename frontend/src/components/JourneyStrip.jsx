import { useState } from 'react'
import { OWNER, formatRange } from '../lib/format.js'
import { totalWeight, weightOf } from '../lib/strip.js'

export function StripLegend({ className = '' }) {
  return (
    <ul className={`legend ${className}`}>
      {['agent', 'you', 'provider'].map((owner) => (
        <li key={owner}>
          <span className={`swatch seg-${owner}`} />
          {OWNER[owner].label}
        </li>
      ))}
    </ul>
  )
}

/**
 * The journey: one block per step, coloured by who does it, sized by how long it takes.
 * `scaleTo` lets several strips share one scale (used when comparing apps).
 */
export default function JourneyStrip({ segments, compact = false, scaleTo, onSelect, labels }) {
  const [active, setActive] = useState(null)
  if (!segments?.length) return null

  const sum = totalWeight(segments)
  const width = scaleTo ? Math.max((sum / scaleTo) * 100, 6) : 100
  const current = active != null ? segments[active] : null

  return (
    <div className={`strip-wrap ${compact ? 'is-compact' : ''}`}>
      <div className="strip" style={{ width: `${width}%` }} role="list" aria-label="Setup journey">
        {segments.map((segment, i) => {
          const Tag = onSelect ? 'button' : 'span'
          return (
            <Tag
              key={segment.step_id || i}
              role="listitem"
              type={onSelect ? 'button' : undefined}
              className={`seg seg-${segment.owner} ${active === i ? 'is-active' : ''}`}
              style={{ flexGrow: weightOf(segment), '--i': i }}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              onClick={onSelect ? () => onSelect(segment.step_id) : undefined}
              aria-label={`Step ${i + 1}: ${segment.label}, ${OWNER[segment.owner].short}, ${formatRange(segment.min_minutes, segment.max_minutes)}`}
            >
              {!compact && <span className="seg-num">{i + 1}</span>}
            </Tag>
          )
        })}
      </div>

      {!compact && (
        <div className="strip-readout" aria-live="polite">
          {current ? (
            <>
              <span className={`readout-owner owner-${current.owner}`}>{OWNER[current.owner].short}</span>
              <strong>
                {active + 1}. {current.label}
              </strong>
              <span className="muted">{formatRange(current.min_minutes, current.max_minutes)}</span>
            </>
          ) : (
            <span className="muted">{labels ?? 'Hover a block to see the step. Width shows time on a compressed scale, so short steps stay visible.'}</span>
          )}
        </div>
      )}
    </div>
  )
}
