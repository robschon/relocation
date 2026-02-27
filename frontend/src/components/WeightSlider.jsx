export default function WeightSlider({ value, onChange, label }) {
  return (
    <div className="space-y-1">
      {label && <span className="text-sm text-gray-600">{label}</span>}
      <div className="flex items-center gap-3">
        <input
          type="range"
          min={0}
          max={10}
          step={0.5}
          value={value ?? 5}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 h-2 rounded-lg appearance-none cursor-pointer accent-purple-600"
        />
        <span className="text-sm font-bold text-gray-700 min-w-[2.5rem] text-center">
          {value ?? '—'}
        </span>
      </div>
    </div>
  )
}
