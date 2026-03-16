import { useState, useEffect } from 'react'
import { getLocations, getProsCons, createProCon, deleteProCon, getCategories, getRankings } from '../api'
import { sortLocationsByOverallRank } from '../utils/rankings'
import Spinner from '../components/Spinner'

export default function ProsCons() {
  const [locations, setLocations] = useState([])
  const [prosCons, setProsCons] = useState([])
  const [categories, setCategories] = useState([])
  const [newItems, setNewItems] = useState({})
  const [loading, setLoading] = useState(true)

  const load = async () => {
    const [locs, pc, cats, rankings] = await Promise.all([getLocations(), getProsCons(), getCategories(), getRankings('combined')])
    setLocations(sortLocationsByOverallRank(locs, rankings))
    setProsCons(pc)
    setCategories(cats)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const getFormState = (locId) => newItems[locId] || { type: 'pro', content: '', category_id: '' }
  const setFormState = (locId, state) => setNewItems({ ...newItems, [locId]: state })

  const handleAdd = async (locId, e) => {
    e.preventDefault()
    const form = getFormState(locId)
    await createProCon({
      location_id: locId,
      type: form.type,
      content: form.content,
      category_id: form.category_id ? Number(form.category_id) : null,
    })
    setFormState(locId, { type: 'pro', content: '', category_id: '' })
    load()
  }

  const handleDelete = async (id) => {
    await deleteProCon(id)
    load()
  }

  const catName = (id) => categories.find((c) => c.id === id)?.name || ''

  if (loading) return <Spinner label="Loading pros & cons..." />

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Pros & Cons</h1>

      {locations.map((loc) => {
        const pros = prosCons.filter((p) => p.location_id === loc.id && p.type === 'pro')
        const cons = prosCons.filter((p) => p.location_id === loc.id && p.type === 'con')
        const form = getFormState(loc.id)

        return (
          <div key={loc.id} className="bg-white rounded-lg shadow p-4 mb-4">
            <h2 className="text-lg font-semibold mb-3">
              {loc.name} <span className="text-sm text-gray-400 font-normal">{loc.country}</span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-3">
              <div>
                <h3 className="text-sm font-medium text-green-700 mb-2">Pros ({pros.length})</h3>
                {pros.map((p) => (
                  <div key={p.id} className="flex items-start justify-between bg-green-50 rounded p-2 mb-1 text-sm">
                    <div>
                      <span>{p.content}</span>
                      {p.category_id && <span className="ml-2 text-xs text-gray-400">[{catName(p.category_id)}]</span>}
                    </div>
                    <button onClick={() => handleDelete(p.id)} className="text-red-400 hover:text-red-600 ml-2 shrink-0">&times;</button>
                  </div>
                ))}
                {pros.length === 0 && <p className="text-xs text-gray-400">No pros yet.</p>}
              </div>
              <div>
                <h3 className="text-sm font-medium text-red-700 mb-2">Cons ({cons.length})</h3>
                {cons.map((p) => (
                  <div key={p.id} className="flex items-start justify-between bg-red-50 rounded p-2 mb-1 text-sm">
                    <div>
                      <span>{p.content}</span>
                      {p.category_id && <span className="ml-2 text-xs text-gray-400">[{catName(p.category_id)}]</span>}
                    </div>
                    <button onClick={() => handleDelete(p.id)} className="text-red-400 hover:text-red-600 ml-2 shrink-0">&times;</button>
                  </div>
                ))}
                {cons.length === 0 && <p className="text-xs text-gray-400">No cons yet.</p>}
              </div>
            </div>
            <form onSubmit={(e) => handleAdd(loc.id, e)} className="flex gap-2">
              <select value={form.type} onChange={(e) => setFormState(loc.id, { ...form, type: e.target.value })} className="border rounded px-2 py-1 text-sm">
                <option value="pro">Pro</option>
                <option value="con">Con</option>
              </select>
              <input
                required placeholder="Add pro or con..." value={form.content}
                onChange={(e) => setFormState(loc.id, { ...form, content: e.target.value })}
                className="border rounded px-2 py-1 text-sm flex-1"
              />
              <select value={form.category_id} onChange={(e) => setFormState(loc.id, { ...form, category_id: e.target.value })} className="border rounded px-2 py-1 text-sm">
                <option value="">Category</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button type="submit" className="bg-blue-600 text-white px-3 py-1 rounded text-sm">Add</button>
            </form>
          </div>
        )
      })}

      {locations.length === 0 && (
        <div className="text-center text-gray-400 py-12">No locations yet. Add locations first.</div>
      )}
    </div>
  )
}
