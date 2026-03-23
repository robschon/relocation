import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getRankings, getLocations, getCategories } from '../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from 'recharts'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import useSortableTable from '../hooks/useSortableTable'
import SortHeader from '../components/SortHeader'

function RankingsTable({ rankings, locationIdForRanking }) {
  const { sortKey, sortDirection, toggleSort, sortedData } = useSortableTable(rankings)

  const displayData = sortKey ? sortedData : rankings

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left text-gray-500">
          <th className="py-2 w-12">#</th>
          <SortHeader label="Location" sortKey="location_name" currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2" />
          <SortHeader label="Country" sortKey="country" currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2" />
          <SortHeader label="Combined" sortKey="overall_score" currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2 text-right" />
          <SortHeader label="Husband" sortKey="husband_score" currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2 text-right" />
          <SortHeader label="Wife" sortKey="wife_score" currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2 text-right" />
        </tr>
      </thead>
      <tbody>
        {displayData.map((r, i) => (
          <tr key={r.location_name} className="border-b hover:bg-gray-50">
            <td className="py-2 text-gray-400">{i + 1}</td>
            <td className="py-2 font-medium">
              {locationIdForRanking(r) ? (
                <Link to={`/locations/${locationIdForRanking(r)}`} className="text-blue-700 hover:underline">
                  {r.location_name}
                </Link>
              ) : (
                r.location_name
              )}
            </td>
            <td className="py-2 text-gray-500">{r.country}</td>
            <td className="py-2 text-right font-mono">{(r.overall_score ?? 0).toFixed(2)}</td>
            <td className="py-2 text-right font-mono">{(r.husband_score ?? 0).toFixed(2)}</td>
            <td className="py-2 text-right font-mono">{(r.wife_score ?? 0).toFixed(2)}</td>
          </tr>
        ))}
        {rankings.length === 0 && (
          <tr>
            <td colSpan={6}>
              <EmptyState
                icon="chart"
                title="No rankings yet"
                message="Add locations and scores to see rankings here."
                action={<Link to="/locations" className="text-sm text-blue-600 hover:underline">Go to Locations</Link>}
              />
            </td>
          </tr>
        )}
      </tbody>
    </table>
  )
}

