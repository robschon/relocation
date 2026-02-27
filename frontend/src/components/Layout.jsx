import { NavLink, Outlet } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/locations', label: 'Locations' },
  { to: '/scores', label: 'Score Matrix' },
  { to: '/weights', label: 'Weights' },
  { to: '/research', label: 'Research' },
  { to: '/pros-cons', label: 'Pros & Cons' },
  { to: '/visa', label: 'Visa Info' },
  { to: '/profile', label: 'Profile' },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <nav className="w-56 bg-gray-900 text-white flex-shrink-0">
        <div className="p-4 text-lg font-bold border-b border-gray-700">
          Relocation Planner
        </div>
        <ul className="mt-2">
          {links.map(({ to, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
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
      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
