// Helpers for per-person ranking data. The API returns scores and weights keyed by user id
// (e.g. ranking.user_scores["1"]); these keep pages from hard-coding who the people are.

export const PERSON_COLORS = ['#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6']

export const personColor = (index) => PERSON_COLORS[index % PERSON_COLORS.length]

export const personLabel = (user) => user?.display_name || user?.name || 'Unknown'

// Sort/chart key for a user's score when flattened onto a ranking row.
export const userKey = (user) => `user_${user.id}`

export const userScore = (ranking, user) => ranking?.user_scores?.[user.id] ?? 0

export const userWeight = (detail, user) => detail?.weights?.[user.id]

export const userWeighted = (detail, user) => detail?.weighted?.[user.id]

// Copy each user's score onto the row as `user_<id>` so tables can sort by it.
export const withUserScores = (rankings, users) =>
  rankings.map((r) => ({
    ...r,
    ...Object.fromEntries(users.map((u) => [userKey(u), userScore(r, u)])),
  }))
