import { useState, useEffect } from 'react'
import { getRankings, getLocations, getCategories } from '../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from 'recharts'

export default function Dashboard() {
  const [rankings, setRankings] = useState([])
  const [view, setView] = useState('combined')
  const [locations, setLocations] = useState([])
  const [categories, setCategories] = useState([])
  const [chartType, setChartType] = useState('bar')
  const [selectedLocations, setSelectedLocations] = useState(new Set())

  useEffect(() => {
    getRankings(view).then((data) => {
      setRankings(data)
      // Initialize selection: all locations with a non-zero score
      setSelectedLocations((prev) => {
        if (prev.size > 0) return prev
        return new Set(data.filter((r) => r.overall_score > 0).map((r) => r.location_name))
      })
    })
  }, [view])

  useEffect(() => {
    getLocations().then(setLocations)
    getCategories().then(setCategories)
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
    combined: +r.overall_score.toFixed(2),
    husband: +r.husband_score.toFixed(2),
    wife: +r.wife_score.toFixed(2),
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

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Dashboard</h1>

      <div className="grid grid-cols-3 gap-4 mb-6">
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
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="py-2 w-12">#</th>
              <th className="py-2">Location</th>
              <th className="py-2">Country</th>
              <th className="py-2 text-right">Combined</th>
              <th className="py-2 text-right">Husband</th>
              <th className="py-2 text-right">Wife</th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((r, i) => (
              <tr key={r.location_name} className="border-b hover:bg-gray-50">
                <td className="py-2 text-gray-400">{i + 1}</td>
                <td className="py-2 font-medium">{r.location_name}</td>
                <td className="py-2 text-gray-500">{r.country}</td>
                <td className="py-2 text-right font-mono">{r.overall_score.toFixed(2)}</td>
                <td className="py-2 text-right font-mono">{r.husband_score.toFixed(2)}</td>
                <td className="py-2 text-right font-mono">{r.wife_score.toFixed(2)}</td>
              </tr>
            ))}
            {rankings.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-gray-400">
                  No rankings yet. Add locations and scores to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
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
        const divergent = [...rankings]
          .map((r) => ({ ...r, diff: r.husband_score - r.wife_score }))
          .sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff))
          .slice(0, 5)
        return (
          <div className="bg-white rounded-lg shadow p-4 mt-6">
            <h2 className="text-lg font-semibold mb-4">Biggest Score Differences</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-2 w-12">#</th>
                  <th className="py-2">Location</th>
                  <th className="py-2">Country</th>
                  <th className="py-2 text-right">Husband</th>
                  <th className="py-2 text-right">Wife</th>
                  <th className="py-2 text-right">Difference</th>
                </tr>
              </thead>
              <tbody>
                {divergent.map((r, i) => (
                  <tr key={r.location_name} className="border-b hover:bg-gray-50">
                    <td className="py-2 text-gray-400">{i + 1}</td>
                    <td className="py-2 font-medium">{r.location_name}</td>
                    <td className="py-2 text-gray-500">{r.country}</td>
                    <td className="py-2 text-right font-mono">{r.husband_score.toFixed(2)}</td>
                    <td className="py-2 text-right font-mono">{r.wife_score.toFixed(2)}</td>
                    <td className={`py-2 text-right font-mono font-bold ${r.diff > 0 ? 'text-green-600' : r.diff < 0 ? 'text-amber-600' : 'text-gray-500'}`}>
                      {r.diff > 0 ? '+' : ''}{r.diff.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-400 mt-2">
              <span className="text-green-600">+</span> = husband scores higher, <span className="text-amber-600">&minus;</span> = wife scores higher
            </p>
          </div>
        )
      })()}
    </div>
  )
}
