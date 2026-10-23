const BASE = '/api/v1'

async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (options.method === 'DELETE' && res.status === 204) return null
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text}`)
  }
  const contentType = res.headers.get('content-type')
  if (contentType && contentType.includes('text/plain')) return res.text()
  return res.json()
}

// Hide locations whose research comes from an older pipeline version (default on).
// Stored per browser; pages that manage locations pass current_research_only: false.
const HIDE_OLDER_KEY = 'relocation.hideOlderResearch'
export const hideOlderResearch = () => {
  try {
    return localStorage.getItem(HIDE_OLDER_KEY) !== '0'
  } catch {
    return true
  }
}
export const setHideOlderResearch = (hide) => {
  try {
    localStorage.setItem(HIDE_OLDER_KEY, hide ? '1' : '0')
  } catch {
    // storage unavailable: the default (hide) applies
  }
}
const withResearchFilter = (params) =>
  'current_research_only' in params || !hideOlderResearch() ? params : { ...params, current_research_only: true }

// Locations
export const getLocations = (params = {}) => {
  const qs = new URLSearchParams(withResearchFilter(params)).toString()
  return request(`${BASE}/locations${qs ? '?' + qs : ''}`)
}
export const getLocation = (id) => request(`${BASE}/locations/${id}`)
export const getLocationCandidates = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`${BASE}/location-candidates${qs ? '?' + qs : ''}`)
}
export const createLocation = (data) => request(`${BASE}/locations`, { method: 'POST', body: JSON.stringify(data) })
export const updateLocation = (id, data) => request(`${BASE}/locations/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteLocation = (id) => request(`${BASE}/locations/${id}`, { method: 'DELETE' })
export const startLocationFullResearch = (id, { forceResearch = false } = {}) => {
  const qs = new URLSearchParams()
  if (forceResearch) qs.set('force_research', 'true')
  return request(`${BASE}/locations/${id}/full-research${qs.size ? `?${qs.toString()}` : ''}`, { method: 'POST' })
}
export const getFullResearchJobs = () => request(`${BASE}/full-research-jobs`)
export const getFullResearchJob = (jobId) => request(`${BASE}/full-research-jobs/${jobId}`)

// Categories
export const getCategories = () => request(`${BASE}/categories`)

// Scores
export const getScores = (params = {}) => {
  const qs = new URLSearchParams(withResearchFilter(params)).toString()
  return request(`${BASE}/scores${qs ? '?' + qs : ''}`)
}
export const getLocationScores = (locationId) => request(`${BASE}/locations/${locationId}/scores`)
export const upsertScore = (data) => request(`${BASE}/scores`, { method: 'POST', body: JSON.stringify(data) })

// Weights
export const getWeights = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`${BASE}/weights${qs ? '?' + qs : ''}`)
}
export const getUserWeights = (userName) => request(`${BASE}/users/${userName}/weights`)
export const upsertWeight = (data) => request(`${BASE}/weights`, { method: 'POST', body: JSON.stringify(data) })

// Research
export const getResearch = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`${BASE}/research${qs ? '?' + qs : ''}`)
}
export const getResearchEntry = (id) => request(`${BASE}/research/${id}`)
export const createResearch = (data) => request(`${BASE}/research`, { method: 'POST', body: JSON.stringify(data) })
export const deleteResearch = (id) => request(`${BASE}/research/${id}`, { method: 'DELETE' })
export const exportLocationResearchMarkdown = (locationId) => request(`${BASE}/locations/${locationId}/research-markdown`)

// Pros/Cons
export const getProsCons = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`${BASE}/pros-cons${qs ? '?' + qs : ''}`)
}
export const getLocationProsCons = (locationId) => request(`${BASE}/locations/${locationId}/pros-cons`)
export const createProCon = (data) => request(`${BASE}/pros-cons`, { method: 'POST', body: JSON.stringify(data) })
export const deleteProCon = (id) => request(`${BASE}/pros-cons/${id}`, { method: 'DELETE' })

// Ocean temperatures
export const getOceanTemperatures = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`${BASE}/ocean-temperatures${qs ? '?' + qs : ''}`)
}
export const getLocationOceanTemperatures = (locationId, params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`${BASE}/locations/${locationId}/ocean-temperatures${qs ? '?' + qs : ''}`)
}

// Visa
export const getVisas = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`${BASE}/visa${qs ? '?' + qs : ''}`)
}
export const getVisa = (id) => request(`${BASE}/visa/${id}`)
export const createVisa = (data) => request(`${BASE}/visa`, { method: 'POST', body: JSON.stringify(data) })
export const updateVisa = (id, data) => request(`${BASE}/visa/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteVisa = (id) => request(`${BASE}/visa/${id}`, { method: 'DELETE' })

// Profile
export const getProfile = () => request(`${BASE}/profile`)
export const upsertProfile = (data) => request(`${BASE}/profile`, { method: 'POST', body: JSON.stringify(data) })
export const exportProfile = () => request(`${BASE}/profile/export`)

// Users
export const getUsers = () => request(`${BASE}/users`)

// Rankings
export const getRankings = (user = 'combined', params = {}) => {
  const qs = new URLSearchParams({ user, ...withResearchFilter(params) }).toString()
  return request(`${BASE}/rankings?${qs}`)
}
