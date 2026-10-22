import { useState, useEffect, useMemo, useCallback } from 'react'
import { getRankings, getCategories, getUserWeights, getUsers } from '../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, ReferenceLine, Cell } from 'recharts'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import { personLabel } from '../utils/people'

const DEFAULT_WEIGHT = 5.0

// weightsByUser: { userId: { categoryName: weight } }; overrides has the same shape.
// Each person's score is their weight-averaged score; overall is the mean across people.
function recomputeRankings(rankings, weightsByUser, overrides) {
  const userIds = Object.keys(weightsByUser)
  const merged = Object.fromEntries(
    userIds.map((id) => [id, { ...weightsByUser[id], ...(overrides[id] || {}) }]),
  )

  return rankings.map((r) => {
    const simScores = {}
    for (const id of userIds) {
      let weightedSum = 0
      let weightSum = 0
      for (const detail of r.details) {
        const wt = merged[id][detail.category_name] ?? DEFAULT_WEIGHT
        weightedSum += detail.score * wt
        weightSum += wt
      }
      simScores[id] = weightSum > 0 ? weightedSum / weightSum : 0
    }
    const values = Object.values(simScores)
    const overall = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
    return { ...r, sim_overall: overall, sim_user_scores: simScores }
  }).sort((a, b) => b.sim_overall - a.sim_overall)
}

