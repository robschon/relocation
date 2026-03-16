import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getLocations,
  createLocation,
  deleteLocation,
  getRankings,
  startLocationFullResearch,
  getFullResearchJob,
} from '../api'
import { sortLocationsByOverallRank } from '../utils/rankings'
import Spinner from '../components/Spinner'

function matchingRanking(location, rankings) {
  return rankings.find(
    (ranking) =>
      ranking.location_name.trim().toLowerCase() === location.name.trim().toLowerCase() &&
      ranking.country.trim().toLowerCase() === location.country.trim().toLowerCase(),
  )
}

function normalizeCountryName(value) {
  return (value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function buildCountryCodeByName() {
  if (typeof Intl === 'undefined' || typeof Intl.DisplayNames === 'undefined') {
    return {}
  }

  const displayNames = new Intl.DisplayNames(['en'], { type: 'region' })
  const map = {}

  for (let first = 65; first <= 90; first += 1) {
    for (let second = 65; second <= 90; second += 1) {
      const code = String.fromCharCode(first, second)
      const label = displayNames.of(code)
      if (label && label !== code) {
        const normalizedLabel = normalizeCountryName(label)
        if (!map[normalizedLabel]) {
          map[normalizedLabel] = code
        }
      }
    }
  }

  const aliases = {
    usa: 'US',
    us: 'US',
    france: 'FR',
    vietnam: 'VN',
    'viet nam': 'VN',
    'u s a': 'US',
    uk: 'GB',
    'u k': 'GB',
    england: 'GB',
    scotland: 'GB',
    wales: 'GB',
    'czech republic': 'CZ',
    'ivory coast': 'CI',
    'congo brazzaville': 'CG',
    'congo kinshasa': 'CD',
    'south korea': 'KR',
    'north korea': 'KP',
    russia: 'RU',
    bolivia: 'BO',
    moldova: 'MD',
    laos: 'LA',
    syria: 'SY',
    tanzania: 'TZ',
    venezuela: 'VE',
    palestine: 'PS',
    kosovo: 'XK',
  }
  for (const [key, code] of Object.entries(aliases)) {
    map[key] = code
  }

  return map
}

function codeToFlagEmoji(code) {
  if (!/^[A-Z]{2}$/.test(code)) return '🌍'
  return String.fromCodePoint(...code.split('').map((char) => 127397 + char.charCodeAt(0)))
}

function scoreBadgeClasses(score) {
  if (score === null || Number.isNaN(score)) {
    return 'bg-gray-100 text-gray-600'
  }
  if (score >= 8.5) return 'bg-emerald-100 text-emerald-800'
  if (score >= 7) return 'bg-blue-100 text-blue-800'
  if (score >= 5.5) return 'bg-amber-100 text-amber-800'
  return 'bg-rose-100 text-rose-800'
}

function formatFullResearchBadge(value) {
  if (!value) return null
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) return null
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(parsed)
}

function formatFullResearchTitle(value) {
  if (!value) return ''
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed)
}

