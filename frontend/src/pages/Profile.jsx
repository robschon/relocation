import { useState, useEffect } from 'react'
import { getProfile, exportProfile } from '../api'

export default function Profile() {
  const [responses, setResponses] = useState([])

  useEffect(() => {
    getProfile().then(setResponses)
  }, [])

  const grouped = responses.reduce((acc, r) => {
    ;(acc[r.section] = acc[r.section] || []).push(r)
    return acc
  }, {})

  const handleExport = async () => {
    const markdown = await exportProfile()
    const blob = new Blob([markdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'relocation-profile.md'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Profile</h1>
        <button
          onClick={handleExport}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
        >
          Export Markdown
        </button>
      </div>

      {Object.entries(grouped).map(([section, items]) => (
        <div key={section} className="bg-white rounded-lg shadow mb-4">
          <div className="px-4 py-3 border-b bg-gray-50 font-semibold">{section}</div>
          <div className="divide-y">
            {items.map((item) => (
              <div key={item.id} className="px-4 py-3">
                <p className="text-sm font-medium text-gray-600">{item.question}</p>
                <p className="text-sm text-gray-800 mt-1">
                  {item.answer || <span className="text-gray-400 italic">Not answered</span>}
                </p>
              </div>
            ))}
          </div>
        </div>
      ))}

      {responses.length === 0 && (
        <div className="text-center text-gray-400 py-12">
          No profile responses yet. Use the CLI to fill out your profile.
        </div>
      )}
    </div>
  )
}
