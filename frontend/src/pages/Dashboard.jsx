import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getRankings, getLocations, getCategories, getUsers } from '../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from 'recharts'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import useSortableTable from '../hooks/useSortableTable'
import SortHeader from '../components/SortHeader'
import { personColor, personLabel, userKey, userScore, withUserScores } from '../utils/people'
import { GROUP_MODES, groupRankings } from '../utils/grouping'

const GROUP_MODE_STORAGE_KEY = 'dashboard.groupMode'

function loadGroupMode() {
  try {
    const saved = localStorage.getItem(GROUP_MODE_STORAGE_KEY)
    return GROUP_MODES.some((m) => m.value === saved) ? saved : 'none'
  } catch {
    return 'none'
  }
}

function RankingsTable({ rankings: baseRankings, users, locationIdForRanking, locationById, groupMode }) {
  const rankings = withUserScores(baseRankings, users)
  const { sortKey, sortDirection, toggleSort, sortedData } = useSortableTable(rankings)
  const [expanded, setExpanded] = useState(new Set())

  const displayData = sortKey ? sortedData : rankings
  const grouped = groupMode !== 'none'
  const groups = groupRankings(displayData, locationById, groupMode)
  const multiGroups = groups.filter((g) => g.rows.length > 1)
  const allExpanded = multiGroups.length > 0 && multiGroups.every((g) => expanded.has(g.key))

  const toggleGroup = (key) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }
  const toggleAll = () => setExpanded(allExpanded ? new Set() : new Set(multiGroups.map((g) => g.key)))

  const locationCell = (r) =>
    locationIdForRanking(r) ? (
      <Link to={`/locations/${locationIdForRanking(r)}`} className="text-blue-700 hover:underline">
        {r.location_name}
      </Link>
    ) : (
      r.location_name
    )

  const scoreCells = (r) => (
    <>
      <td className="py-2 text-right font-mono">{(r.overall_score ?? 0).toFixed(2)}</td>
      {users.map((u) => (
        <td key={u.id} className="py-2 text-right font-mono">{userScore(r, u).toFixed(2)}</td>
      ))}
    </>
  )

  return (
    <>
      {grouped && rankings.length > 0 && (
        <div className="flex items-center gap-3 mb-2 text-xs text-gray-500">
          <span>
            {groups.length} {groupMode === 'country' ? 'countries' : 'regions'} · {displayData.length} places
          </span>
          {multiGroups.length > 0 && (
            <button onClick={toggleAll} className="text-blue-600 hover:underline">
              {allExpanded ? 'Collapse all' : 'Expand all'}
            </button>
          )}
        </div>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="py-2 w-12">#</th>
            <SortHeader label="Location" sortKey="location_name" currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2" />
            <SortHeader label={groupMode === 'region' ? 'Region' : 'Country'} sortKey="country" currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2" />
            <SortHeader label="Combined" sortKey="overall_score" currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2 text-right" />
            {users.map((u) => (
              <SortHeader key={u.id} label={personLabel(u)} sortKey={userKey(u)} currentSortKey={sortKey} sortDirection={sortDirection} onToggle={toggleSort} className="py-2 text-right" />
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((g, i) => {
            const [top, ...rest] = g.rows
            const isOpen = expanded.has(g.key)
            return [
              <tr key={top.location_id} className="border-b hover:bg-gray-50">
                <td className="py-2 text-gray-400">{i + 1}</td>
                <td className="py-2 font-medium">
                  {locationCell(top)}
                  {rest.length > 0 && (
                    <button
                      onClick={() => toggleGroup(g.key)}
                      className="ml-2 px-1.5 py-0.5 text-xs font-normal rounded bg-gray-100 text-gray-600 hover:bg-gray-200"
                      aria-expanded={isOpen}
                    >
                      {isOpen ? '− hide' : `+${rest.length} more`}
                    </button>
                  )}
                </td>
                <td className="py-2 text-gray-500">{grouped ? g.label : top.country}</td>
                {scoreCells(top)}
              </tr>,
              ...(isOpen
                ? rest.map((r) => (
                    <tr key={r.location_id} className="border-b bg-gray-50/60 hover:bg-gray-50 text-gray-600">
                      <td className="py-1.5" />
                      <td className="py-1.5 pl-5">{locationCell(r)}</td>
                      <td className="py-1.5 text-gray-400">{g.label}</td>
                      {scoreCells(r)}
                    </tr>
                  ))
                : []),
            ]
          })}
          {rankings.length === 0 && (
            <tr>
              <td colSpan={4 + users.length}>
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
    </>
  )
}

export default function Dashboard() {
  const [rankings, setRankings] = useState([])
  const [view, setView] = useState('combined')
  const [locations, setLocations] = useState([])
  const [categories, setCategories] = useState([])
  const [users, setUsers] = useState([])
  const [chartType, setChartType] = useState('bar')
  const [selectedLocations, setSelectedLocations] = useState(new Set())
  const [groupMode, setGroupMode] = useState(loadGroupMode)
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
    Promise.all([getLocations({ fully_scored_only: true }), getCategories(), getUsers()]).then(([locs, cats, us]) => {
      setLocations(locs)
      setCategories(cats)
      setUsers(us)
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

  const changeGroupMode = (mode) => {
    setGroupMode(mode)
    try {
      localStorage.setItem(GROUP_MODE_STORAGE_KEY, mode)
    } catch {
      // Storage unavailable; the choice just won't persist.
    }
  }

  const filteredRankings = rankings.filter((r) => selectedLocations.has(r.location_name))

  const barData = filteredRankings.map((r) => ({
    name: r.location_name,
    combined: +(r.overall_score ?? 0).toFixed(2),
    ...Object.fromEntries(users.map((u) => [personLabel(u), +userScore(r, u).toFixed(2)])),
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
  const locationById = Object.fromEntries(locations.map((loc) => [loc.id, loc]))
  // Best place per region/country, in the current ranking order.
  const selectBestPerGroup = () =>
    setSelectedLocations(new Set(groupRankings(rankings, locationById, groupMode).map((g) => g.rows[0].location_name)))

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
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex flex-wrap items-center gap-4">
            <h2 className="text-lg font-semibold">Rankings</h2>
            <div className="flex items-center gap-1.5 text-sm">
              <span className="text-xs text-gray-500">Group by</span>
              <div className="inline-flex rounded border border-gray-300 overflow-hidden">
                {GROUP_MODES.map((m) => (
                  <button
                    key={m.value}
                    onClick={() => changeGroupMode(m.value)}
                    className={`px-2.5 py-0.5 text-xs ${groupMode === m.value ? 'bg-gray-700 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'}`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            {[{ value: 'combined', label: 'Combined' }, ...users.map((u) => ({ value: u.name, label: personLabel(u) }))].map((v) => (
              <button
                key={v.value}
                onClick={() => setView(v.value)}
                className={`px-3 py-1 text-sm rounded ${view === v.value ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>
        <RankingsTable
          rankings={rankings}
          users={users}
          locationIdForRanking={locationIdForRanking}
          locationById={locationById}
          groupMode={groupMode}
        />
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
            {rankings.map((r) => (
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
            {groupMode !== 'none' && (
              <button onClick={selectBestPerGroup} className="text-xs text-blue-600 hover:underline">
                Best per {groupMode}
              </button>
            )}
          </div>

          {chartType === 'bar' ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 10]} />
                <Tooltip />
                <Legend />
                <Bar dataKey="combined" fill="#3b82f6" />
                {users.map((u, i) => (
                  <Bar key={u.id} dataKey={personLabel(u)} fill={personColor(i)} />
                ))}
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

      {rankings.length > 0 && users.length >= 2 && (() => {
        // Compares the first two people.
        const [a, b] = users
        const withDiff = rankings.map((r) => ({ ...r, diff: userScore(r, a) - userScore(r, b) }))
        const aHigher = [...withDiff].sort((x, y) => y.diff - x.diff).slice(0, 3).filter((r) => r.diff > 0)
        const bHigher = [...withDiff].sort((x, y) => x.diff - y.diff).slice(0, 3).filter((r) => r.diff < 0)
        if (aHigher.length + bHigher.length === 0) return null

        const DiffRow = ({ r }) => (
          <tr className="border-b hover:bg-gray-50">
            <td className="py-2 font-medium">{r.location_name}</td>
            <td className="py-2 text-gray-500">{r.country}</td>
            <td className="py-2 text-right font-mono">{userScore(r, a).toFixed(2)}</td>
            <td className="py-2 text-right font-mono">{userScore(r, b).toFixed(2)}</td>
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
                  <th className="py-2 text-right">{personLabel(a)}</th>
                  <th className="py-2 text-right">{personLabel(b)}</th>
                  <th className="py-2 text-right">Difference</th>
                </tr>
              </thead>
              <tbody>
                {aHigher.length > 0 && (
                  <>
                    <tr><td colSpan={5} className="pt-3 pb-1 text-xs font-semibold text-green-700">{personLabel(a)} scores higher</td></tr>
                    {aHigher.map((r) => <DiffRow key={r.location_name} r={r} />)}
                  </>
                )}
                {bHigher.length > 0 && (
                  <>
                    <tr><td colSpan={5} className="pt-3 pb-1 text-xs font-semibold text-amber-700">{personLabel(b)} scores higher</td></tr>
                    {bHigher.map((r) => <DiffRow key={r.location_name} r={r} />)}
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
