import { useState, useEffect } from 'react'
import { getResearch, createResearch, deleteResearch, getLocations, getCategories, getRankings } from '../api'
import { sortLocationsByOverallRank } from '../utils/rankings'

export default function Research() {
  const [research, setResearch] = useState([])
  const [locations, setLocations] = useState([])
  const [categories, setCategories] = useState([])
  const [filterLocation, setFilterLocation] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ location_id: '', category_id: '', content: '', source: '' })
  const [expanded, setExpanded] = useState({})

  const load = async () => {
    const params = {}
    if (filterLocation) params.location_id = filterLocation
    if (filterCategory) params.category_id = filterCategory
    const [res, locs, cats, rankings] = await Promise.all([
      getResearch(params),
      getLocations(),
      getCategories(),
      getRankings('combined'),
    ])
    setResearch(res)
    setLocations(sortLocationsByOverallRank(locs, rankings))
    setCategories(cats)
  }

  useEffect(() => { load() }, [filterLocation, filterCategory])

  const handleSubmit = async (e) => {
    e.preventDefault()
    await createResearch({
      location_id: Number(form.location_id),
      category_id: form.category_id ? Number(form.category_id) : null,
      content: form.content,
      source: form.source || null,
    })
    setForm({ location_id: '', category_id: '', content: '', source: '' })
    setShowForm(false)
    load()
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this research entry?')) return
    await deleteResearch(id)
    load()
  }

  const locName = (id) => locations.find((l) => l.id === id)?.name || `#${id}`
  const catName = (id) => categories.find((c) => c.id === id)?.name || ''

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Research</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : 'Add Research'}
        </button>
      </div>

      <div className="flex gap-3 mb-4">
        <select value={filterLocation} onChange={(e) => setFilterLocation(e.target.value)} className="border rounded px-3 py-1 text-sm">
          <option value="">All Locations</option>
          {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
        <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} className="border rounded px-3 py-1 text-sm">
          <option value="">All Categories</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 mb-6 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <select required value={form.location_id} onChange={(e) => setForm({ ...form, location_id: e.target.value })} className="border rounded px-3 py-2 text-sm">
              <option value="">Select Location</option>
              {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
            <select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })} className="border rounded px-3 py-2 text-sm">
              <option value="">Category (optional)</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <textarea
            required placeholder="Research content..." value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            className="border rounded px-3 py-2 text-sm w-full" rows={4}
          />
          <input
            placeholder="Source (optional)" value={form.source}
            onChange={(e) => setForm({ ...form, source: e.target.value })}
            className="border rounded px-3 py-2 text-sm w-full"
          />
          <button type="submit" className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700">
            Save Research
          </button>
        </form>
      )}

      <div className="space-y-3">
        {research.map((r) => {
          const isLong = r.content.length > 200
          const isExpanded = expanded[r.id]
          return (
            <div key={r.id} className="bg-white rounded-lg shadow p-4">
              <div className="flex items-start justify-between">
                <div className="flex gap-2 mb-2">
                  <span className="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded">{locName(r.location_id)}</span>
                  {r.category_id && <span className="bg-purple-100 text-purple-800 text-xs px-2 py-0.5 rounded">{catName(r.category_id)}</span>}
                </div>
                <button onClick={() => handleDelete(r.id)} className="text-red-400 hover:text-red-600 text-sm">Delete</button>
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">
                {isLong && !isExpanded ? r.content.slice(0, 200) + '...' : r.content}
              </p>
              {isLong && (
                <button
                  onClick={() => setExpanded({ ...expanded, [r.id]: !isExpanded })}
                  className="text-xs text-blue-600 hover:underline mt-1"
                >
                  {isExpanded ? 'Show less' : 'Show more'}
                </button>
              )}
              {r.source && <p className="text-xs text-blue-500 mt-2">Source: {r.source}</p>}
              <p className="text-xs text-gray-400 mt-1">{new Date(r.created_at).toLocaleDateString()}</p>
            </div>
          )
        })}
        {research.length === 0 && (
          <div className="text-center text-gray-400 py-12">No research entries yet.</div>
        )}
      </div>
    </div>
  )
}
