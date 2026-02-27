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

// Locations
export const getLocations = () => request(`${BASE}/locations`)
export const getLocation = (id) => request(`${BASE}/locations/${id}`)
export const createLocation = (data) => request(`${BASE}/locations`, { method: 'POST', body: JSON.stringify(data) })
export const updateLocation = (id, data) => request(`${BASE}/locations/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteLocation = (id) => request(`${BASE}/locations/${id}`, { method: 'DELETE' })

// Categories
export const getCategories = () => request(`${BASE}/categories`)

// Scores
export const getScores = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
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

// Pros/Cons
export const getProsCons = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`${BASE}/pros-cons${qs ? '?' + qs : ''}`)
}
export const getLocationProsCons = (locationId) => request(`${BASE}/locations/${locationId}/pros-cons`)
export const createProCon = (data) => request(`${BASE}/pros-cons`, { method: 'POST', body: JSON.stringify(data) })
export const deleteProCon = (id) => request(`${BASE}/pros-cons/${id}`, { method: 'DELETE' })

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
export const getRankings = (user = 'combined') => request(`${BASE}/rankings?user=${user}`)
