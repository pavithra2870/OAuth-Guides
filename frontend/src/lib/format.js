// Labels, colours and time formatting shared across the UI.

export const DIFFICULTY = {
  easy: { label: 'Easy', tone: 'ok', blurb: 'Self-serve, no review' },
  medium: { label: 'Medium', tone: 'warn', blurb: 'Review needed to go public' },
  hard: { label: 'Hard', tone: 'hard', blurb: 'Mandatory review, weeks of waiting' },
  gated: { label: 'Gated', tone: 'bad', blurb: 'Access by application or partnership' },
}

export const OWNER = {
  agent: { label: 'AI can draft', short: 'AI', verb: 'AI writes the text, you use it' },
  you: { label: 'You must do', short: 'You', verb: 'Only you can do these' },
  provider: { label: 'Waiting on provider', short: 'Waiting', verb: 'Out of your hands' },
}

export const EVIDENCE = {
  tested: { label: 'Tested', hint: 'Someone actually did this and it worked.' },
  documented: { label: 'In official docs', hint: 'The exact wording was found on the provider’s own site.' },
  reported: { label: 'Reported', hint: 'Found only in a forum or third-party page, not in official docs.' },
  inferred: { label: 'Our estimate', hint: 'No source states this directly. Treat it as a best guess.' },
}

export const PHASE = { setup: 'Setup', submit: 'Submit', review: 'Review', launch: 'Launch' }

const MIN = 1
const HOUR = 60
const DAY = 1440
const WEEK = 10080

function unitFor(maxMinutes) {
  if (maxMinutes < HOUR) return ['min', MIN]
  if (maxMinutes < DAY) return ['hr', HOUR]
  if (maxMinutes < 14 * DAY) return ['day', DAY]
  return ['week', WEEK]
}

// Estimates shouldn't look more precise than they are: whole numbers, or halves below 10.
function round(n) {
  return String(n < 10 ? Math.round(n * 2) / 2 : Math.round(n))
}

function pluralize(unit, n) {
  if (unit === 'min') return 'min'
  return n === 1 ? unit : `${unit}s`
}

/** 5–15 min, 1–2 hrs, 6–12 weeks. Returns "none" for zero. */
export function formatRange(minMinutes, maxMinutes) {
  if (!maxMinutes) return 'none'
  const [unit, divisor] = unitFor(maxMinutes)
  const low = round(minMinutes / divisor)
  const high = round(maxMinutes / divisor)
  const label = pluralize(unit, maxMinutes / divisor)
  return low === high ? `${high} ${label}` : `${low}–${high} ${label}`
}

/** A step's duration, e.g. "10–30 min". */
export function stepRange(step) {
  const unit = { minutes: 1, hours: 60, days: 1440, weeks: 10080 }[step.duration.unit] || 1
  return formatRange(step.duration.low * unit, step.duration.high * unit)
}

export function totalSpan(timeline) {
  return {
    min_minutes: timeline.hands_on.min_minutes + timeline.waiting.min_minutes,
    max_minutes: timeline.hands_on.max_minutes + timeline.waiting.max_minutes,
  }
}

export function formatDate(iso) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const days = Math.floor((Date.now() - date.getTime()) / 86400000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days} days ago`
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
