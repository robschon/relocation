import { useState, useEffect } from 'react'
import { getVisas, createVisa, updateVisa, deleteVisa } from '../api'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import { toast } from 'sonner'

const todayIso = new Date().toISOString().slice(0, 10)

const emptyForm = {
  country: '',
  visa_type: '',
  description: '',
  residency_pathway: '',
  requirements: '',
  timeline: '',
  cost: '',
  notes: '',
  source_urls_text: '',
  source_published_at: '',
  source_checked_at: todayIso,
  verification_status: 'verified',
  confidence: '0.70',
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

export default function Visa() {
  const [visas, setVisas] = useState([])
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({ ...emptyForm })
  const [expanded, setExpanded] = useState({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = () => {
    const params = search ? { country: search } : {}
    getVisas(params)
      .then(setVisas)
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    const params = search ? { country: search } : {}
    getVisas(params)
      .then((data) => {
        setVisas(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [search])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    const sourceUrls = parseSourceUrls(form.source_urls_text)
    if (sourceUrls.length === 0) {
      setError('At least one source URL is required.')
      return
    }
    if (!form.source_checked_at) {
      setError('Source checked date is required.')
      return
    }

    const confidence = form.confidence === '' ? null : Number(form.confidence)
    if (confidence !== null && Number.isNaN(confidence)) {
      setError('Confidence must be a number between 0 and 1.')
      return
    }
    if (form.verification_status === 'verified' && confidence === null) {
      setError('Verified entries require confidence.')
      return
    }

    const data = {
      country: form.country.trim(),
      visa_type: form.visa_type.trim(),
      description: form.description.trim() || null,
      residency_pathway: form.residency_pathway.trim() || null,
      requirements: form.requirements.trim() || null,
      timeline: form.timeline.trim() || null,
      cost: form.cost.trim() || null,
      notes: form.notes.trim() || null,
      source_urls: sourceUrls,
      source_published_at: form.source_published_at || null,
      source_checked_at: form.source_checked_at || null,
      verification_status: form.verification_status,
      confidence,
    }

    try {
      if (editingId) {
        await updateVisa(editingId, data)
        toast.success('Visa info updated')
      } else {
        await createVisa(data)
        toast.success('Visa info created')
      }
      setForm({ ...emptyForm, source_checked_at: todayIso })
      setShowForm(false)
      setEditingId(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleEdit = (visa) => {
    setError('')
    setForm({
      country: visa.country || '',
      visa_type: visa.visa_type || '',
      description: visa.description || '',
      residency_pathway: visa.residency_pathway || '',
      requirements: visa.requirements || '',
      timeline: visa.timeline || '',
      cost: visa.cost || '',
      notes: visa.notes || '',
      source_urls_text: (visa.source_urls || []).join('\n'),
      source_published_at: formatDateInput(visa.source_published_at),
      source_checked_at: formatDateInput(visa.source_checked_at) || todayIso,
      verification_status: visa.verification_status || 'needs_review',
      confidence: visa.confidence === null || visa.confidence === undefined ? '' : String(visa.confidence),
    })
    setEditingId(visa.id)
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this visa entry?')) return
    setError('')
    try {
      await deleteVisa(id)
      toast.success('Visa entry deleted')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const grouped = visas.reduce((acc, visa) => {
    ;(acc[visa.country] = acc[visa.country] || []).push(visa)
    return acc
  }, {})

  if (loading) return <Spinner label="Loading visa info..." />

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Visa Info</h1>
        <button
          onClick={() => {
            setError('')
            setShowForm(!showForm)
            setEditingId(null)
            setForm({ ...emptyForm, source_checked_at: todayIso })
          }}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : 'Add Visa Info'}
        </button>
      </div>

      {error && <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <input
        placeholder="Search by country..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="border rounded px-3 py-2 text-sm mb-4 w-64"
      />

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-1 md:grid-cols-2 gap-3">
          <input
            required
            placeholder="Country"
            value={form.country}
            onChange={(e) => setForm({ ...form, country: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="Visa Type"
            value={form.visa_type}
            onChange={(e) => setForm({ ...form, visa_type: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <textarea
            placeholder="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="border rounded px-3 py-2 text-sm md:col-span-2"
            rows={2}
          />
          <textarea
            placeholder="Residency Pathway"
            value={form.residency_pathway}
            onChange={(e) => setForm({ ...form, residency_pathway: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
            rows={2}
          />
          <textarea
            placeholder="Requirements"
            value={form.requirements}
            onChange={(e) => setForm({ ...form, requirements: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
            rows={2}
          />
          <input
            placeholder="Timeline"
            value={form.timeline}
            onChange={(e) => setForm({ ...form, timeline: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            placeholder="Cost"
            value={form.cost}
            onChange={(e) => setForm({ ...form, cost: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <textarea
            placeholder="Notes"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            className="border rounded px-3 py-2 text-sm md:col-span-2"
            rows={2}
          />
          <textarea
            required
            placeholder="Source URLs (one per line)"
            value={form.source_urls_text}
            onChange={(e) => setForm({ ...form, source_urls_text: e.target.value })}
            className="border rounded px-3 py-2 text-sm md:col-span-2"
            rows={3}
          />
          <input
            type="date"
            placeholder="Source published date"
            value={form.source_published_at}
            onChange={(e) => setForm({ ...form, source_published_at: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
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
          <button type="submit" className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 md:col-span-2">
            {editingId ? 'Update' : 'Create'} Visa Info
          </button>
        </form>
      )}

      {Object.entries(grouped).map(([country, entries]) => (
        <div key={country} className="bg-white rounded-lg shadow mb-4">
          <div className="px-4 py-3 border-b bg-gray-50 font-semibold">{country}</div>
          {entries.map((visa) => (
            <div key={visa.id} className="px-4 py-3 border-b last:border-b-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-medium">{visa.visa_type}</span>
                  {visa.timeline && <span className="text-xs text-gray-400">Timeline: {visa.timeline}</span>}
                  {visa.cost && <span className="text-xs text-gray-400">Cost: {visa.cost}</span>}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setExpanded({ ...expanded, [visa.id]: !expanded[visa.id] })} className="text-xs text-blue-600 hover:underline">
                    {expanded[visa.id] ? 'Collapse' : 'Details'}
                  </button>
                  <button onClick={() => handleEdit(visa)} className="text-xs text-blue-600 hover:underline">Edit</button>
                  <button onClick={() => handleDelete(visa.id)} className="text-xs text-red-500 hover:underline">Delete</button>
                </div>
              </div>
              {visa.description && <p className="text-sm text-gray-600 mt-1">{visa.description}</p>}
              {expanded[visa.id] && (
                <div className="mt-3 space-y-2 text-sm">
                  {visa.residency_pathway && <div><span className="font-medium text-gray-600">Residency Pathway:</span> <span className="text-gray-700">{visa.residency_pathway}</span></div>}
                  {visa.requirements && <div><span className="font-medium text-gray-600">Requirements:</span> <span className="text-gray-700">{visa.requirements}</span></div>}
                  {visa.notes && <div><span className="font-medium text-gray-600">Notes:</span> <span className="text-gray-700">{visa.notes}</span></div>}
                  <div><span className="font-medium text-gray-600">Verification:</span> <span className="text-gray-700">{visa.verification_status || 'needs_review'}</span></div>
                  <div><span className="font-medium text-gray-600">Checked:</span> <span className="text-gray-700">{formatDateInput(visa.source_checked_at) || 'Unknown'}</span></div>
                  {visa.source_published_at && <div><span className="font-medium text-gray-600">Source Published:</span> <span className="text-gray-700">{formatDateInput(visa.source_published_at)}</span></div>}
                  {visa.confidence !== null && visa.confidence !== undefined && (
                    <div><span className="font-medium text-gray-600">Confidence:</span> <span className="text-gray-700">{Number(visa.confidence).toFixed(2)}</span></div>
                  )}
                  {visa.source_urls && visa.source_urls.length > 0 && (
                    <div>
                      <span className="font-medium text-gray-600">Sources:</span>
                      <div className="mt-1 flex flex-col gap-1">
                        {visa.source_urls.map((url) => (
                          <a key={url} href={url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline break-all">
                            {url}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}

      {visas.length === 0 && (
        <EmptyState
          icon="visa"
          title={search ? 'No matches' : 'No visa information yet'}
          message={search ? 'No visa entries match your search.' : 'Add visa details for the countries you are considering.'}
        />
      )}
    </div>
  )
}
