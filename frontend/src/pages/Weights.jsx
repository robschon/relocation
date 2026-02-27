import { useState, useEffect } from 'react'
import { getCategories, getUsers, getWeights, upsertWeight } from '../api'
import WeightSlider from '../components/WeightSlider'

export default function Weights() {
  const [categories, setCategories] = useState([])
  const [users, setUsers] = useState([])
  const [weights, setWeights] = useState([])

  const load = async () => {
    const [cats, us, ws] = await Promise.all([getCategories(), getUsers(), getWeights()])
    setCategories(cats)
    setUsers(us)
    setWeights(ws)
  }

  useEffect(() => { load() }, [])

  const getWeight = (userId, catId) => {
    const w = weights.find((w) => w.user_id === userId && w.category_id === catId)
    return w ? w.weight : null
  }

  const handleChange = async (userId, catId, value) => {
    await upsertWeight({ user_id: userId, category_id: catId, weight: value })
    load()
  }

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
            <p className="text-gray-400 text-sm col-span-2">No users found.</p>
          )}
        </div>
      </div>
    </div>
  )
}
