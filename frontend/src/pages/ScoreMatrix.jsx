import { useState, useEffect } from 'react'
import { getLocations, getCategories, getScores, upsertScore, getRankings } from '../api'
import { sortLocationsByOverallRank } from '../utils/rankings'

function scoreColor(score) {
  if (score === null || score === undefined) return 'bg-gray-100 text-gray-400'
  if (score <= 3) return 'bg-red-100 text-red-800'
  if (score <= 5) return 'bg-yellow-100 text-yellow-800'
  if (score <= 7) return 'bg-green-100 text-green-800'
  return 'bg-green-200 text-green-900'
}

export default function ScoreMatrix() {
  const [locations, setLocations] = useState([])
  const [categories, setCategories] = useState([])
  const [scores, setScores] = useState([])
  const [editingCell, setEditingCell] = useState(null)
  const [editValue, setEditValue] = useState('')

  const load = async () => {
    const [locs, cats, sc, rankings] = await Promise.all([getLocations(), getCategories(), getScores(), getRankings('combined')])
    setLocations(sortLocationsByOverallRank(locs, rankings))
    setCategories(cats)
    setScores(sc)
  }

  useEffect(() => { load() }, [])

  const getScore = (locId, catId) => {
    const s = scores.find((s) => s.location_id === locId && s.category_id === catId)
    return s ? s.score : null
  }

  const handleEdit = (locId, catId) => {
    const current = getScore(locId, catId)
    setEditingCell(`${locId}-${catId}`)
    setEditValue(current ?? '')
  }

  const handleSave = async (locId, catId) => {
    const val = Number(editValue)
    if (val >= 0 && val <= 10) {
      await upsertScore({ location_id: locId, category_id: catId, score: val })
      await load()
    }
    setEditingCell(null)
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Score Matrix</h1>
      <div className="bg-white rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="py-2 px-3 text-left font-medium text-gray-600 sticky left-0 bg-gray-50">Location</th>
              {categories.map((cat) => (
                <th key={cat.id} className="py-2 px-3 text-center font-medium text-gray-600 min-w-[80px]">
                  <span className="text-xs">{cat.name}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {locations.map((loc) => (
              <tr key={loc.id} className="border-b hover:bg-gray-50">
                <td className="py-2 px-3 font-medium sticky left-0 bg-white">{loc.name}</td>
                {categories.map((cat) => {
                  const cellKey = `${loc.id}-${cat.id}`
                  const score = getScore(loc.id, cat.id)
                  return (
                    <td key={cat.id} className="py-1 px-1 text-center">
                      {editingCell === cellKey ? (
                        <input
                          type="number" min={0} max={10} value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onBlur={() => handleSave(loc.id, cat.id)}
                          onKeyDown={(e) => e.key === 'Enter' && handleSave(loc.id, cat.id)}
                          className="w-12 border rounded px-1 py-0.5 text-center text-sm"
                          autoFocus
                        />
                      ) : (
                        <button
                          onClick={() => handleEdit(loc.id, cat.id)}
                          className={`w-10 h-8 rounded text-sm font-mono font-bold ${scoreColor(score)}`}
                        >
                          {score ?? '—'}
                        </button>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
            {locations.length === 0 && (
              <tr>
                <td colSpan={categories.length + 1} className="py-8 text-center text-gray-400">
                  No locations yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
