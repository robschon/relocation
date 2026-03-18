/**
 * Maps a score to a hex color on a red → yellow → green gradient.
 * minScore = red (#ef4444), midpoint = yellow (#eab308), maxScore = green (#22c55e)
 */
export function scoreToColor(score, minScore = 0, maxScore = 10) {
  const range = maxScore - minScore
  const t = range === 0 ? 0.5 : Math.max(0, Math.min(1, (score - minScore) / range))

  let r, g, b
  if (t < 0.5) {
    // red → yellow
    const s = t * 2
    r = Math.round(239 + (234 - 239) * s)
    g = Math.round(68 + (179 - 68) * s)
    b = Math.round(68 + (8 - 68) * s)
  } else {
    // yellow → green
    const s = (t - 0.5) * 2
    r = Math.round(234 + (34 - 234) * s)
    g = Math.round(179 + (197 - 179) * s)
    b = Math.round(8 + (94 - 8) * s)
  }

  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}
