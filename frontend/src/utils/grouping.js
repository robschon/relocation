// Group ranking rows by region (geocoder admin1, e.g. "Canary Islands", "Hawaii") or by
// country, so one cluster of similar places doesn't crowd everything else out of the top.

export const GROUP_MODES = [
  { value: 'none', label: 'None' },
  { value: 'region', label: 'Region' },
  { value: 'country', label: 'Country' },
]

// The geocoder sometimes names the same admin1 two ways; map variants onto one label.
const ADMIN1_ALIASES = {
  'illes balears': 'Balearic Islands',
}

// Prefixes the geocoder puts on some admin1 names; dropped for display only.
const ADMIN1_PREFIXES = /^(estado de|departamento de|provincia de)\s+/i

const norm = (s) => (s ?? '').trim().toLowerCase()

export function regionName(admin1) {
  const trimmed = (admin1 ?? '').trim()
  if (!trimmed) return null
  return ADMIN1_ALIASES[norm(trimmed)] ?? trimmed.replace(ADMIN1_PREFIXES, '')
}

// `location` is the full location record (has admin1); falls back to the ranking row.
export function groupFor(ranking, location, mode) {
  const country = (location?.country ?? ranking.country ?? '').trim()
  if (mode === 'country') {
    return { key: `c::${norm(country)}`, label: country }
  }
  // Region mode: places with no admin1 fall back to their country.
  const region = regionName(location?.admin1)
  if (!region) return { key: `c::${norm(country)}`, label: country }
  return { key: `r::${norm(country)}::${norm(region)}`, label: `${region}, ${country}` }
}

// Groups `rows` (already in display order) and keeps that order: each group sits where its
// best row sits, and rows within a group stay in display order. Returns
// [{ key, label, rows: [...] }], where rows[0] is the group's representative.
export function groupRankings(rows, locationById, mode) {
  if (mode === 'none') {
    return rows.map((r) => ({ key: `l::${r.location_id}`, label: r.country, rows: [r] }))
  }
  const groups = new Map()
  for (const r of rows) {
    const { key, label } = groupFor(r, locationById[r.location_id], mode)
    if (!groups.has(key)) groups.set(key, { key, label, rows: [] })
    groups.get(key).rows.push(r)
  }
  return [...groups.values()]
}
