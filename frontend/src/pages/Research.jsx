import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getResearch, createResearch, deleteResearch, getLocations, getCategories } from '../api'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import { toast } from 'sonner'

const strictCategoryNames = new Set(['Visa / residency feasibility', 'Tax implications'])
const todayIso = new Date().toISOString().slice(0, 10)

const emptyForm = {
  location_id: '',
  location_name_text: '',
  category_id: '',
  content: '',
  source: '',
  source_urls_text: '',
  source_published_at: '',
  source_checked_at: todayIso,
  verification_status: 'needs_review',
  confidence: '',
}

function parseSourceUrls(raw) {
  return raw
    .split(/[\n,\s]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0 && /^https?:\/\//i.test(item))
}

function formatDateInput(value) {
  if (!value) return ''
  return String(value).slice(0, 10)
}

function normalizeSourceUrls(value) {
  if (Array.isArray(value)) return value
  if (typeof value !== 'string' || value.trim() === '') return []
  return value
    .split(/[\n,\s]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0 && /^https?:\/\//i.test(item))
}

function sortLocationsAlphabetically(rows) {
  return [...rows].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
}

export default function Research() {
  const [searchParams] = useSearchParams()
  const [research, setResearch] = useState([])
  const [locations, setLocations] = useState([])
  const [categories, setCategories] = useState([])
  const [filterLocation, setFilterLocation] = useState('')
  const [filterLocationText, setFilterLocationText] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ ...emptyForm })
  const [expanded, setExpanded] = useState({})
  const [error, setError] = useState('')

  const hydratePage = async (params, { cancelRef } = {}) => {
    const [researchRes, locationsRes, categoriesRes] = await Promise.allSettled([
      getResearch(params),
      getLocations({ fully_scored_only: true }),
      getCategories(),
    ])

    if (cancelRef?.cancelled) return

    let errorMessage = ''
    const hasResearch = researchRes.status === 'fulfilled'

    const locationsValue = locationsRes.status === 'fulfilled' ? locationsRes.value : []
    const allowedLocationIds = new Set(locationsValue.map((location) => location.id))

    if (hasResearch) {
      const normalized = researchRes.value.map((entry) => ({
        ...entry,
        source_urls: normalizeSourceUrls(entry.source_urls),
      }))
      setResearch(
        locationsRes.status === 'fulfilled'
          ? normalized.filter((entry) => entry.location_id == null || allowedLocationIds.has(entry.location_id))
          : normalized,
      )
    } else {
      setResearch([])
      errorMessage = researchRes.reason?.message || 'Failed to load research.'
    }

    const categoriesValue = categoriesRes.status === 'fulfilled' ? categoriesRes.value : []

    if (locationsRes.status === 'fulfilled') {
      setLocations(sortLocationsAlphabetically(locationsValue))
    }
    if (categoriesRes.status === 'fulfilled') {
      setCategories(categoriesValue)
    }

    const auxErrors = [locationsRes, categoriesRes].filter((result) => result.status === 'rejected')
    if (auxErrors.length > 0 && hasResearch) {
      errorMessage = 'Some supporting data failed to load, but research entries are shown.'
    }

    setError(errorMessage)
    return hasResearch
  }

  const load = async ({ cancelRef, retries = 1 } = {}) => {
    setError('')
    setIsLoading(true)
    const params = {}
    if (filterLocation) params.location_id = filterLocation
    if (filterCategory) params.category_id = filterCategory
    let loaded = await hydratePage(params, { cancelRef })

    for (let attempt = 0; !loaded && attempt < retries; attempt += 1) {
      if (cancelRef?.cancelled) break
      await new Promise((resolve) => setTimeout(resolve, 800 * (attempt + 1)))
      if (cancelRef?.cancelled) break
      loaded = await hydratePage(params, { cancelRef })
    }

    if (!cancelRef?.cancelled) {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    const cancelRef = { cancelled: false }
    load({ cancelRef, retries: 2 })

    return () => {
      cancelRef.cancelled = true
    }
  }, [filterLocation, filterCategory])

  useEffect(() => {
    const locationIdParam = searchParams.get('location_id')
    if (locationIdParam && /^\d+$/.test(locationIdParam)) {
      setFilterLocation(locationIdParam)
    }
    const categoryIdParam = searchParams.get('category_id')
    if (categoryIdParam && /^\d+$/.test(categoryIdParam)) {
      setFilterCategory(categoryIdParam)
    }
  }, [searchParams])

  useEffect(() => {
    if (!filterLocation) return
    const selected = locations.find((location) => String(location.id) === String(filterLocation))
    if (selected && selected.name !== filterLocationText) {
      setFilterLocationText(selected.name)
    }
  }, [filterLocation, filterLocationText, locations])

  const findLocationByName = (name) =>
    locations.find((location) => location.name.toLowerCase() === name.trim().toLowerCase())

  const handleFilterLocationTextChange = (value) => {
    setFilterLocationText(value)
    const normalized = value.trim()
    if (!normalized) {
      setFilterLocation('')
      return
    }
    const selected = findLocationByName(normalized)
    setFilterLocation(selected ? String(selected.id) : '')
  }

  const handleFormLocationTextChange = (value) => {
    const selected = findLocationByName(value)
    setForm((prev) => ({
      ...prev,
      location_name_text: value,
      location_id: selected ? String(selected.id) : '',
    }))
  }

  const selectedCategory = categories.find((category) => category.id === Number(form.category_id))
  const requiresStrictEvidence = !!selectedCategory && strictCategoryNames.has(selectedCategory.name)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!form.location_id) {
      setError('Please select a valid location from the location list.')
      return
    }

    const sourceUrls = parseSourceUrls(form.source_urls_text)
    const confidence = form.confidence === '' ? null : Number(form.confidence)

    if (confidence !== null && Number.isNaN(confidence)) {
      setError('Confidence must be a number between 0 and 1.')
      return
    }

    if (requiresStrictEvidence) {
      if (!form.source.trim()) {
        setError('Visa/tax research requires a source summary.')
        return
      }
      if (/general knowledge/i.test(form.source)) {
        setError('Visa/tax research cannot use "general knowledge" as the source basis.')
        return
      }
      if (sourceUrls.length === 0) {
        setError('Visa/tax research requires at least one source URL.')
        return
      }
      if (!form.source_checked_at) {
        setError('Visa/tax research requires source checked date.')
        return
      }
      if (confidence === null) {
        setError('Visa/tax research requires confidence.')
        return
      }
    }

    try {
      await createResearch({
        location_id: Number(form.location_id),
        category_id: form.category_id ? Number(form.category_id) : null,
        content: form.content,
        source: form.source.trim() || null,
        source_urls: sourceUrls.length > 0 ? sourceUrls : null,
        source_published_at: form.source_published_at || null,
        source_checked_at: form.source_checked_at || null,
        verification_status: form.verification_status,
        confidence,
      })
      toast.success('Research entry saved')
      setForm({ ...emptyForm, source_checked_at: todayIso })
      setShowForm(false)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this research entry?')) return
    setError('')
    try {
      await deleteResearch(id)
      toast.success('Research entry deleted')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const locName = (id) => locations.find((location) => location.id === id)?.name || `#${id}`
  // Country-level research (e.g. visa/residency) has no location_id, only a country_code.
  const subjectName = (entry) =>
    entry.location_id == null
      ? `${locations.find((location) => location.country_code === entry.country_code)?.country || entry.country_code} (country)`
      : locName(entry.location_id)
  const catName = (id) => categories.find((category) => category.id === id)?.name || ''

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Research</h1>
        <button
          onClick={() => {
            setError('')
            setShowForm(!showForm)
            if (!showForm) setForm({ ...emptyForm, source_checked_at: todayIso })
          }}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : 'Add Research'}
        </button>
      </div>

      {error && <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="flex gap-3 mb-4">
        <input
          list="research-locations-filter"
          value={filterLocationText}
          onChange={(e) => handleFilterLocationTextChange(e.target.value)}
          placeholder="All Locations (type to search)"
          className="border rounded px-3 py-1 text-sm min-w-[260px]"
        />
        <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} className="border rounded px-3 py-1 text-sm">
          <option value="">All Categories</option>
          {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
        </select>
        {(filterLocation || filterLocationText) && (
          <button
            onClick={() => {
              setFilterLocation('')
              setFilterLocationText('')
            }}
            className="text-xs text-gray-600 hover:text-gray-900 border rounded px-2"
            type="button"
          >
            Clear
          </button>
        )}
      </div>
      <datalist id="research-locations-filter">
        {locations.map((location) => <option key={location.id} value={location.name} />)}
      </datalist>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 mb-6 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              list="research-locations-form"
              required
              placeholder="Select Location"
              value={form.location_name_text}
              onChange={(e) => handleFormLocationTextChange(e.target.value)}
              className="border rounded px-3 py-2 text-sm w-full"
            />
            <select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })} className="border rounded px-3 py-2 text-sm">
              <option value="">Category (optional)</option>
              {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select>
          </div>
          <datalist id="research-locations-form">
            {locations.map((location) => <option key={location.id} value={location.name} />)}
          </datalist>
          <textarea
            required
            placeholder="Research content..."
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            className="border rounded px-3 py-2 text-sm w-full"
            rows={4}
          />
          <input
            placeholder="Source summary"
            value={form.source}
            onChange={(e) => setForm({ ...form, source: e.target.value })}
            className="border rounded px-3 py-2 text-sm w-full"
          />
          <textarea
            placeholder="Source URLs (one per line)"
            value={form.source_urls_text}
            onChange={(e) => setForm({ ...form, source_urls_text: e.target.value })}
            className="border rounded px-3 py-2 text-sm w-full"
            rows={3}
          />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <input
              type="date"
              placeholder="Source published date"
              value={form.source_published_at}
              onChange={(e) => setForm({ ...form, source_published_at: e.target.value })}
              className="border rounded px-3 py-2 text-sm"
            />
            <input
              type="date"
              value={form.source_checked_at}
              onChange={(e) => setForm({ ...form, source_checked_at: e.target.value })}
              className="border rounded px-3 py-2 text-sm"
            />
            <select
              value={form.verification_status}
              onChange={(e) => setForm({ ...form, verification_status: e.target.value })}
              className="border rounded px-3 py-2 text-sm"
            >
              <option value="verified">Verified</option>
              <option value="needs_review">Needs Review</option>
              <option value="stale">Stale</option>
            </select>
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              placeholder="Confidence (0-1)"
              value={form.confidence}
              onChange={(e) => setForm({ ...form, confidence: e.target.value })}
              className="border rounded px-3 py-2 text-sm"
            />
          </div>
          {requiresStrictEvidence && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              This category requires dated citations, source URLs, checked date, and confidence.
            </p>
          )}
          <button type="submit" className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700">
            Save Research
          </button>
        </form>
      )}

      <div className="space-y-3">
        {isLoading && research.length === 0 && <Spinner label="Loading research..." />}
        {research.map((entry) => {
          const isLong = entry.content.length > 200
          const isExpanded = expanded[entry.id]
          return (
            <div key={entry.id} className="bg-white rounded-lg shadow p-4">
              <div className="flex items-start justify-between">
                <div className="flex gap-2 mb-2">
                  <span className="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded">{subjectName(entry)}</span>
                  {entry.category_id && <span className="bg-purple-100 text-purple-800 text-xs px-2 py-0.5 rounded">{catName(entry.category_id)}</span>}
                </div>
                <button onClick={() => handleDelete(entry.id)} className="text-red-400 hover:text-red-600 text-sm">Delete</button>
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">
                {isLong && !isExpanded ? `${entry.content.slice(0, 200)}...` : entry.content}
              </p>
              {isLong && (
                <button
                  onClick={() => setExpanded({ ...expanded, [entry.id]: !isExpanded })}
                  className="text-xs text-blue-600 hover:underline mt-1"
                >
                  {isExpanded ? 'Show less' : 'Show more'}
                </button>
              )}
              {entry.source && <p className="text-xs text-blue-500 mt-2">Source: {entry.source}</p>}
              {(entry.source_urls || []).length > 0 && (
                <div className="mt-1 text-xs">
                  <span className="text-gray-500">Source URLs:</span>
                  <div className="mt-1 flex flex-col gap-1">
                    {entry.source_urls.map((url) => (
                      <a key={url} href={url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline break-all">
                        {url}
                      </a>
                    ))}
                  </div>
                </div>
              )}
              {(entry.verification_status || entry.source_checked_at || entry.confidence !== null) && (
                <div className="mt-2 text-xs text-gray-500">
                  <span>Status: {entry.verification_status || 'needs_review'}</span>
                  {entry.source_checked_at && <span className="ml-3">Checked: {formatDateInput(entry.source_checked_at)}</span>}
                  {entry.confidence !== null && entry.confidence !== undefined && (
                    <span className="ml-3">Confidence: {Number(entry.confidence).toFixed(2)}</span>
                  )}
                </div>
              )}
              <p className="text-xs text-gray-400 mt-1">{new Date(entry.created_at).toLocaleDateString()}</p>
            </div>
          )
        })}
        {!isLoading && research.length === 0 && (
          <EmptyState
            icon={filterLocation || filterCategory ? 'filter' : 'research'}
            title={filterLocation || filterCategory ? 'No matches' : 'No research yet'}
            message={filterLocation || filterCategory ? 'No research matches the current filters.' : 'Add research entries or run full research on a location.'}
          />
        )}
      </div>
    </div>
  )
}
