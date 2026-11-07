// Turn a guide into shareable Markdown, and build the prompt a developer can hand to their own agent.

import { DIFFICULTY, EVIDENCE, OWNER, formatRange, stepRange, totalSpan } from './format.js'

export function guideToMarkdown(guide, url) {
  const total = totalSpan(guide.timeline)
  const lines = [
    `# ${guide.app_name}: OAuth app setup guide`,
    '',
    `**Difficulty:** ${DIFFICULTY[guide.difficulty.level].label}. ${guide.difficulty.headline}`,
    `**Plan for:** ${formatRange(total.min_minutes, total.max_minutes)} (hands-on ${formatRange(guide.timeline.hands_on.min_minutes, guide.timeline.hands_on.max_minutes)}, waiting ${formatRange(guide.timeline.waiting.min_minutes, guide.timeline.waiting.max_minutes)})`,
    '',
    guide.summary,
    '',
    '## Steps',
    ...guide.steps.map((s, i) => {
      const parts = [`${i + 1}. **${s.title}** (${OWNER[s.owner].short}, ${stepRange(s)})`, `   ${s.detail}`]
      if (s.link) parts.push(`   ${s.link}`)
      return parts.join('\n')
    }),
    '',
    '## Requirements',
    ...guide.requirements.map((r) => `- ${r.required ? '' : '(optional) '}**${r.label}**: ${r.detail}`),
    '',
    '## Gotchas',
    ...guide.gotchas.map((g) => `- **${g.title}**: ${g.detail}`),
    '',
    '## If you get stuck',
    ...guide.blockers.map((b) => `- **${b.problem}** ${b.why} Fix: ${b.fix}`),
    '',
    '## How much to trust this',
    ...Object.entries(guide.stats.counts)
      .filter(([, n]) => n > 0)
      .map(([level, n]) => `- ${n} claims: ${EVIDENCE[level].label}`),
    ...guide.stats.unverified.map((u) => `- Not verified: ${u}`),
    '',
    '## Sources',
    ...guide.sources.map((s) => `- [${s.id}] ${s.title || s.url} (${s.kind}) ${s.url}`),
    '',
    url ? `Guide: ${url}` : '',
  ]
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n'
}

export function agentPrompt(guide, step) {
  return [
    `I'm registering an OAuth app with ${guide.app_name} so users of my AI-agent product can connect their accounts.`,
    `Help me with this step: "${step.title}".`,
    step.agent_assist ? `What I need from you: ${step.agent_assist}` : '',
    step.detail ? `Context: ${step.detail}` : '',
    step.link ? `Reference: ${step.link}` : '',
    'Keep it concrete and ready to paste into the provider’s form. Flag anything you are unsure about.',
  ]
    .filter(Boolean)
    .join('\n')
}