export default function SensitivityAnalysis() {
  const [rankings, setRankings] = useState([])
  const [categories, setCategories] = useState([])
  const [users, setUsers] = useState([])
  const [weightsByUser, setWeightsByUser] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [applyTo, setApplyTo] = useState('all') // 'all' or a user id

  useEffect(() => {
    let cancelled = false
    Promise.all([
      getRankings('combined', { fully_scored_only: true }),
      getCategories(),
      getUsers(),
    ]).then(async ([ranks, cats, us]) => {
      const userWeights = await Promise.all(us.map((u) => getUserWeights(u.name)))
      if (cancelled) return
      setRankings(ranks)
      setCategories(cats)
      setUsers(us)
      // Build weight maps keyed by category name (via category_id → name lookup)
      const catIdToName = Object.fromEntries(cats.map((c) => [c.id, c.name]))
      const byUser = {}
      us.forEach((u, i) => {
        byUser[u.id] = {}
        for (const w of userWeights[i]) {
          const name = catIdToName[w.category_id]
          if (name) byUser[u.id][name] = w.weight
        }
      })
      setWeightsByUser(byUser)
      if (cats.length > 0) setSelectedCategory(cats[0].name)
    }).catch((e) => {
      if (!cancelled) setError(e.message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [])

  // For each weight value 0-10, compute the full ranking and track position changes
  const sensitivityData = useMemo(() => {
    if (!selectedCategory || rankings.length === 0) return null

    const baseRanked = recomputeRankings(rankings, weightsByUser, {})
    const basePositions = {}
    baseRanked.forEach((r, i) => { basePositions[r.location_name] = i + 1 })

    // Test weight values from 0 to 10
    const weightValues = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    const locationSeries = {} // { locationName: [{ weight, rank, score }] }

    for (const wv of weightValues) {
      const overrides = {}
      for (const id of Object.keys(weightsByUser)) {
        if (applyTo === 'all' || String(applyTo) === id) overrides[id] = { [selectedCategory]: wv }
      }

      const simRanked = recomputeRankings(rankings, weightsByUser, overrides)
      simRanked.forEach((r, i) => {
        if (!locationSeries[r.location_name]) locationSeries[r.location_name] = []
        locationSeries[r.location_name].push({
          weight: wv,
          rank: i + 1,
          score: +r.sim_overall.toFixed(3),
        })
      })
    }

    return { basePositions, locationSeries, baseRanked }
  }, [selectedCategory, rankings, weightsByUser, applyTo])

  // Find the current weight for the selected category
  const currentWeight = useMemo(() => {
    if (!selectedCategory) return DEFAULT_WEIGHT
    const ids = Object.keys(weightsByUser)
    const weightFor = (id) => weightsByUser[id]?.[selectedCategory] ?? DEFAULT_WEIGHT
    if (applyTo !== 'all') return weightFor(String(applyTo))
    return ids.length ? ids.reduce((sum, id) => sum + weightFor(id), 0) / ids.length : DEFAULT_WEIGHT
  }, [selectedCategory, weightsByUser, applyTo])

  // Compute which locations are most sensitive to this category
  const impactSummary = useMemo(() => {
    if (!sensitivityData) return []

    return Object.entries(sensitivityData.locationSeries).map(([name, series]) => {
      const ranks = series.map((s) => s.rank)
      const scores = series.map((s) => s.score)
      const baseRank = sensitivityData.basePositions[name]
      const bestRank = Math.min(...ranks)
      const worstRank = Math.max(...ranks)
      const rankSwing = worstRank - bestRank
      const scoreSwing = Math.max(...scores) - Math.min(...scores)

      return { name, baseRank, bestRank, worstRank, rankSwing, scoreSwing }
    }).sort((a, b) => b.rankSwing - a.rankSwing || b.scoreSwing - a.scoreSwing)
  }, [sensitivityData])

  // Chart data: score at each weight value for top most-impacted locations
  const chartData = useMemo(() => {
    if (!sensitivityData) return []

    const topLocations = impactSummary.slice(0, 8).map((s) => s.name)
    const weights = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    return weights.map((w) => {
      const entry = { weight: w }
      for (const locName of topLocations) {
        const pt = sensitivityData.locationSeries[locName]?.find((s) => s.weight === w)
        if (pt) entry[locName] = pt.score
      }
      return entry
    })
  }, [sensitivityData, impactSummary])

  const palette = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']

  if (loading) return <Spinner label="Loading sensitivity data..." />

  if (rankings.length === 0) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-4">Sensitivity Analysis</h1>
        <EmptyState
          icon="chart"
          title="No ranked locations"
          message="Add locations and scores to see sensitivity analysis."
        />
      </div>
    )
  }

  const topLocations = impactSummary.slice(0, 8).map((s) => s.name)

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Sensitivity Analysis</h1>
      <p className="text-sm text-gray-500 mb-4">
        See how changing a category's weight affects overall rankings. Pick a category, then see which locations gain or lose the most.
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
            <label className="block text-xs font-medium text-gray-500 mb-1">Category</label>
            <select
              value={selectedCategory || ''}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="border rounded px-3 py-1.5 text-sm bg-white"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.name}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Adjust weight for</label>
            <div className="flex gap-1">
              {[{ value: 'all', label: 'Everyone' }, ...users.map((u) => ({ value: u.id, label: personLabel(u) }))].map((v) => (
                <button
                  key={v.value}
                  onClick={() => setApplyTo(v.value)}
                  className={`px-3 py-1.5 text-sm rounded ${applyTo === v.value ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </div>
          <div className="text-sm text-gray-500">
            Current weight: <span className="font-mono font-semibold">{currentWeight.toFixed(1)}</span>
          </div>
        </div>
      </div>

      {/* Score trajectories chart */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <h2 className="text-lg font-semibold mb-1">Score Trajectories</h2>
        <p className="text-xs text-gray-500 mb-4">
          How overall scores change as the <span className="font-semibold">{selectedCategory}</span> weight moves from 0 to 10 (top 8 most affected locations shown)
        </p>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={chartData} barCategoryGap="15%">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="weight" label={{ value: 'Weight', position: 'insideBottom', offset: -2, fontSize: 12 }} />
            <YAxis domain={['auto', 'auto']} tick={{ fontSize: 12 }} label={{ value: 'Overall Score', angle: -90, position: 'insideLeft', fontSize: 12 }} />
            <Tooltip formatter={(value) => value.toFixed(3)} />
            <Legend />
            <ReferenceLine x={Math.round(currentWeight)} stroke="#6b7280" strokeDasharray="3 3" label={{ value: 'Current', position: 'top', fontSize: 10 }} />
            {topLocations.map((name, i) => (
              <Bar key={name} dataKey={name} fill={palette[i % palette.length]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Impact summary table */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-semibold mb-1">Ranking Impact</h2>
        <p className="text-xs text-gray-500 mb-4">
          How much each location's rank and score change when <span className="font-semibold">{selectedCategory}</span> weight varies from 0 to 10
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-2">Location</th>
                <th className="py-2 text-right">Current Rank</th>
                <th className="py-2 text-right">Best Rank</th>
                <th className="py-2 text-right">Worst Rank</th>
                <th className="py-2 text-right">Rank Swing</th>
                <th className="py-2 text-right">Score Swing</th>
              </tr>
            </thead>
            <tbody>
              {impactSummary.map((row) => (
                <tr key={row.name} className="border-b hover:bg-gray-50">
                  <td className="py-2 font-medium">{row.name}</td>
                  <td className="py-2 text-right font-mono">{row.baseRank}</td>
                  <td className="py-2 text-right font-mono text-green-600">{row.bestRank}</td>
                  <td className="py-2 text-right font-mono text-red-600">{row.worstRank}</td>
                  <td className="py-2 text-right font-mono">
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      row.rankSwing === 0 ? 'bg-gray-100 text-gray-500' :
                      row.rankSwing <= 2 ? 'bg-yellow-100 text-yellow-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {row.rankSwing === 0 ? 'None' : `${row.rankSwing} positions`}
                    </span>
                  </td>
                  <td className="py-2 text-right font-mono">{row.scoreSwing.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
