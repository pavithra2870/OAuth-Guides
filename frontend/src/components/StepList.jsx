import { useState } from 'react'
import { useCopy } from '../hooks/hooks.js'
import { OWNER, PHASE, stepRange } from '../lib/format.js'
import { agentPrompt } from '../lib/markdown.js'
import { EvidenceBadge } from './Badges.jsx'

function Step({ guide, step, index, done, isNext, onToggle }) {
  const [open, setOpen] = useState(isNext)
  const [copied, copy] = useCopy()
  const waiting = step.owner === 'provider'

  return (
    <li id={`step-${step.id}`} className={`step step-${step.owner} ${done ? 'is-done' : ''} ${isNext ? 'is-next' : ''}`}>
      <div className="step-rail">
        {waiting ? (
          <span className="step-hourglass" aria-hidden="true">
            ⏳
          </span>
        ) : (
          <input
            type="checkbox"
            className="step-check"
            checked={done}
            onChange={() => onToggle(step.id)}
            aria-label={`Mark “${step.title}” as done`}
          />
        )}
        <span className="step-line" />
      </div>

      <div className="step-body">
        <button className="step-head" type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <span className="step-num label">{String(index + 1).padStart(2, '0')}</span>
          <span className="step-title">{step.title}</span>
          {isNext && <span className="tag tag-next">Next</span>}
          <span className={`tag tag-${step.owner}`}>{OWNER[step.owner].short}</span>
          <span className="step-time">{stepRange(step)}</span>
          <span className="chevron" aria-hidden="true">
            {open ? '−' : '+'}
          </span>
        </button>

        {open && (
          <div className="step-detail rise">
            <p>{step.detail}</p>

            {step.agent_assist && (
              <div className="assist">
                <span className="label">What AI can draft</span>
                <p>{step.agent_assist}</p>
                <button type="button" className="btn btn-small" onClick={() => copy(agentPrompt(guide, step), step.id)}>
                  {copied === step.id ? 'Copied ✓' : 'Copy as AI prompt'}
                </button>
              </div>
            )}

            <div className="step-foot">
              <span className="label">{PHASE[step.phase]}</span>
              <EvidenceBadge evidence={step.evidence} sources={guide.sources} />
              {step.link && (
                <a className="step-link" href={step.link} target="_blank" rel="noreferrer noopener">
                  Open page ↗
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </li>
  )
}

export default function StepList({ guide, done, onToggle }) {
  const nextId = guide.steps.find((s) => s.owner !== 'provider' && !done.has(s.id))?.id
  const doable = guide.steps.filter((s) => s.owner !== 'provider')
  const finished = doable.filter((s) => done.has(s.id)).length

  return (
    <div>
      <div className="progress" role="status" aria-label={`${finished} of ${doable.length} steps done`}>
        <div className="progress-bar">
          <span style={{ width: `${doable.length ? (finished / doable.length) * 100 : 0}%` }} />
        </div>
        <span className="label">
          {finished} of {doable.length} steps done · saved in this browser
        </span>
      </div>
      <ol className="steps-list">
        {guide.steps.map((step, i) => (
          <Step key={step.id} guide={guide} step={step} index={i} done={done.has(step.id)} isNext={step.id === nextId} onToggle={onToggle} />
        ))}
      </ol>
    </div>
  )
}
