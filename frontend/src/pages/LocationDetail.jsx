import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getLocation, updateLocation, getLocationScores, upsertScore, getLocationProsCons, createProCon, deleteProCon, getCategories, getResearch, exportLocationResearchMarkdown } from '../api'
import ScoreSlider from '../components/ScoreSlider'
import Spinner from '../components/Spinner'
import { toast } from 'sonner'

export default function LocationDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [location, setLocation] = useState(null)
  const [scores, setScores] = useState([])
  const [categories, setCategories] = useState([])
  const [prosCons, setProsCons] = useState([])
  const [research, setResearch] = useState([])
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [newProCon, setNewProCon] = useState({ type: 'pro', content: '', category_id: '' })
  const [showResearchMarkdown, setShowResearchMarkdown] = useState(false)
  const [researchMarkdown, setResearchMarkdown] = useState('')
  const [researchMarkdownLoading, setResearchMarkdownLoading] = useState(false)
  const [researchMarkdownError, setResearchMarkdownError] = useState('')

  const load = async () => {
    const [loc, sc, cats, pc, res] = await Promise.all([
      getLocation(id),
      getLocationScores(id),
      getCategories(),
      getLocationProsCons(id),
      getResearch({ location_id: id }),
    ])
    setLocation(loc)
    setScores(sc)
    setCategories(cats)
    setProsCons(pc)
    setResearch(res)
    setEditForm({ name: loc.name, country: loc.country, region: loc.region || '', population: loc.population || '', description: loc.description || '' })
  }

  useEffect(() => {
    setShowResearchMarkdown(false)
    setResearchMarkdown('')
    setResearchMarkdownError('')
    void load()
  }, [id])

  const handleSave = async () => {
    await updateLocation(id, {
      ...editForm,
      population: editForm.population ? Number(editForm.population) : null,
      region: editForm.region || null,
      description: editForm.description || null,
    })
    toast.success('Location updated')
    setEditing(false)
    load()
  }

  const handleScoreChange = async (categoryId, score) => {
    await upsertScore({ location_id: Number(id), category_id: categoryId, score })
    toast.success('Score saved')
    load()
  }

  const handleAddProCon = async (e) => {
    e.preventDefault()
    await createProCon({
      location_id: Number(id),
      type: newProCon.type,
      content: newProCon.content,
      category_id: newProCon.category_id ? Number(newProCon.category_id) : null,
    })
    toast.success(`${newProCon.type === 'pro' ? 'Pro' : 'Con'} added`)
    setNewProCon({ type: 'pro', content: '', category_id: '' })
    load()
  }

  const handleDeleteProCon = async (itemId) => {
    await deleteProCon(itemId)
    toast.success('Item removed')
    load()
  }

  const handleToggleResearchMarkdown = async () => {
    if (showResearchMarkdown) {
      setShowResearchMarkdown(false)
      return
    }

    if (!researchMarkdown) {
      setResearchMarkdownLoading(true)
      setResearchMarkdownError('')
      try {
        const markdown = await exportLocationResearchMarkdown(id)
        setResearchMarkdown(markdown)
      } catch (error) {
        setResearchMarkdownError(error.message || 'Failed to load research markdown document.')
        setResearchMarkdownLoading(false)
        return
      }
      setResearchMarkdownLoading(false)
    }

    setShowResearchMarkdown(true)
  }

  if (!location) return <Spinner label="Loading location..." />

  const scoreMap = Object.fromEntries(scores.map((s) => [s.category_id, s.score]))
  const categoryNameById = Object.fromEntries(categories.map((cat) => [cat.id, cat.name]))
  const categoryOrderById = Object.fromEntries(categories.map((cat, idx) => [cat.id, idx]))
  const researchSectionsMap = research.reduce((acc, entry) => {
    const key = entry.category_id ?? 'uncategorized'
    if (!acc[key]) {
      const categoryName = entry.category_id ? (categoryNameById[entry.category_id] || `Category #${entry.category_id}`) : 'General'
      acc[key] = { key, categoryName, entries: [] }
    }
    acc[key].entries.push(entry)
    return acc
  }, {})
  const researchSections = Object.values(researchSectionsMap).sort((a, b) => {
    if (a.key === 'uncategorized') return 1
    if (b.key === 'uncategorized') return -1
    return (categoryOrderById[a.key] ?? 999) - (categoryOrderById[b.key] ?? 999)
  })
  const pros = prosCons.filter((p) => p.type === 'pro')
  const cons = prosCons.filter((p) => p.type === 'con')

  return (
    <div>
      <button onClick={() => navigate('/locations')} className="text-sm text-blue-600 hover:underline mb-4 block">
        &larr; Back to Locations
      </button>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-start justify-between">
          {editing ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 flex-1 mr-4">
              <input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} className="border rounded px-3 py-1 text-sm" placeholder="Name" />
              <input value={editForm.country} onChange={(e) => setEditForm({ ...editForm, country: e.target.value })} className="border rounded px-3 py-1 text-sm" placeholder="Country" />
              <input value={editForm.region} onChange={(e) => setEditForm({ ...editForm, region: e.target.value })} className="border rounded px-3 py-1 text-sm" placeholder="Region" />
              <input value={editForm.population} onChange={(e) => setEditForm({ ...editForm, population: e.target.value })} className="border rounded px-3 py-1 text-sm" placeholder="Population" type="number" />
              <textarea value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} className="border rounded px-3 py-1 text-sm sm:col-span-2" placeholder="Description" rows={2} />
              <div className="sm:col-span-2 flex gap-2">
                <button onClick={handleSave} className="bg-green-600 text-white px-3 py-1 rounded text-sm">Save</button>
                <button onClick={() => setEditing(false)} className="bg-gray-300 px-3 py-1 rounded text-sm">Cancel</button>
              </div>
            </div>
          ) : (
            <div>
              <h1 className="text-2xl font-bold">{location.name}</h1>
              <p className="text-gray-500">{location.country}{location.region ? `, ${location.region}` : ''}</p>
              {location.population && <p className="text-sm text-gray-400">Population: {location.population.toLocaleString()}</p>}
              {location.description && <p className="text-gray-600 mt-2">{location.description}</p>}
            </div>
          )}
          {!editing && (
            <div className="flex flex-col items-end gap-1">
              <button onClick={handleToggleResearchMarkdown} className="text-sm text-blue-600 hover:underline">
                {showResearchMarkdown ? 'Hide Markdown Research' : 'Show Markdown Research'}
              </button>
              <button onClick={() => setEditing(true)} className="text-sm text-blue-600 hover:underline">Edit</button>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-semibold mb-4">Scores</h2>
          <div className="space-y-3">
            {categories.map((cat) => (
              <ScoreSlider
                key={cat.id}
                label={cat.name}
                value={scoreMap[cat.id]}
                onChange={(v) => handleScoreChange(cat.id, v)}
              />
            ))}
            {categories.length === 0 && <p className="text-gray-400 text-sm">No categories defined.</p>}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-semibold mb-4">Pros & Cons</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <h3 className="text-sm font-medium text-green-700 mb-2">Pros ({pros.length})</h3>
              {pros.map((p) => (
                <div key={p.id} className="flex items-start justify-between bg-green-50 rounded p-2 mb-1 text-sm">
                  <span>{p.content}</span>
                  <button onClick={() => handleDeleteProCon(p.id)} className="text-red-400 hover:text-red-600 ml-2 shrink-0">&times;</button>
                </div>
              ))}
            </div>
            <div>
              <h3 className="text-sm font-medium text-red-700 mb-2">Cons ({cons.length})</h3>
              {cons.map((p) => (
                <div key={p.id} className="flex items-start justify-between bg-red-50 rounded p-2 mb-1 text-sm">
                  <span>{p.content}</span>
                  <button onClick={() => handleDeleteProCon(p.id)} className="text-red-400 hover:text-red-600 ml-2 shrink-0">&times;</button>
                </div>
              ))}
            </div>
          </div>
          <form onSubmit={handleAddProCon} className="flex gap-2">
            <select value={newProCon.type} onChange={(e) => setNewProCon({ ...newProCon, type: e.target.value })} className="border rounded px-2 py-1 text-sm">
              <option value="pro">Pro</option>
              <option value="con">Con</option>
            </select>
            <input
              required placeholder="Add pro or con..." value={newProCon.content}
              onChange={(e) => setNewProCon({ ...newProCon, content: e.target.value })}
              className="border rounded px-2 py-1 text-sm flex-1"
            />
            <button type="submit" className="bg-blue-600 text-white px-3 py-1 rounded text-sm">Add</button>
          </form>
        </div>
      </div>

      {research.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4 mt-6">
          <h2 className="text-lg font-semibold mb-4">Research Notes</h2>
          <div className="space-y-4">
            {researchSections.map((section) => (
              <div key={section.key} className="border rounded p-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">{section.categoryName}</h3>
                <div className="space-y-3">
                  {section.entries.map((r) => (
                    <div key={r.id} className="text-sm">
                      <p className="text-gray-700">{r.content}</p>
                      {r.source && <p className="text-xs text-blue-500 mt-1">Source: {r.source}</p>}
                      <p className="text-xs text-gray-400 mt-1">{new Date(r.created_at).toLocaleDateString()}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {showResearchMarkdown && (
        <div className="bg-white rounded-lg shadow p-4 mt-6">
          <h2 className="text-lg font-semibold mb-3">Research Markdown Document</h2>
          {researchMarkdownLoading && <p className="text-sm text-gray-500">Loading markdown document...</p>}
          {researchMarkdownError && <p className="text-sm text-red-600">{researchMarkdownError}</p>}
          {!researchMarkdownLoading && !researchMarkdownError && (
            <pre className="text-xs text-gray-700 bg-gray-50 border rounded p-3 overflow-auto max-h-[70vh] whitespace-pre-wrap">
              {researchMarkdown}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
