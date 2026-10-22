import { useState, useEffect, useMemo } from 'react'
import { getRankings, getCategories, getWeights, getUsers } from '../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts'
import Spinner from '../components/Spinner'
import { personLabel, userScore, userWeighted } from '../utils/people'

export default function Compare() {
  const [rankings, setRankings] = useState([])
  const [categories, setCategories] = useState([])
  const [weights, setWeights] = useState([])
  const [users, setUsers] = useState([])
  const [selectedLocations, setSelectedLocations] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedCategory, setExpandedCategory] = useState(null)

  useEffect(() => {
    Promise.all([getRankings('combined', { fully_scored_only: true }), getCategories(), getWeights(), getUsers()])
      .then(([r, c, w, u]) => {
        setRankings(r)
        setCategories(c)
        setWeights(w)
        setUsers(u)
        setSelectedLocations(new Set(r.filter((x) => x.overall_score > 0).map((x) => x.location_name)))
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const toggleLocation = (name) => {
    setSelectedLocations((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  // This page compares the first two people.
  const [personA, personB] = users
  const labelA = personLabel(personA)
  const labelB = personLabel(personB)
  const scoreA = (r) => (personA ? userScore(r, personA) : 0)
  const scoreB = (r) => (personB ? userScore(r, personB) : 0)

  const getWeight = (userId, catId) => {
    const w = weights.find((w) => w.user_id === userId && w.category_id === catId)
    return w ? w.weight : 0
  }

  const filteredRankings = rankings.filter((r) => selectedLocations.has(r.location_name))

  // Section 1: Bar chart data sorted by absolute difference
  const barData = useMemo(() =>
    filteredRankings
      .map((r) => ({
        name: r.location_name,
        personA: +scoreA(r).toFixed(2),
        personB: +scoreB(r).toFixed(2),
        diff: Math.abs(scoreA(r) - scoreB(r)),
      }))
      .sort((a, b) => b.diff - a.diff),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filteredRankings, personA, personB],
  )

  // Section 3: All locations sorted by absolute difference
  const divergenceData = useMemo(() =>
    rankings
      .map((r) => ({
        ...r,
        diff: scoreA(r) - scoreB(r),
        absDiff: Math.abs(scoreA(r) - scoreB(r)),
      }))
      .sort((a, b) => b.absDiff - a.absDiff),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rankings, personA, personB],
  )

  const diffRowColor = (absDiff) => {
    if (absDiff < 0.5) return 'bg-green-50'
    if (absDiff <= 2) return 'bg-amber-50'
    return 'bg-red-50'
  }

  if (loading) return <Spinner label="Loading comparison data..." />

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">{labelA} vs. {labelB} Comparison</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 mb-4">
          <p className="text-sm font-medium">Failed to load data</p>
          <p className="text-xs mt-1">{error}</p>
        </div>
      )}
      <p className="text-sm text-gray-500 mb-4">Side-by-side view of how each person scores and weights locations.</p>

      {/* Location selector chips */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <span className="text-xs text-gray-500 mr-1">Locations:</span>
        {rankings.map((r) => (
          <button
            key={r.location_name}
            onClick={() => toggleLocation(r.location_name)}
            className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
              selectedLocations.has(r.location_name)
                ? 'bg-blue-600 text-white border-transparent'
                : 'bg-white text-gray-400 border-gray-300'
            }`}
          >
            {r.location_name}
          </button>
        ))}
        <span className="text-gray-300 mx-1">|</span>
        <button onClick={() => setSelectedLocations(new Set(rankings.map((r) => r.location_name)))} className="text-xs text-blue-600 hover:underline">All</button>
        <button onClick={() => setSelectedLocations(new Set())} className="text-xs text-blue-600 hover:underline">None</button>
      </div>

      {/* Section 1: Overall Score Comparison */}
      {filteredRankings.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <h2 className="text-lg font-semibold mb-4">Overall Score Comparison</h2>
          <ResponsiveContainer width="100%" height={Math.max(200, barData.length * 45 + 40)}>
            <BarChart data={barData} layout="vertical" margin={{ left: 20, right: 20 }}>
              <XAxis type="number" domain={[0, 10]} />
              <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="personA" fill="#10b981" name={labelA} barSize={16} />
              <Bar dataKey="personB" fill="#f59e0b" name={labelB} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Section 2: Category-by-Category Breakdown */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <h2 className="text-lg font-semibold mb-4">Category-by-Category Breakdown</h2>
        <div className="space-y-1">
          {categories.map((cat) => {
            const hWeight = personA ? getWeight(personA.id, cat.id) : 0
            const wWeight = personB ? getWeight(personB.id, cat.id) : 0
            const weightDiff = hWeight - wWeight
            const isExpanded = expandedCategory === cat.id

            return (
              <div key={cat.id} className="border rounded-lg">
                <button
                  onClick={() => setExpandedCategory(isExpanded ? null : cat.id)}
                  className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-sm">{cat.name}</span>
                    <span className="inline-flex items-center gap-1 text-xs">
                      <span className="px-1.5 py-0.5 rounded bg-green-100 text-green-800 font-mono">{hWeight}</span>
                      <span className="text-gray-400">vs</span>
                      <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-mono">{wWeight}</span>
                    </span>
                    {weightDiff !== 0 && (
                      <span className={`text-xs ${weightDiff > 0 ? 'text-green-600' : 'text-amber-600'}`}>
                        {weightDiff > 0 ? `${labelA} cares more` : `${labelB} cares more`}
                      </span>
                    )}
                  </div>
                  <svg className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                  </svg>
                </button>

                {isExpanded && filteredRankings.length > 0 && (
                  <div className="px-4 pb-3">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-500 text-xs">
                          <th className="py-1">Location</th>
                          <th className="py-1 text-right">{labelA} score</th>
                          <th className="py-1 text-right">{labelA} weighted</th>
                          <th className="py-1 text-right">{labelB} score</th>
                          <th className="py-1 text-right">{labelB} weighted</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredRankings.map((r) => {
                          const detail = r.details?.find((d) => d.category_name === cat.name)
                          if (!detail) return null
                          const weightedA = personA ? userWeighted(detail, personA) : null
                          const weightedB = personB ? userWeighted(detail, personB) : null
                          return (
                            <tr key={r.location_name} className="border-b last:border-0">
                              <td className="py-1.5 text-gray-700">{r.location_name}</td>
                              <td className="py-1.5 text-right font-mono">{detail.score ?? '—'}</td>
                              <td className="py-1.5 text-right font-mono text-green-700">{weightedA?.toFixed(2) ?? '—'}</td>
                              <td className="py-1.5 text-right font-mono">{detail.score ?? '—'}</td>
                              <td className="py-1.5 text-right font-mono text-amber-700">{weightedB?.toFixed(2) ?? '—'}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Section 3: Agreement & Divergence Summary */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-semibold mb-4">Agreement & Divergence</h2>
        <div className="text-xs text-gray-500 mb-3 flex gap-4">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-100 border border-green-200"></span>Agree (diff &lt; 0.5)</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-100 border border-amber-200"></span>Somewhat differ (0.5–2)</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-100 border border-red-200"></span>Strongly differ (&gt; 2)</span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="py-2">Location</th>
              <th className="py-2 text-right">{labelA}</th>
              <th className="py-2 text-right">{labelB}</th>
              <th className="py-2 text-right">Difference</th>
              <th className="py-2 text-right">Who Prefers</th>
            </tr>
          </thead>
          <tbody>
            {divergenceData.map((r) => (
              <tr key={r.location_name} className={`border-b ${diffRowColor(r.absDiff)}`}>
                <td className="py-2 font-medium">{r.location_name}</td>
                <td className="py-2 text-right font-mono">{scoreA(r).toFixed(2)}</td>
                <td className="py-2 text-right font-mono">{scoreB(r).toFixed(2)}</td>
                <td className="py-2 text-right font-mono font-bold">{(r.absDiff ?? 0).toFixed(2)}</td>
                <td className="py-2 text-right text-xs">
                  {r.absDiff < 0.1 ? (
                    <span className="text-gray-400">Equal</span>
                  ) : r.diff > 0 ? (
                    <span className="text-green-600">{labelA}</span>
                  ) : (
                    <span className="text-amber-600">{labelB}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
