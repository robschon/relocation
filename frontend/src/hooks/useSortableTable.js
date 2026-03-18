import { useState, useMemo } from 'react'

export default function useSortableTable(data, defaultSortKey = null, defaultDirection = 'asc') {
  const [sortKey, setSortKey] = useState(defaultSortKey)
  const [sortDirection, setSortDirection] = useState(defaultDirection)

  const toggleSort = (key) => {
    if (sortKey !== key) {
      setSortKey(key)
      setSortDirection('asc')
    } else if (sortDirection === 'asc') {
      setSortDirection('desc')
    } else {
      setSortKey(null)
      setSortDirection('asc')
    }
  }

  const sortedData = useMemo(() => {
    if (!sortKey) return data

    return [...data].sort((a, b) => {
      let aVal = typeof sortKey === 'function' ? sortKey(a) : a[sortKey]
      let bVal = typeof sortKey === 'function' ? sortKey(b) : b[sortKey]

      if (aVal == null) aVal = ''
      if (bVal == null) bVal = ''

      let cmp
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        cmp = aVal - bVal
      } else if (aVal instanceof Date && bVal instanceof Date) {
        cmp = aVal.getTime() - bVal.getTime()
      } else {
        cmp = String(aVal).localeCompare(String(bVal))
      }

      return sortDirection === 'desc' ? -cmp : cmp
    })
  }, [data, sortKey, sortDirection])

  return { sortKey, sortDirection, toggleSort, sortedData }
}
