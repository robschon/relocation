export default function SortHeader({ label, sortKey, currentSortKey, sortDirection, onToggle, className = '' }) {
  const isActive = currentSortKey === sortKey
  return (
    <th
      className={`py-2 cursor-pointer select-none hover:text-gray-700 group ${className}`}
      onClick={() => onToggle(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <svg
          className={`w-3 h-3 transition-opacity ${isActive ? 'opacity-100 text-gray-700' : 'opacity-0 group-hover:opacity-40 text-gray-400'}`}
          viewBox="0 0 10 10"
          fill="currentColor"
        >
          {isActive && sortDirection === 'desc'
            ? <path d="M5 7L1 3h8z" />
            : <path d="M5 3L1 7h8z" />}
        </svg>
      </span>
    </th>
  )
}
