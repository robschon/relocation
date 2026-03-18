import { useState, useEffect } from 'react'
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
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getLocations(), getRankings('combined')]).then(([locs, ranks]) => {
      setLocations(locs)
      setRankings(ranks)
      setLoading(false)
    })
  }, [])

  if (loading) return <Spinner label="Loading map..." />

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

  const scoreField = SCORE_FIELDS[view]

  // Compute actual score range for the current view
  const scoredValues = markers
    .map((m) => m.ranking?.[scoreField])
    .filter((s) => s != null && s > 0)
  const minScore = scoredValues.length > 0 ? Math.min(...scoredValues) : 0
  const maxScore = scoredValues.length > 0 ? Math.max(...scoredValues) : 10

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Map</h1>
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
          {markers.map((m) => {
            const score = m.ranking?.[scoreField]
            const hasScore = score != null && score > 0
            return (
              <CircleMarker
                key={m.id}
                center={[m.latitude, m.longitude]}
                radius={hasScore ? scoreRadius(score, minScore, maxScore) : 5}
                pathOptions={{
                  fillColor: hasScore ? scoreToColor(score, minScore, maxScore) : '#9ca3af',
                  color: hasScore ? scoreToColor(score, minScore, maxScore) : '#9ca3af',
                  fillOpacity: hasScore ? 0.8 : 0.4,
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
                        <div>Combined: <span className="font-mono">{m.ranking.overall_score.toFixed(2)}</span></div>
                        <div>Husband: <span className="font-mono">{m.ranking.husband_score.toFixed(2)}</span></div>
                        <div>Wife: <span className="font-mono">{m.ranking.wife_score.toFixed(2)}</span></div>
                      </div>
                    ) : (
                      <div className="mt-1 text-gray-400 italic">No scores yet</div>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            )
          })}
        </MapContainer>
      </div>

      {/* Score legend */}
      <div className="flex items-center gap-2 mt-3 text-xs text-gray-500">
        <span>{scoredValues.length > 0 ? minScore.toFixed(1) : 'Low'}</span>
        <div
          className="h-3 w-32 rounded"
          style={{
            background: 'linear-gradient(to right, #ef4444, #eab308, #22c55e)',
          }}
        />
        <span>{scoredValues.length > 0 ? maxScore.toFixed(1) : 'High'}</span>
        <span className="ml-4 inline-block w-3 h-3 rounded-full bg-gray-400 opacity-40" />
        <span>Unscored</span>
      </div>
    </div>
  )
}
