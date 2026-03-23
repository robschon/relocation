import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { getLocations, getRankings } from '../api'
import { scoreToColor } from '../utils/scoreColor'
import Spinner from '../components/Spinner'

const SCORE_FIELDS = {
  combined: 'overall_score',
  husband: 'husband_score',
  wife: 'wife_score',
}

function scoreRadius(score, minScore, maxScore) {
  if (score == null) return 5
  const range = maxScore - minScore
  const t = range === 0 ? 0.5 : (score - minScore) / range
  return 6 + t * 10 // 6–16px
}

export default function MapView() {
  const [locations, setLocations] = useState([])
  const [rankings, setRankings] = useState([])
  const [view, setView] = useState('combined')
  const [topCount, setTopCount] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      getLocations({ fully_scored_only: true }),
      getRankings('combined', { fully_scored_only: true }),
    ]).then(([locs, ranks]) => {
      setLocations(locs)
      setRankings(ranks)
    }).catch((e) => setError(e.message)).finally(() => setLoading(false))
  }, [])

  // Build ranking lookup by name::country key
  const rankingByKey = Object.fromEntries(
    rankings.map((r) => [
      `${r.location_name.trim().toLowerCase()}::${r.country.trim().toLowerCase()}`,
      r,
    ])
  )

  // Join locations with rankings, skip those without coordinates
  const markers = locations
    .filter((loc) => loc.latitude != null && loc.longitude != null)
    .map((loc) => {
      const key = `${loc.name.trim().toLowerCase()}::${loc.country.trim().toLowerCase()}`
      const ranking = rankingByKey[key]
      return { ...loc, ranking }
    })
    .filter((marker) => marker.ranking)

  const scoreField = SCORE_FIELDS[view]

  const rankedMarkers = useMemo(
    () => [...markers].sort((a, b) => (b.ranking?.[scoreField] ?? 0) - (a.ranking?.[scoreField] ?? 0)),
    [markers, scoreField],
  )

  const displayedMarkers = useMemo(() => {
    if (topCount === 'all') return rankedMarkers
    const limit = Number(topCount)
    if (!Number.isFinite(limit) || limit <= 0) return rankedMarkers
    return rankedMarkers.slice(0, limit)
  }, [rankedMarkers, topCount])

  // Compute actual score range for the current view
  const scoredValues = displayedMarkers
    .map((m) => m.ranking?.[scoreField])
    .filter((s) => s != null && s > 0)
  const minScore = scoredValues.length > 0 ? Math.min(...scoredValues) : 0
  const maxScore = scoredValues.length > 0 ? Math.max(...scoredValues) : 10

  if (loading) return <Spinner label="Loading map..." />

  if (error) return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Map</h1>
      <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4">
        <p className="text-sm font-medium">Failed to load data</p>
        <p className="text-xs mt-1">{error}</p>
      </div>
    </div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Map</h1>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600" htmlFor="map-top-count">Show</label>
          <select
            id="map-top-count"
            value={topCount}
            onChange={(e) => setTopCount(e.target.value)}
            className="border rounded px-3 py-1 text-sm bg-white"
          >
            <option value="all">All results</option>
            <option value="5">Top 5</option>
            <option value="10">Top 10</option>
            <option value="25">Top 25</option>
            <option value="50">Top 50</option>
          </select>
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
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden" style={{ height: 'calc(100vh - 12rem)' }}>
        <MapContainer
          center={[20, 0]}
          zoom={2}
          style={{ height: '100%', width: '100%' }}
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {displayedMarkers.map((m) => {
            const score = m.ranking?.[scoreField]
            return (
              <CircleMarker
                key={m.id}
                center={[m.latitude, m.longitude]}
                radius={scoreRadius(score, minScore, maxScore)}
                pathOptions={{
                  fillColor: scoreToColor(score, minScore, maxScore),
                  color: scoreToColor(score, minScore, maxScore),
                  fillOpacity: 0.8,
                  weight: 1,
                }}
              >
                <Popup>
                  <div className="text-sm">
                    <Link to={`/locations/${m.id}`} className="font-semibold text-blue-700 hover:underline">
                      {m.name}
                    </Link>
                    <div className="text-gray-500">{m.country}</div>
                    {m.ranking ? (
                      <div className="mt-1 space-y-0.5">
                        <div>Combined: <span className="font-mono">{(m.ranking.overall_score ?? 0).toFixed(2)}</span></div>
                        <div>Husband: <span className="font-mono">{(m.ranking.husband_score ?? 0).toFixed(2)}</span></div>
                        <div>Wife: <span className="font-mono">{(m.ranking.wife_score ?? 0).toFixed(2)}</span></div>
                      </div>
                    ) : null}
                  </div>
                </Popup>
              </CircleMarker>
            )
          })}
        </MapContainer>
      </div>

      {/* Score legend */}
      <div className="flex items-center gap-2 mt-3 text-xs text-gray-500">
        <span>{displayedMarkers.length} shown</span>
        <span>{scoredValues.length > 0 ? minScore.toFixed(1) : 'Low'}</span>
        <div
          className="h-3 w-32 rounded"
          style={{
            background: 'linear-gradient(to right, #ef4444, #eab308, #22c55e)',
          }}
        />
        <span>{scoredValues.length > 0 ? maxScore.toFixed(1) : 'High'}</span>
      </div>
    </div>
  )
}
