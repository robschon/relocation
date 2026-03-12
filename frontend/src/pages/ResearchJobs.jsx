import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getFullResearchJobs } from '../api'

function statusClasses(status) {
  if (status === 'running') return 'bg-blue-100 text-blue-800'
  if (status === 'queued') return 'bg-amber-100 text-amber-800'
  if (status === 'completed') return 'bg-emerald-100 text-emerald-800'
  if (status === 'failed') return 'bg-rose-100 text-rose-800'
  return 'bg-gray-100 text-gray-700'
}

function formatDateTime(value) {
  if (!value) return 'N/A'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed)
}

function formatDuration(startedAt, finishedAt) {
  if (!startedAt) return 'N/A'
  const start = new Date(startedAt)
  const end = finishedAt ? new Date(finishedAt) : new Date()
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 'N/A'

  const totalSeconds = Math.max(0, Math.round((end.getTime() - start.getTime()) / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (minutes === 0) return `${seconds}s`
  if (minutes < 60) return `${minutes}m ${seconds}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

function latestOutputLine(job) {
  if (!job.output || job.output.length === 0) return ''
  return job.output[job.output.length - 1]
}

export default function ResearchJobs() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedJobId, setSelectedJobId] = useState(null)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const data = await getFullResearchJobs()
        if (!cancelled) {
          setJobs(data)
          setError('')
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Failed to load research jobs.')
          setLoading(false)
        }
      }
    }

    void load()
    const intervalId = window.setInterval(() => {
      void load()
    }, 2000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  const activeJobs = jobs.filter((job) => job.status === 'queued' || job.status === 'running')
  const completedJobs = jobs.filter((job) => job.status === 'completed')
  const failedJobs = jobs.filter((job) => job.status === 'failed')
  const selectedJob = jobs.find((job) => job.id === selectedJobId) || null

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Research Jobs</h1>
          <p className="text-sm text-gray-500 mt-1">
            Live status for queued, running, completed, and failed full research jobs.
          </p>
        </div>
        <div className="text-xs text-gray-500">
          Refreshes every 2 seconds
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-2xl font-bold text-gray-900">{jobs.length}</div>
          <div className="text-sm text-gray-500">Total tracked jobs</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-2xl font-bold text-blue-600">{activeJobs.length}</div>
          <div className="text-sm text-gray-500">Active now</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-2xl font-bold text-emerald-600">{completedJobs.length}</div>
          <div className="text-sm text-gray-500">Completed</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-2xl font-bold text-rose-600">{failedJobs.length}</div>
          <div className="text-sm text-gray-500">Failed</div>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.9fr)] gap-6">
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold">All Jobs</h2>
            {!loading && <span className="text-xs text-gray-500">{jobs.length} shown</span>}
          </div>

          {loading ? (
            <div className="p-6 text-sm text-gray-500">Loading research jobs...</div>
          ) : jobs.length === 0 ? (
            <div className="p-6 text-sm text-gray-500">No full research jobs have been started in this backend session.</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50 text-left text-gray-500">
                    <th className="px-4 py-3">Location</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Step</th>
                    <th className="px-4 py-3">Started</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Latest</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr
                      key={job.id}
                      className={`border-b hover:bg-gray-50 cursor-pointer ${selectedJobId === job.id ? 'bg-blue-50/60' : ''}`}
                      onClick={() => setSelectedJobId(selectedJobId === job.id ? null : job.id)}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{job.location_name}</div>
                        <div className="text-xs text-gray-400">#{job.location_id}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusClasses(job.status)}`}>
                          {job.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{job.step || 'N/A'}</td>
                      <td className="px-4 py-3 text-gray-600">{formatDateTime(job.started_at)}</td>
                      <td className="px-4 py-3 text-gray-600">{formatDuration(job.started_at, job.finished_at)}</td>
                      <td className="px-4 py-3 text-gray-500 max-w-xs truncate">
                        {job.error || latestOutputLine(job) || 'No output yet'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Job Log</h2>
            {selectedJob && (
              <Link
                to={`/locations/${selectedJob.location_id}`}
                className="text-xs text-blue-600 hover:underline"
              >
                Open location
              </Link>
            )}
          </div>

          {!selectedJob ? (
            <div className="p-6 text-sm text-gray-500">Select a job to inspect its live output.</div>
          ) : (
            <>
              <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900">{selectedJob.location_name}</span>
                  <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusClasses(selectedJob.status)}`}>
                    {selectedJob.status}
                  </span>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  Started {formatDateTime(selectedJob.started_at)}
                  {selectedJob.finished_at ? ` • Finished ${formatDateTime(selectedJob.finished_at)}` : ''}
                  {selectedJob.step ? ` • Step ${selectedJob.step}` : ''}
                </div>
                {selectedJob.error && (
                  <div className="mt-2 text-xs text-rose-600">
                    {selectedJob.error}
                  </div>
                )}
              </div>

              <div className="max-h-[70vh] overflow-auto bg-gray-950 text-gray-100 p-4 text-xs font-mono leading-relaxed whitespace-pre-wrap">
                {selectedJob.output && selectedJob.output.length > 0
                  ? selectedJob.output.join('\n')
                  : 'No output yet. This panel updates live while the job runs.'}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
