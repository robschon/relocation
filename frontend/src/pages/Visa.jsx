import { useState, useEffect } from 'react'
import { getVisas, createVisa, updateVisa, deleteVisa } from '../api'

const emptyForm = { country: '', visa_type: '', description: '', residency_pathway: '', requirements: '', timeline: '', cost: '', notes: '' }

export default function Visa() {
  const [visas, setVisas] = useState([])
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({ ...emptyForm })
  const [expanded, setExpanded] = useState({})

  const load = () => {
    const params = search ? { country: search } : {}
    getVisas(params).then(setVisas)
  }

  useEffect(() => { load() }, [search])

  const handleSubmit = async (e) => {
    e.preventDefault()
    const data = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v || null]))
    data.country = form.country
    data.visa_type = form.visa_type
    if (editingId) {
      await updateVisa(editingId, data)
    } else {
      await createVisa(data)
    }
    setForm({ ...emptyForm })
    setShowForm(false)
    setEditingId(null)
    load()
  }

  const handleEdit = (visa) => {
    setForm({
      country: visa.country,
      visa_type: visa.visa_type,
      description: visa.description || '',
      residency_pathway: visa.residency_pathway || '',
      requirements: visa.requirements || '',
      timeline: visa.timeline || '',
      cost: visa.cost || '',
      notes: visa.notes || '',
    })
    setEditingId(visa.id)
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this visa entry?')) return
    await deleteVisa(id)
    load()
  }

  const grouped = visas.reduce((acc, v) => {
    ;(acc[v.country] = acc[v.country] || []).push(v)
    return acc
  }, {})

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Visa Info</h1>
        <button
          onClick={() => { setShowForm(!showForm); setEditingId(null); setForm({ ...emptyForm }) }}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : 'Add Visa Info'}
        </button>
      </div>

      <input
        placeholder="Search by country..." value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="border rounded px-3 py-2 text-sm mb-4 w-64"
      />

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-2 gap-3">
          <input required placeholder="Country" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} className="border rounded px-3 py-2 text-sm" />
          <input required placeholder="Visa Type" value={form.visa_type} onChange={(e) => setForm({ ...form, visa_type: e.target.value })} className="border rounded px-3 py-2 text-sm" />
          <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="border rounded px-3 py-2 text-sm col-span-2" rows={2} />
          <textarea placeholder="Residency Pathway" value={form.residency_pathway} onChange={(e) => setForm({ ...form, residency_pathway: e.target.value })} className="border rounded px-3 py-2 text-sm" rows={2} />
          <textarea placeholder="Requirements" value={form.requirements} onChange={(e) => setForm({ ...form, requirements: e.target.value })} className="border rounded px-3 py-2 text-sm" rows={2} />
          <input placeholder="Timeline" value={form.timeline} onChange={(e) => setForm({ ...form, timeline: e.target.value })} className="border rounded px-3 py-2 text-sm" />
          <input placeholder="Cost" value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} className="border rounded px-3 py-2 text-sm" />
          <textarea placeholder="Notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="border rounded px-3 py-2 text-sm col-span-2" rows={2} />
          <button type="submit" className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 col-span-2">
            {editingId ? 'Update' : 'Create'} Visa Info
          </button>
        </form>
      )}

      {Object.entries(grouped).map(([country, entries]) => (
        <div key={country} className="bg-white rounded-lg shadow mb-4">
          <div className="px-4 py-3 border-b bg-gray-50 font-semibold">{country}</div>
          {entries.map((v) => (
            <div key={v.id} className="px-4 py-3 border-b last:border-b-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-medium">{v.visa_type}</span>
                  {v.timeline && <span className="text-xs text-gray-400">Timeline: {v.timeline}</span>}
                  {v.cost && <span className="text-xs text-gray-400">Cost: {v.cost}</span>}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setExpanded({ ...expanded, [v.id]: !expanded[v.id] })} className="text-xs text-blue-600 hover:underline">
                    {expanded[v.id] ? 'Collapse' : 'Details'}
                  </button>
                  <button onClick={() => handleEdit(v)} className="text-xs text-blue-600 hover:underline">Edit</button>
                  <button onClick={() => handleDelete(v.id)} className="text-xs text-red-500 hover:underline">Delete</button>
                </div>
              </div>
              {v.description && <p className="text-sm text-gray-600 mt-1">{v.description}</p>}
              {expanded[v.id] && (
                <div className="mt-3 space-y-2 text-sm">
                  {v.residency_pathway && <div><span className="font-medium text-gray-600">Residency Pathway:</span> <span className="text-gray-700">{v.residency_pathway}</span></div>}
                  {v.requirements && <div><span className="font-medium text-gray-600">Requirements:</span> <span className="text-gray-700">{v.requirements}</span></div>}
                  {v.notes && <div><span className="font-medium text-gray-600">Notes:</span> <span className="text-gray-700">{v.notes}</span></div>}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}

      {visas.length === 0 && (
        <div className="text-center text-gray-400 py-12">No visa information yet.</div>
      )}
    </div>
  )
}
