// Library helpers: summaries, matching what a visitor typed to a guide we already have.

export function normalize(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .replace(/[/?#].*$/, '')
    .replace(/[^a-z0-9]/g, '')
}

/** Same shape the API returns from /api/guides, built from a full guide. */
export function summarize(guide, origin = 'generated') {
  return {
    slug: guide.slug,
    app_name: guide.app_name,
    domain: guide.domain,
    origin,
    difficulty: guide.difficulty.level,
    headline: guide.difficulty.headline,
    segments: guide.timeline.segments,
    hands_on: guide.timeline.hands_on,
    waiting: guide.timeline.waiting,
    agent_share: guide.timeline.agent_share,
    composio: guide.composio.status,
    confidence: guide.stats.confidence,
    researched_at: guide.meta.researched_at,
  }
}

function keys(entry) {
  const domainLabel = (entry.domain || '').split('.')[0]
  return [normalize(entry.app_name), normalize(entry.slug), normalize(domainLabel)].filter(Boolean)
}

/** Guides whose name, slug or site start with (or equal) what was typed. */
export function matchGuides(guides, query, limit = 6) {
  const q = normalize(query)
  if (q.length < 1) return []
  return guides
    .map((g) => {
      const ks = keys(g)
      const score = ks.includes(q) ? 2 : ks.some((k) => k.startsWith(q)) ? 1 : ks.some((k) => q.length >= 3 && k.includes(q)) ? 0.5 : 0
      return { g, score }
    })
    .filter((m) => m.score > 0)
    .sort((a, b) => b.score - a.score || a.g.app_name.localeCompare(b.g.app_name))
    .slice(0, limit)
    .map((m) => m.g)
}

export function findExact(guides, query) {
  const q = normalize(query)
  return guides.find((g) => keys(g).includes(q)) || null
}
