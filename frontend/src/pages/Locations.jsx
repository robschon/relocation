import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLocations, createLocation, deleteLocation } from '../api'

export default function Locations() {
  const [locations, setLocations] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', country: '', region: '', population: '', description: '' })
  const navigate = useNavigate()

  const load = () => getLocations().then(setLocations)
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

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Locations</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : 'Add Location'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-2 gap-4">
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
            className="border rounded px-3 py-2 text-sm col-span-2"
            rows={2}
          />
          <button type="submit" className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 col-span-2">
            Create Location
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {locations.map((loc) => (
          <div
            key={loc.id}
            className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => navigate(`/locations/${loc.id}`)}
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-lg">{loc.name}</h3>
                <p className="text-sm text-gray-500">{loc.country}{loc.region ? `, ${loc.region}` : ''}</p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleDelete(loc.id, loc.name) }}
                className="text-red-400 hover:text-red-600 text-sm"
              >
                Delete
              </button>
            </div>
            {loc.population && (
              <p className="text-xs text-gray-400 mt-1">Pop. {loc.population.toLocaleString()}</p>
            )}
            {loc.description && (
              <p className="text-sm text-gray-600 mt-2 line-clamp-2">{loc.description}</p>
            )}
          </div>
        ))}
        {locations.length === 0 && (
          <div className="col-span-3 text-center text-gray-400 py-12">
            No locations yet. Click "Add Location" to get started.
          </div>
        )}
      </div>
    </div>
  )
}
