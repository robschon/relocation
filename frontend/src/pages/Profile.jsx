import { useState, useEffect } from 'react'
import { getProfile, upsertProfile, exportProfile } from '../api'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import { toast } from 'sonner'

export default function Profile() {
  const [responses, setResponses] = useState([])
  const [editingId, setEditingId] = useState(null)
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = () => getProfile().then((data) => {
    setResponses(data)
    setLoading(false)
  })

  useEffect(() => { load() }, [])

  const grouped = responses.reduce((acc, r) => {
    ; (acc[r.section] = acc[r.section] || []).push(r)
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

  const startEdit = (item) => {
    setEditingId(item.id)
    setEditValue(item.answer || '')
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditValue('')
  }

  const saveEdit = async (item) => {
    setSaving(true)
    try {
      await upsertProfile({ question_key: item.question_key, answer: editValue })
      toast.success('Answer saved')
      setEditingId(null)
      setEditValue('')
      await load()
    } finally {
      setSaving(false)
    }
  }

  const handleKeyDown = (e, item) => {
    if (e.key === 'Escape') cancelEdit()
    if (e.key === 'Enter' && e.metaKey) saveEdit(item)
  }

  if (loading) return <Spinner label="Loading profile..." />

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

      <p className="text-sm text-gray-500 mb-4">
        Click any answer to edit it inline. Press <kbd className="px-1 py-0.5 bg-gray-100 border rounded text-xs">⌘ Enter</kbd> to save or <kbd className="px-1 py-0.5 bg-gray-100 border rounded text-xs">Esc</kbd> to cancel.
      </p>

      {Object.entries(grouped).map(([section, items]) => (
        <div key={section} className="bg-white rounded-lg shadow mb-4">
          <div className="px-4 py-3 border-b bg-gray-50 font-semibold">{section}</div>
          <div className="divide-y">
            {items.map((item) => (
              <div key={item.id} className="px-4 py-3">
                <p className="text-sm font-medium text-gray-600">{item.question}</p>

                {editingId === item.id ? (
                  <div className="mt-2">
                    <textarea
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e, item)}
                      rows={3}
                      autoFocus
                      className="w-full border border-blue-400 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <div className="flex gap-2 mt-2">
                      <button
                        onClick={() => saveEdit(item)}
                        disabled={saving}
                        className="bg-blue-600 text-white px-3 py-1 text-xs rounded hover:bg-blue-700 disabled:opacity-50"
                      >
                        {saving ? 'Saving…' : 'Save'}
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="bg-gray-200 text-gray-700 px-3 py-1 text-xs rounded hover:bg-gray-300"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <p
                    className="text-sm text-gray-800 mt-1 cursor-pointer hover:bg-blue-50 rounded px-1 py-0.5 -mx-1 transition-colors"
                    onClick={() => startEdit(item)}
                    title="Click to edit"
                  >
                    {item.answer || <span className="text-gray-400 italic">Click to add answer…</span>}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {responses.length === 0 && (
        <EmptyState
          icon="profile"
          title="No profile responses yet"
          message="Use the CLI to fill out your profile, then answers will appear here for editing."
        />
      )}
    </div>
  )
}
