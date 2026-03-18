import { useState, useEffect, useRef, useCallback } from 'react'
import { getCategories, getUsers, getWeights, upsertWeight } from '../api'
import WeightSlider from '../components/WeightSlider'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import { toast } from 'sonner'

export default function Weights() {
  const [categories, setCategories] = useState([])
  const [users, setUsers] = useState([])
  const [weights, setWeights] = useState([])
  const [localOverrides, setLocalOverrides] = useState({})
  const [loading, setLoading] = useState(true)
  const pendingSaves = useRef({})

  const load = async () => {
    const [cats, us, ws] = await Promise.all([getCategories(), getUsers(), getWeights()])
    setCategories(cats)
    setUsers(us)
    setWeights(ws)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const getWeight = (userId, catId) => {
    const key = `${userId}-${catId}`
    if (key in localOverrides) return localOverrides[key]
    const w = weights.find((w) => w.user_id === userId && w.category_id === catId)
    return w ? w.weight : null
  }

  const handleChange = useCallback((userId, catId, value) => {
    const key = `${userId}-${catId}`
    setLocalOverrides((prev) => ({ ...prev, [key]: value }))

    if (pendingSaves.current[key]) clearTimeout(pendingSaves.current[key])

    pendingSaves.current[key] = setTimeout(async () => {
      delete pendingSaves.current[key]
      await upsertWeight({ user_id: userId, category_id: catId, weight: value })
      toast.success('Weight saved')
      const [, , ws] = await Promise.all([getCategories(), getUsers(), getWeights()])
      setWeights(ws)
      setLocalOverrides((prev) => {
        const next = { ...prev }
        delete next[key]
        return next
      })
    }, 600)
  }, [])

  if (loading) return <Spinner label="Loading weights..." />

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Weights</h1>
      <p className="text-sm text-gray-500 mb-6">
        Set how important each category is to each person (0 = not important, 10 = most important). Default weight is 5.
      </p>

      <div className="bg-white rounded-lg shadow p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {users.map((user) => (
            <div key={user.id}>
              <h2 className="text-lg font-semibold mb-4 capitalize">{user.name}</h2>
              <div className="space-y-3">
                {categories.map((cat) => (
                  <WeightSlider
                    key={cat.id}
                    label={cat.name}
                    value={getWeight(user.id, cat.id)}
                    onChange={(v) => handleChange(user.id, cat.id, v)}
                  />
                ))}
              </div>
            </div>
          ))}
          {users.length === 0 && (
            <div className="col-span-2">
              <EmptyState icon="profile" title="No users found" message="Users are created automatically from seed data." />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