export default function Dashboard() {
  const [rankings, setRankings] = useState([])
  const [view, setView] = useState('combined')
  const [locations, setLocations] = useState([])
  const [categories, setCategories] = useState([])
  const [chartType, setChartType] = useState('bar')
  const [selectedLocations, setSelectedLocations] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getRankings(view, { fully_scored_only: true }).then((data) => {
      setRankings(data)
      // Initialize selection: all locations with a non-zero score
      setSelectedLocations((prev) => {
        if (prev.size > 0) return prev
        return new Set(data.filter((r) => r.overall_score > 0).map((r) => r.location_name))
      })
    }).catch((e) => setError(e.message))
  }, [view])

  useEffect(() => {
    Promise.all([getLocations({ fully_scored_only: true }), getCategories()]).then(([locs, cats]) => {
      setLocations(locs)
      setCategories(cats)
    }).catch((e) => setError(e.message)).finally(() => setLoading(false))
  }, [])

  const toggleLocation = (name) => {
    setSelectedLocations((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }

  const selectAll = () => setSelectedLocations(new Set(rankings.map((r) => r.location_name)))
  const selectNone = () => setSelectedLocations(new Set())

  const filteredRankings = rankings.filter((r) => selectedLocations.has(r.location_name))

  const barData = filteredRankings.map((r) => ({
    name: r.location_name,
    combined: +(r.overall_score ?? 0).toFixed(2),
    husband: +(r.husband_score ?? 0).toFixed(2),
    wife: +(r.wife_score ?? 0).toFixed(2),
  }))

  const radarData = categories.map((cat) => {
    const entry = { category: cat.name }
    filteredRankings.forEach((r) => {
      const detail = r.details?.find((d) => d.category_name === cat.name)
      entry[r.location_name] = detail ? detail.score : 0
    })
    return entry
  })

  const palette = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']
  const colorMap = Object.fromEntries(rankings.map((r, i) => [r.location_name, palette[i % palette.length]]))
  const locationIdByKey = Object.fromEntries(
    locations.map((loc) => [`${loc.name.trim().toLowerCase()}::${loc.country.trim().toLowerCase()}`, loc.id]),
  )
  const locationIdForRanking = (ranking) =>
    locationIdByKey[`${ranking.location_name.trim().toLowerCase()}::${ranking.country.trim().toLowerCase()}`]

  if (loading) return <Spinner label="Loading dashboard..." />

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Dashboard</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 mb-4">
          <p className="text-sm font-medium">Failed to load data</p>
          <p className="text-xs mt-1">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-3xl font-bold text-blue-600">{locations.length}</div>
          <div className="text-sm text-gray-500">Total Locations</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-3xl font-bold text-green-600">{rankings.length}</div>
          <div className="text-sm text-gray-500">Ranked Locations</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-3xl font-bold text-purple-600">{categories.length}</div>
          <div className="text-sm text-gray-500">Categories</div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Rankings</h2>
          <div className="flex gap-2">
            {['combined', 'husband', 'wife'].map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-3 py-1 text-sm rounded ${view === v ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                {v.charAt(0).toUpperCase() + v.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <RankingsTable rankings={rankings} locationIdForRanking={locationIdForRanking} />
      </div>

      {rankings.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Comparison Chart</h2>
            <div className="flex gap-2">
              <button
                onClick={() => setChartType('bar')}
                className={`px-3 py-1 text-sm rounded ${chartType === 'bar' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                Bar
              </button>
              <button
                onClick={() => setChartType('radar')}
                className={`px-3 py-1 text-sm rounded ${chartType === 'radar' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                Radar
              </button>
            </div>
          </div>

          {/* Location selector chips */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className="text-xs text-gray-500 mr-1">Show:</span>
            {rankings.map((r, i) => (
              <button
                key={r.location_name}
                onClick={() => toggleLocation(r.location_name)}
                className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${selectedLocations.has(r.location_name)
                  ? 'text-white border-transparent'
                  : 'bg-white text-gray-400 border-gray-300'
                  }`}
                style={selectedLocations.has(r.location_name) ? { backgroundColor: colorMap[r.location_name] } : {}}
              >
                {r.location_name}
              </button>
            ))}
            <span className="text-gray-300 mx-1">|</span>
            <button onClick={selectAll} className="text-xs text-blue-600 hover:underline">All</button>
            <button onClick={selectNone} className="text-xs text-blue-600 hover:underline">None</button>
          </div>

          {chartType === 'bar' ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 10]} />
                <Tooltip />
                <Legend />
                <Bar dataKey="combined" fill="#3b82f6" />
                <Bar dataKey="husband" fill="#10b981" />
                <Bar dataKey="wife" fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <ResponsiveContainer width="100%" height={400}>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="category" tick={{ fontSize: 10 }} />
                <PolarRadiusAxis domain={[0, 10]} />
                {filteredRankings.map((r) => (
                  <Radar
                    key={r.location_name}
                    name={r.location_name}
                    dataKey={r.location_name}
                    stroke={colorMap[r.location_name]}
                    fill={colorMap[r.location_name]}
                    fillOpacity={0.1}
                  />
                ))}
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {rankings.length > 0 && (() => {
        const withDiff = rankings.map((r) => ({ ...r, diff: (r.husband_score ?? 0) - (r.wife_score ?? 0) }))
        const husbandHigher = [...withDiff].sort((a, b) => b.diff - a.diff).slice(0, 3).filter((r) => r.diff > 0)
        const wifeHigher = [...withDiff].sort((a, b) => a.diff - b.diff).slice(0, 3).filter((r) => r.diff < 0)
        const divergent = [...husbandHigher, ...wifeHigher]
        if (divergent.length === 0) return null

        const DiffRow = ({ r }) => (
          <tr className="border-b hover:bg-gray-50">
            <td className="py-2 font-medium">{r.location_name}</td>
            <td className="py-2 text-gray-500">{r.country}</td>
            <td className="py-2 text-right font-mono">{(r.husband_score ?? 0).toFixed(2)}</td>
            <td className="py-2 text-right font-mono">{(r.wife_score ?? 0).toFixed(2)}</td>
            <td className={`py-2 text-right font-mono font-bold ${r.diff > 0 ? 'text-green-600' : 'text-amber-600'}`}>
              {r.diff > 0 ? '+' : ''}{r.diff.toFixed(2)}
            </td>
          </tr>
        )

        return (
          <div className="bg-white rounded-lg shadow p-4 mt-6">
            <h2 className="text-lg font-semibold mb-4">Biggest Score Differences</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-2">Location</th>
                  <th className="py-2">Country</th>
                  <th className="py-2 text-right">Husband</th>
                  <th className="py-2 text-right">Wife</th>
                  <th className="py-2 text-right">Difference</th>
                </tr>
              </thead>
              <tbody>
                {husbandHigher.length > 0 && (
                  <>
                    <tr><td colSpan={5} className="pt-3 pb-1 text-xs font-semibold text-green-700">Husband scores higher</td></tr>
                    {husbandHigher.map((r) => <DiffRow key={r.location_name} r={r} />)}
                  </>
                )}
                {wifeHigher.length > 0 && (
                  <>
                    <tr><td colSpan={5} className="pt-3 pb-1 text-xs font-semibold text-amber-700">Wife scores higher</td></tr>
                    {wifeHigher.map((r) => <DiffRow key={r.location_name} r={r} />)}
                  </>
                )}
              </tbody>
            </table>
          </div>
        )
      })()}
    </div>
  )
}
