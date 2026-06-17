import React from 'react'
import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/strategy',   label: 'Strategy',    icon: '📋' },
  { to: '/rules',      label: 'Rule Editor', icon: '✏️' },
  { to: '/simulation', label: 'Simulation',  icon: '🔬' },
  { to: '/experiment', label: 'Experiments', icon: '⚗️' },
  { to: '/analytics',  label: 'Analytics',   icon: '📊' },
  { to: '/decisions',  label: 'Decisions',   icon: '🔍' },
  { to: '/fairness',   label: 'Fairness',    icon: '⚖️' },
  { to: '/evals',      label: 'Evals',       icon: '✅' },
]

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 bg-brand-900 text-white flex flex-col flex-shrink-0">
        <div className="px-4 py-5 border-b border-brand-700">
          <p className="text-xs text-blue-300 font-medium uppercase tracking-widest">AI Decisioning</p>
          <p className="text-lg font-bold">Platform</p>
        </div>
        <nav className="flex-1 py-4 overflow-y-auto">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors
                 ${isActive ? 'bg-brand-700 text-white' : 'text-blue-200 hover:bg-brand-700 hover:text-white'}`
              }
            >
              <span>{icon}</span> {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-brand-700 text-xs text-blue-400">
          v1.0.0 · Apache 2.0
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
