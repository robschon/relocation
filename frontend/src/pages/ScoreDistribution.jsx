import { useState, useEffect, useMemo } from 'react'
import { getScores, getCategories, getLocations } from '../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { scoreToColor } from '../utils/scoreColor'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'

const BINS = [
  { label: '1-2', min: 1, max: 2 },
  { label: '3-4', min: 3, max: 4 },
  { label: '5-6', min: 5, max: 6 },
  { label: '7-8', min: 7, max: 8 },
  { label: '9-10', min: 9, max: 10 },
]

function getBinLabel(score) {
  for (const bin of BINS) {
    if (score >= bin.min && score <= bin.max) return bin.label
  }
  return '1-2'
}

function computeStats(values) {
  if (values.length === 0) return { mean: 0, median: 0, stdDev: 0, min: 0, max: 0, count: 0 }
  const sorted = [...values].sort((a, b) => a - b)
  const sum = sorted.reduce((a, b) => a + b, 0)
  const mean = sum / sorted.length
  const median = sorted.length % 2 === 0
    ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
    : sorted[Math.floor(sorted.length / 2)]
  const variance = sorted.reduce((acc, v) => acc + (v - mean) ** 2, 0) / sorted.length
  const stdDev = Math.sqrt(variance)
  return { mean, median, stdDev, min: sorted[0], max: sorted[sorted.length - 1], count: sorted.length }
}

