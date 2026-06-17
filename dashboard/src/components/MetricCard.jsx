import React from 'react'

export default function MetricCard({ title, value, sub, color = 'blue', loading }) {
  const colors = {
    blue:   'bg-blue-50 border-blue-200 text-blue-700',
    green:  'bg-green-50 border-green-200 text-green-700',
    red:    'bg-red-50 border-red-200 text-red-700',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    gray:   'bg-gray-50 border-gray-200 text-gray-700',
  }
  return (
    <div className={`rounded-xl border p-4 ${colors[color] ?? colors.blue}`}>
      <p className="text-xs font-semibold uppercase tracking-wide opacity-70">{title}</p>
      {loading
        ? <div className="h-7 w-20 bg-current opacity-20 rounded animate-pulse mt-1" />
        : <p className="text-2xl font-bold mt-0.5">{value ?? '—'}</p>
      }
      {sub && <p className="text-xs mt-1 opacity-60">{sub}</p>}
    </div>
  )
}
