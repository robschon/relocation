import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'sonner'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Locations from './pages/Locations'
import LocationDetail from './pages/LocationDetail'
import ScoreMatrix from './pages/ScoreMatrix'
import Weights from './pages/Weights'
import Research from './pages/Research'
import ResearchJobs from './pages/ResearchJobs'
import ProsCons from './pages/ProsCons'
import Visa from './pages/Visa'
import Profile from './pages/Profile'
import OceanTemperatures from './pages/OceanTemperatures'
import Compare from './pages/Compare'
import MapView from './pages/MapView'
import SensitivityAnalysis from './pages/SensitivityAnalysis'
import ScoreDistribution from './pages/ScoreDistribution'

export default function App() {
  return (
    <>
      <Toaster position="bottom-right" richColors closeButton />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/locations" element={<Locations />} />
          <Route path="/locations/:id" element={<LocationDetail />} />
          <Route path="/scores" element={<ScoreMatrix />} />
          <Route path="/weights" element={<Weights />} />
          <Route path="/research" element={<Research />} />
          <Route path="/research-jobs" element={<ResearchJobs />} />
          <Route path="/pros-cons" element={<ProsCons />} />
          <Route path="/visa" element={<Visa />} />
          <Route path="/ocean-temperatures" element={<OceanTemperatures />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/sensitivity" element={<SensitivityAnalysis />} />
          <Route path="/distribution" element={<ScoreDistribution />} />
        </Route>
      </Routes>
    </>
  )
}
