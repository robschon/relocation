import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Locations from './pages/Locations'
import LocationDetail from './pages/LocationDetail'
import ScoreMatrix from './pages/ScoreMatrix'
import Weights from './pages/Weights'
import Research from './pages/Research'
import ProsCons from './pages/ProsCons'
import Visa from './pages/Visa'
import Profile from './pages/Profile'
import OceanTemperatures from './pages/OceanTemperatures'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/locations" element={<Locations />} />
        <Route path="/locations/:id" element={<LocationDetail />} />
        <Route path="/scores" element={<ScoreMatrix />} />
        <Route path="/weights" element={<Weights />} />
        <Route path="/research" element={<Research />} />
        <Route path="/pros-cons" element={<ProsCons />} />
        <Route path="/visa" element={<Visa />} />
        <Route path="/ocean-temperatures" element={<OceanTemperatures />} />
        <Route path="/profile" element={<Profile />} />
      </Route>
    </Routes>
  )
}
