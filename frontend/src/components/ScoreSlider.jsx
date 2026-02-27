export default function ScoreSlider({ value, onChange, label }) {
  const color = value <= 3 ? 'bg-red-500' : value <= 6 ? 'bg-yellow-500' : 'bg-green-500'
  return (
    <div className="flex items-center gap-3">
      {label && <span className="text-sm text-gray-600 w-32 truncate">{label}</span>}
      <input
        type="range"
        min={1}
        max={10}
        value={value || 5}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 h-2 rounded-lg appearance-none cursor-pointer accent-blue-600"
      />
      <span className={`text-sm font-bold text-white px-2 py-0.5 rounded ${color} min-w-[2rem] text-center`}>
        {value || '—'}
      </span>
    </div>
  )
}
