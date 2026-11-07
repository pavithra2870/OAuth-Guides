// Journey-strip geometry. Durations span minutes to weeks, so block widths use a square-root
// scale: a 10-minute step stays visible next to a 6-week wait, while the wait still dominates.

const MIN_WEIGHT = 3

export function weightOf(segment) {
  return Math.max(Math.sqrt((segment.min_minutes + segment.max_minutes) / 2), MIN_WEIGHT)
}

export function totalWeight(segments) {
  return segments.reduce((sum, s) => sum + weightOf(s), 0)
}

const UNIT_MINUTES = { minutes: 1, hours: 60, days: 1440, weeks: 10080 }

/** A step's duration as [min, max] minutes. */
export function stepMinutes(step) {
  const factor = UNIT_MINUTES[step.duration.unit] || 1
  return [step.duration.low * factor, step.duration.high * factor]
}