export default function Locations() {
  const [locations, setLocations] = useState([])
  const [researchJobs, setResearchJobs] = useState({})
  const [activeLogLocationId, setActiveLogLocationId] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [countryFilter, setCountryFilter] = useState('')
  const [form, setForm] = useState({ name: '', country: '', region: '', population: '', description: '' })
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const countryCodeByName = useMemo(() => buildCountryCodeByName(), [])

  const flagEmojiForCountry = (country) => {
    const normalized = normalizeCountryName(country)
    const code = countryCodeByName[normalized]
    if (code) return codeToFlagEmoji(code)

    const segment = normalized.split('/')[0].trim()
    return codeToFlagEmoji(countryCodeByName[segment] || '')
  }

  const load = async () => {
    const [locs, rankings] = await Promise.all([getLocations(), getRankings('combined')])
    const sorted = sortLocationsByOverallRank(locs, rankings)
    setLocations(
      sorted.map((loc) => {
        const ranking = matchingRanking(loc, rankings)
        return {
          ...loc,
          overall_score: ranking?.overall_score ?? null,
        }
      }),
    )
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    await createLocation({
      ...form,
      population: form.population ? Number(form.population) : null,
      region: form.region || null,
      description: form.description || null,
    })
    setForm({ name: '', country: '', region: '', population: '', description: '' })
    setShowForm(false)
    load()
  }

  const handleDelete = async (id, name) => {
    if (!confirm(`Delete "${name}"? This will also delete all scores, research, and pros/cons for this location.`)) return
    await deleteLocation(id)
    load()
  }

  const pollFullResearchJob = async (locationId, jobId) => {
    while (true) {
      const job = await getFullResearchJob(jobId)
      setResearchJobs((prev) => ({ ...prev, [locationId]: job }))
      if (job.status === 'completed' || job.status === 'failed') break
      await new Promise((resolve) => setTimeout(resolve, 2000))
    }

    const finalJob = await getFullResearchJob(jobId)
    setResearchJobs((prev) => ({ ...prev, [locationId]: finalJob }))
    if (finalJob.status === 'completed') {
      load()
    }
  }

  const handleRunFullResearch = async (loc, e) => {
    e.stopPropagation()
    const current = researchJobs[loc.id]
    if (current && (current.status === 'running' || current.status === 'queued')) return

    try {
      const job = await startLocationFullResearch(loc.id, { forceResearch: true })
      setResearchJobs((prev) => ({ ...prev, [loc.id]: job }))
      setActiveLogLocationId(loc.id)
      void pollFullResearchJob(loc.id, job.id)
    } catch (error) {
      setResearchJobs((prev) => ({
        ...prev,
        [loc.id]: {
          id: null,
          status: 'failed',
          error: error.message || 'Failed to start full research job',
        },
      }))
      setActiveLogLocationId(loc.id)
    }
  }

  const activeLogLocation = activeLogLocationId
    ? locations.find((loc) => loc.id === activeLogLocationId)
    : null
  const activeLogJob = activeLogLocationId ? researchJobs[activeLogLocationId] : null
  const uniqueCountries = useMemo(
    () => Array.from(new Set(locations.map((loc) => loc.country).filter(Boolean))).sort((a, b) => a.localeCompare(b)),
    [locations],
  )
  const filteredLocations = useMemo(() => {
    if (!countryFilter) return locations
    const normalizedFilter = normalizeCountryName(countryFilter)
    return locations.filter((loc) => normalizeCountryName(loc.country) === normalizedFilter)
  }, [locations, countryFilter])

  if (loading) return <Spinner label="Loading locations..." />

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Locations</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : 'Add Location'}
        </button>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <label htmlFor="country-filter" className="text-sm text-gray-600">Country</label>
        <select
          id="country-filter"
          value={countryFilter}
          onChange={(e) => setCountryFilter(e.target.value)}
          className="border rounded px-3 py-2 text-sm bg-white"
        >
          <option value="">All countries</option>
          {uniqueCountries.map((country) => (
            <option key={country} value={country}>{country}</option>
          ))}
        </select>
        {countryFilter && (
          <button
            onClick={() => setCountryFilter('')}
            className="px-2 py-1 rounded text-xs border bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
          >
            Clear
          </button>
        )}
        <span className="text-xs text-gray-500">{filteredLocations.length} of {locations.length} shown</span>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <input
            required placeholder="Name" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required placeholder="Country" value={form.country}
            onChange={(e) => setForm({ ...form, country: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            placeholder="Region" value={form.region}
            onChange={(e) => setForm({ ...form, region: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            placeholder="Population" type="number" value={form.population}
            onChange={(e) => setForm({ ...form, population: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <textarea
            placeholder="Description" value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="border rounded px-3 py-2 text-sm sm:col-span-2"
            rows={2}
          />
          <button type="submit" className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 sm:col-span-2">
            Create Location
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredLocations.map((loc) => {
          const job = researchJobs[loc.id]
          const isRunning = job?.status === 'running' || job?.status === 'queued'
          const flagEmoji = flagEmojiForCountry(loc.country)
          const fullResearchBadge = formatFullResearchBadge(loc.full_research_ran_at)
          const fullResearchTitle = formatFullResearchTitle(loc.full_research_ran_at)
          return (
            <div
              key={loc.id}
              className="relative overflow-hidden bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => navigate(`/locations/${loc.id}`)}
            >
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <span className="select-none text-[12rem] leading-none opacity-10">{flagEmoji}</span>
              </div>
              <div className="relative z-10">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-lg">{loc.name}</h3>
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-semibold ${scoreBadgeClasses(loc.overall_score)}`}
                      >
                        {loc.overall_score !== null ? loc.overall_score.toFixed(1) : 'Unranked'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500">{loc.country}{loc.region ? `, ${loc.region}` : ''}</p>
                    {fullResearchBadge && (
                      <div
                        className="mt-2 inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700"
                        title={`Last full research run: ${fullResearchTitle}`}
                      >
                        Full research {fullResearchBadge}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <button
                      onClick={(e) => handleRunFullResearch(loc, e)}
                      disabled={isRunning}
                      className={`px-2 py-1 rounded text-xs border ${isRunning ? 'bg-blue-50 text-blue-500 border-blue-200 cursor-not-allowed' : 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700'}`}
                    >
                      {isRunning ? 'Researching...' : 'Run Full Research'}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/research?location_id=${loc.id}`)
                      }}
                      className="px-2 py-1 rounded text-xs border bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
                    >
                      View Research
                    </button>
                    {job && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setActiveLogLocationId(activeLogLocationId === loc.id ? null : loc.id)
                        }}
                        className="px-2 py-1 rounded text-xs border bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
                      >
                        {activeLogLocationId === loc.id ? 'Hide Log' : 'View Log'}
                      </button>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(loc.id, loc.name) }}
                      className="text-red-400 hover:text-red-600 text-sm"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                {loc.population && (
                  <p className="text-xs text-gray-400 mt-1">Pop. {loc.population.toLocaleString()}</p>
                )}
                {loc.description && (
                  <p className="text-sm text-gray-600 mt-2 line-clamp-4">{loc.description}</p>
                )}
                {job?.status === 'running' && (
                  <p className="text-xs text-blue-600 mt-2">Running full routine{job.step ? `: ${job.step}` : '...'}</p>
                )}
                {job?.status === 'queued' && (
                  <p className="text-xs text-blue-600 mt-2">Queued full routine...</p>
                )}
                {job?.status === 'completed' && (
                  <p className="text-xs text-green-600 mt-2">Full routine completed.</p>
                )}
                {job?.status === 'failed' && (
                  <p className="text-xs text-red-600 mt-2">Full routine failed{job.error ? `: ${job.error}` : '.'}</p>
                )}
              </div>
            </div>
          )
        })}
        {locations.length === 0 && (
          <div className="col-span-3 text-center text-gray-400 py-12">
            No locations yet. Click "Add Location" to get started.
          </div>
        )}
        {locations.length > 0 && filteredLocations.length === 0 && (
          <div className="col-span-3 text-center text-gray-400 py-12">
            No locations match the selected country filter.
          </div>
        )}
      </div>

      {activeLogLocation && activeLogJob && (
        <div className="fixed right-4 bottom-4 z-50 w-[min(720px,96vw)] max-h-[72vh] bg-white border border-gray-200 rounded-lg shadow-2xl flex flex-col">
          <div className="px-4 py-3 border-b border-gray-200 flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">
                Full Research Log: {activeLogLocation.name}
              </h3>
              <p className="text-xs text-gray-500">
                Status: {activeLogJob.status}
                {activeLogJob.step ? ` • Step: ${activeLogJob.step}` : ''}
              </p>
            </div>
            <button
              onClick={() => setActiveLogLocationId(null)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Close
            </button>
          </div>

          <div className="p-4 overflow-auto bg-gray-950 text-gray-100 text-xs font-mono leading-relaxed whitespace-pre-wrap">
            {activeLogJob.output && activeLogJob.output.length > 0
              ? activeLogJob.output.join('\n')
              : 'No output yet. The job log will appear here as steps complete.'}
            {activeLogJob.error ? `\n\n[error] ${activeLogJob.error}` : ''}
          </div>
        </div>
      )}
    </div>
  )
}
