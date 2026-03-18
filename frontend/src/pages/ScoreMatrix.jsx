import { useState, useEffect, useMemo } from 'react'
import { getLocations, getCategories, getScores, upsertScore, getRankings } from '../api'
import { sortLocationsByOverallRank } from '../utils/rankings'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import { toast } from 'sonner'
import useSortableTable from '../hooks/useSortableTable'
import SortHeader from '../components/SortHeader'

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
  const [countryFilter, setCountryFilter] = useState('')
  const [editingCell, setEditingCell] = useState(null)
  const [editValue, setEditValue] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    const [locs, cats, sc, rankings] = await Promise.all([getLocations(), getCategories(), getScores(), getRankings('combined')])
    setLocations(sortLocationsByOverallRank(locs, rankings))
    setCategories(cats)
    setScores(sc)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const uniqueCountries = useMemo(
    () => Array.from(new Set(locations.map((loc) => loc.country).filter(Boolean))).sort((a, b) => a.localeCompare(b)),
    [locations],
  )

  const filteredLocations = useMemo(() => {
    if (!countryFilter) return locations
    const normalizedFilter = countryFilter.trim().toLowerCase()
    return locations.filter((loc) => loc.country?.trim().toLowerCase() === normalizedFilter)
  }, [locations, countryFilter])

  const { sortKey, sortDirection, toggleSort, sortedData: sortedLocations } = useSortableTable(filteredLocations)
  const displayLocations = sortKey ? sortedLocations : filteredLocations

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
      toast.success('Score saved')
      await load()
    }
    setEditingCell(null)
  }

  if (loading) return <Spinner label="Loading score matrix..." />

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Score Matrix</h1>
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
      <div className="bg-white rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50">
              <SortHeader label="Location" sortKey="name" currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2 px-3 text-left font-medium text-gray-600 sticky left-0 bg-gray-50" />
              {categories.map((cat) => (
                <th key={cat.id} className="py-2 px-3 text-center font-medium text-gray-600 min-w-[80px]">
                  <span className="text-xs">{cat.name}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayLocations.map((loc) => (
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
            {filteredLocations.length === 0 && (
              <tr>
                <td colSpan={categories.length + 1}>
                  <EmptyState
                    icon={locations.length === 0 ? 'locations' : 'filter'}
                    title={locations.length === 0 ? 'No locations yet' : 'No matches'}
                    message={locations.length === 0 ? 'Add locations to start scoring them.' : 'No locations match the selected country filter.'}
                  />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
