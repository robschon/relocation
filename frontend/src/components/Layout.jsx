import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/locations', label: 'Locations' },
  { to: '/scores', label: 'Score Matrix' },
  { to: '/weights', label: 'Weights' },
  { to: '/research', label: 'Research' },
  { to: '/research-jobs', label: 'Research Jobs' },
  { to: '/pros-cons', label: 'Pros & Cons' },
  { to: '/visa', label: 'Visa Info' },
  { to: '/ocean-temperatures', label: 'Ocean Temps' },
  { to: '/profile', label: 'Profile' },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  const handleNavClick = () => {
    setSidebarOpen(false)
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Mobile header */}
      <div className="fixed top-0 left-0 right-0 z-40 flex items-center bg-gray-900 text-white px-4 py-3 md:hidden">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="mr-3 p-1 rounded hover:bg-gray-800"
          aria-label="Toggle menu"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {sidebarOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
        <span className="text-lg font-bold">Relocation Assistant</span>
      </div>

      {/* Backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <nav
        className={`fixed inset-y-0 left-0 z-50 w-56 bg-gray-900 text-white flex-shrink-0 transform transition-transform duration-200 ease-in-out md:relative md:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="p-4 text-lg font-bold border-b border-gray-700">
          Relocation Assistant
        </div>
        <ul className="mt-2">
          {links.map(({ to, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                onClick={handleNavClick}
                className={({ isActive }) =>
                  `block px-4 py-2 text-sm hover:bg-gray-800 ${isActive ? 'bg-gray-800 font-semibold text-blue-400' : 'text-gray-300'}`
                }
              >
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Main content */}
      <main className="flex-1 p-4 pt-16 md:p-6 md:pt-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
