import { useEffect, useMemo, useState } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'
import { getLocations, getLocationOceanTemperatures } from '../api'

const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export default function OceanTemperatures() {
  const [locations, setLocations] = useState([])
  const [locationId, setLocationId] = useState('')
  const [locationInput, setLocationInput] = useState('')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const loadLocations = async () => {
      const locs = await getLocations({ fully_scored_only: true })
      if (cancelled) return
      setLocations(locs)
      if (locs.length > 0) {
        setLocationId(String(locs[0].id))
      }
    }
    void loadLocations()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!locationId) return
    let cancelled = false
    const loadData = async () => {
      setLoading(true)
      setError('')
      try {
        const data = await getLocationOceanTemperatures(locationId)
        if (cancelled) return
        setRows(data)
      } catch (err) {
        if (cancelled) return
        setRows([])
        setError(err.message || 'Failed to load ocean temperatures.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void loadData()
    return () => { cancelled = true }
  }, [locationId])

  const sortedLocations = useMemo(
    () => locations.slice().sort((a, b) => a.name.localeCompare(b.name)),
    [locations],
  )

  const locationLabelById = useMemo(
    () =>
      Object.fromEntries(
        sortedLocations.map((loc) => [String(loc.id), `${loc.name} (${loc.country})`]),
      ),
    [sortedLocations],
  )

  const locationIdByLabel = useMemo(
    () =>
      Object.fromEntries(
        sortedLocations.map((loc) => [`${loc.name} (${loc.country})`, String(loc.id)]),
      ),
    [sortedLocations],
  )

  useEffect(() => {
    if (!locationId) return
    const label = locationLabelById[String(locationId)]
    if (label) {
      setLocationInput(label)
    }
  }, [locationId, locationLabelById])

  const latestRows = useMemo(() => {
    if (rows.length === 0) return []
    const latestBaseline = Math.max(...rows.map((row) => row.baseline_end_year))
    const candidates = rows.filter((row) => row.baseline_end_year === latestBaseline)
    const baselineStart = Math.max(...candidates.map((row) => row.baseline_start_year))
    return candidates
      .filter((row) => row.baseline_start_year === baselineStart)
      .sort((a, b) => a.month - b.month)
  }, [rows])

  const chartData = latestRows.map((row) => ({
    month: monthLabels[row.month - 1] || `M${row.month}`,
    avg: row.avg_temp_c,
    min: row.min_temp_c,
    max: row.max_temp_c,
  }))

  const yDomain = useMemo(() => {
    if (chartData.length === 0) return ['auto', 'auto']
    const values = chartData.flatMap((row) => [row.avg, row.min, row.max]).filter((value) => value != null)
    if (values.length === 0) return ['auto', 'auto']
    const comfortThresholdC = 19
    const min = Math.min(...values, comfortThresholdC)
    const max = Math.max(...values, comfortThresholdC)
    return [Math.floor(min - 1), Math.ceil(max + 1)]
  }, [chartData])

  const selectedLocation = locations.find((loc) => String(loc.id) === String(locationId))
  const qualityFlags = Array.from(new Set(latestRows.map((row) => row.quality_flag).filter((flag) => flag && flag !== 'ok')))
  const baselineLabel = latestRows[0]
    ? `${latestRows[0].baseline_start_year}-${latestRows[0].baseline_end_year}`
    : 'N/A'

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Ocean Temperatures</h1>
      <p className="text-sm text-gray-500 mb-4">Monthly average sea surface temperature for each location.</p>

      <div className="bg-white rounded-lg shadow p-4 mb-4 flex flex-wrap items-center gap-3">
        <label htmlFor="ocean-location" className="text-sm text-gray-600">Location (type to search)</label>
        <input
          id="ocean-location"
          list="ocean-location-options"
          value={locationInput}
          onChange={(e) => {
            const next = e.target.value
            setLocationInput(next)
            const matchedId = locationIdByLabel[next]
            if (matchedId) {
              setLocationId(matchedId)
            }
          }}
          className="border rounded px-3 py-2 text-sm bg-white min-w-64"
          placeholder="Start typing a location..."
        />
        <datalist id="ocean-location-options">
          {sortedLocations.map((loc) => (
            <option key={loc.id} value={`${loc.name} (${loc.country})`} />
          ))}
        </datalist>
        <span className="text-xs text-gray-500">Baseline: {baselineLabel}</span>
      </div>

      <div className="bg-white rounded-lg shadow p-4 mb-4">
        {loading && <p className="text-sm text-gray-500">Loading ocean temperature data...</p>}
        {!loading && error && <p className="text-sm text-red-600">{error}</p>}
        {!loading && !error && latestRows.length === 0 && (
          <p className="text-sm text-gray-500">No ocean temperature data found for this location.</p>
        )}
        {!loading && !error && latestRows.length > 0 && (
          <>
            <h2 className="text-sm font-semibold text-gray-700 mb-2">
              {selectedLocation ? `${selectedLocation.name}, ${selectedLocation.country}` : 'Selected location'}
            </h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis unit="°C" domain={yDomain} />
                  <Tooltip formatter={(value) => `${Number(value).toFixed(1)}°C`} />
                  <ReferenceLine
                    y={19}
                    stroke="#d97706"
                    strokeDasharray="6 4"
                    label={{ value: '19°C comfort', position: 'insideTopRight', fill: '#92400e', fontSize: 12 }}
                  />
                  <Line type="monotone" dataKey="avg" stroke="#2563eb" strokeWidth={3} dot />
                  <Line type="monotone" dataKey="min" stroke="#059669" strokeWidth={1.5} dot={false} />
                  <Line type="monotone" dataKey="max" stroke="#dc2626" strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Dashed line marks the 19°C comfort threshold for year-round swimming.
            </p>
          </>
        )}
      </div>

      {!loading && !error && latestRows.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          {qualityFlags.length > 0 && (
            <p className="text-xs text-amber-700 mb-2">Quality flags: {qualityFlags.join(', ')}</p>
          )}
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="py-2">Month</th>
                <th className="py-2 text-right">Avg (°C)</th>
                <th className="py-2 text-right">Min (°C)</th>
                <th className="py-2 text-right">Max (°C)</th>
              </tr>
            </thead>
            <tbody>
              {latestRows.map((row) => (
                <tr key={row.month} className="border-b last:border-b-0">
                  <td className="py-2">{monthLabels[row.month - 1] || row.month}</td>
                  <td className="py-2 text-right font-mono">{row.avg_temp_c.toFixed(1)}</td>
                  <td className="py-2 text-right font-mono">{row.min_temp_c?.toFixed(1) ?? '-'}</td>
                  <td className="py-2 text-right font-mono">{row.max_temp_c?.toFixed(1) ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