export default function ScoreDistribution() {
  const [scores, setScores] = useState([])
  const [categories, setCategories] = useState([])
  const [locations, setLocations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [viewMode, setViewMode] = useState('histogram') // 'histogram' or 'byCategory'

  useEffect(() => {
    let cancelled = false
    Promise.all([
      getScores(),
      getCategories(),
      getLocations({ fully_scored_only: true }),
    ]).then(([scrs, cats, locs]) => {
      if (cancelled) return
      setScores(scrs)
      setCategories(cats)
      setLocations(locs)
    }).catch((e) => {
      if (!cancelled) setError(e.message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [])

  // Build lookup maps
  const categoryMap = useMemo(() => Object.fromEntries(categories.map((c) => [c.id, c.name])), [categories])
  const locationMap = useMemo(() => Object.fromEntries(locations.map((l) => [l.id, l.name])), [locations])

  // Enrich scores with names
  const enrichedScores = useMemo(() =>
    scores
      .filter((s) => locationMap[s.location_id]) // only fully scored locations
      .map((s) => ({
        ...s,
        category_name: categoryMap[s.category_id] || `Category ${s.category_id}`,
        location_name: locationMap[s.location_id] || `Location ${s.location_id}`,
      })),
    [scores, categoryMap, locationMap]
  )

  // Filtered scores based on selected category
  const filteredScores = useMemo(() => {
    if (selectedCategory === 'all') return enrichedScores
    return enrichedScores.filter((s) => s.category_name === selectedCategory)
  }, [enrichedScores, selectedCategory])

  // Histogram data
  const histogramData = useMemo(() => {
    const bins = BINS.map((b) => ({ ...b, count: 0, locations: [] }))
    for (const s of filteredScores) {
      const bin = bins.find((b) => s.score >= b.min && s.score <= b.max)
      if (bin) {
        bin.count++
        bin.locations.push(`${s.location_name}: ${s.score}`)
      }
    }
    return bins
  }, [filteredScores])

  // Per-category distribution data (box-plot style summary)
  const categoryStats = useMemo(() => {
    const grouped = {}
    for (const s of enrichedScores) {
      if (!grouped[s.category_name]) grouped[s.category_name] = []
      grouped[s.category_name].push(s.score)
    }
    return categories
      .map((c) => {
        const values = grouped[c.name] || []
        const stats = computeStats(values)
        return { name: c.name, ...stats }
      })
      .sort((a, b) => a.mean - b.mean)
  }, [enrichedScores, categories])

  // Per-category bar chart data: mean with range
  const categoryChartData = useMemo(() =>
    categoryStats.map((s) => ({
      name: s.name.length > 20 ? s.name.slice(0, 18) + '...' : s.name,
      fullName: s.name,
      mean: +s.mean.toFixed(2),
      min: s.min,
      max: s.max,
      stdDev: +s.stdDev.toFixed(2),
      spread: +(s.max - s.min).toFixed(1),
    })),
    [categoryStats]
  )

  // Overall stats
  const overallStats = useMemo(() => computeStats(filteredScores.map((s) => s.score)), [filteredScores])

  // Scores per location for the detail table
  const locationBreakdown = useMemo(() => {
    if (selectedCategory === 'all') return null
    return filteredScores
      .map((s) => ({ name: s.location_name, score: s.score }))
      .sort((a, b) => b.score - a.score)
  }, [filteredScores, selectedCategory])

  if (loading) return <Spinner label="Loading score data..." />

  if (scores.length === 0) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-4">Score Distribution</h1>
        <EmptyState
          icon="chart"
          title="No scores yet"
          message="Add scores to locations to see distribution analysis."
        />
      </div>
    )
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    return (
      <div className="bg-white border border-gray-200 rounded shadow-lg p-3 text-sm max-w-xs">
        <p className="font-semibold mb-1">{label}</p>
        {payload.map((p) => (
          <p key={p.name} style={{ color: p.color }}>
            {p.name}: {p.value}
          </p>
        ))}
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Score Distribution</h1>
      <p className="text-sm text-gray-500 mb-4">
        Analyze how scores are distributed across locations and categories. Find which categories differentiate locations vs. which cluster tightly.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 mb-4">
          <p className="text-sm font-medium">Failed to load data</p>
          <p className="text-xs mt-1">{error}</p>
        </div>
      )}

      {/* Controls */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">View</label>
            <div className="flex gap-1">
              <button
                onClick={() => setViewMode('histogram')}
                className={`px-3 py-1.5 text-sm rounded ${viewMode === 'histogram' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                Histogram
              </button>
              <button
                onClick={() => setViewMode('byCategory')}
                className={`px-3 py-1.5 text-sm rounded ${viewMode === 'byCategory' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                By Category
              </button>
            </div>
          </div>
          {viewMode === 'histogram' && (
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Category Filter</label>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="border rounded px-3 py-1.5 text-sm bg-white"
              >
                <option value="all">All Categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.name}>{c.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Summary stats */}
      {viewMode === 'histogram' && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-blue-600">{overallStats.mean.toFixed(1)}</div>
            <div className="text-xs text-gray-500">Mean</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-purple-600">{overallStats.median.toFixed(1)}</div>
            <div className="text-xs text-gray-500">Median</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-amber-600">{overallStats.stdDev.toFixed(2)}</div>
            <div className="text-xs text-gray-500">Std Dev</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-green-600">{overallStats.min}–{overallStats.max}</div>
            <div className="text-xs text-gray-500">Range</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-gray-600">{overallStats.count}</div>
            <div className="text-xs text-gray-500">Scores</div>
          </div>
        </div>
      )}

      {viewMode === 'histogram' ? (
        <>
          {/* Histogram chart */}
          <div className="bg-white rounded-lg shadow p-4 mb-6">
            <h2 className="text-lg font-semibold mb-1">
              Score Distribution{selectedCategory !== 'all' ? `: ${selectedCategory}` : ''}
            </h2>
            <p className="text-xs text-gray-500 mb-4">Number of scores in each range</p>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={histogramData} barCategoryGap="20%">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const d = payload[0].payload
                    return (
                      <div className="bg-white border border-gray-200 rounded shadow-lg p-3 text-sm max-w-xs">
                        <p className="font-semibold">Scores {d.label}</p>
                        <p className="text-gray-600">{d.count} score{d.count !== 1 ? 's' : ''}</p>
                        {d.locations.length > 0 && d.locations.length <= 10 && (
                          <div className="mt-1 text-xs text-gray-400">
                            {d.locations.map((l, i) => <div key={i}>{l}</div>)}
                          </div>
                        )}
                      </div>
                    )
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {histogramData.map((entry) => (
                    <Cell key={entry.label} fill={scoreToColor((entry.min + entry.max) / 2)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Location breakdown table (when a specific category is selected) */}
          {locationBreakdown && (
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold mb-4">Scores by Location: {selectedCategory}</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="py-2 w-12">#</th>
                      <th className="py-2">Location</th>
                      <th className="py-2 text-right">Score</th>
                      <th className="py-2 w-48">Distribution</th>
                    </tr>
                  </thead>
                  <tbody>
                    {locationBreakdown.map((row, i) => (
                      <tr key={row.name} className="border-b hover:bg-gray-50">
                        <td className="py-2 text-gray-400">{i + 1}</td>
                        <td className="py-2 font-medium">{row.name}</td>
                        <td className="py-2 text-right font-mono">{row.score}</td>
                        <td className="py-2">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                              <div
                                className="h-3 rounded-full"
                                style={{
                                  width: `${(row.score / 10) * 100}%`,
                                  backgroundColor: scoreToColor(row.score),
                                }}
                              />
                            </div>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          {/* By-category view: average scores per category */}
          <div className="bg-white rounded-lg shadow p-4 mb-6">
            <h2 className="text-lg font-semibold mb-1">Average Score by Category</h2>
            <p className="text-xs text-gray-500 mb-4">
              Categories sorted by average score. Low averages = harder to satisfy; tight spread = less differentiating.
            </p>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={categoryChartData} layout="vertical" margin={{ left: 10, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 10]} tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={160} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const d = payload[0].payload
                    return (
                      <div className="bg-white border border-gray-200 rounded shadow-lg p-3 text-sm">
                        <p className="font-semibold">{d.fullName}</p>
                        <p>Mean: <span className="font-mono">{d.mean}</span></p>
                        <p>Range: <span className="font-mono">{d.min}–{d.max}</span> (spread: {d.spread})</p>
                        <p>Std Dev: <span className="font-mono">{d.stdDev}</span></p>
                      </div>
                    )
                  }}
                />
                <Bar dataKey="mean" radius={[0, 4, 4, 0]}>
                  {categoryChartData.map((entry) => (
                    <Cell key={entry.name} fill={scoreToColor(entry.mean)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Category stats table */}
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">Category Statistics</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2">Category</th>
                    <th className="py-2 text-right">Mean</th>
                    <th className="py-2 text-right">Median</th>
                    <th className="py-2 text-right">Std Dev</th>
                    <th className="py-2 text-right">Min</th>
                    <th className="py-2 text-right">Max</th>
                    <th className="py-2 text-right">Spread</th>
                    <th className="py-2 text-center">Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryStats.map((row) => {
                    const spread = row.max - row.min
                    const signal = row.stdDev >= 2 ? 'High' : row.stdDev >= 1.2 ? 'Medium' : 'Low'
                    const signalColor = signal === 'High' ? 'bg-green-100 text-green-700' : signal === 'Medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
                    return (
                      <tr key={row.name} className="border-b hover:bg-gray-50">
                        <td className="py-2 font-medium">{row.name}</td>
                        <td className="py-2 text-right font-mono">{row.mean.toFixed(2)}</td>
                        <td className="py-2 text-right font-mono">{row.median.toFixed(1)}</td>
                        <td className="py-2 text-right font-mono">{row.stdDev.toFixed(2)}</td>
                        <td className="py-2 text-right font-mono">{row.min}</td>
                        <td className="py-2 text-right font-mono">{row.max}</td>
                        <td className="py-2 text-right font-mono">{spread}</td>
                        <td className="py-2 text-center">
                          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${signalColor}`}>
                            {signal}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <p className="text-xs text-gray-400 mt-3">
                Signal = how much this category differentiates locations. High standard deviation means locations vary widely on this category, making it more useful for ranking.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
