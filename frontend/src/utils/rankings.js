function locationKey(location) {
  return `${location.name.trim().toLowerCase()}::${location.country.trim().toLowerCase()}`
}

export function sortLocationsByOverallRank(locations, rankings) {
  const rankIndex = new Map(
    rankings.map((ranking, index) => [
      `${ranking.location_name.trim().toLowerCase()}::${ranking.country.trim().toLowerCase()}`,
      index,
    ]),
  )

  return [...locations].sort((a, b) => {
    const aRank = rankIndex.get(locationKey(a)) ?? Number.POSITIVE_INFINITY
    const bRank = rankIndex.get(locationKey(b)) ?? Number.POSITIVE_INFINITY

    if (aRank !== bRank) return aRank - bRank

    const byName = a.name.localeCompare(b.name)
    if (byName !== 0) return byName

    return a.country.localeCompare(b.country)
  })
}
