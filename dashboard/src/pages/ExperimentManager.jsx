import React, { useState, useEffect } from 'react'
import MetricCard from '../components/MetricCard'
import { getExperiment, listStrategies } from '../api/client'

export default function ExperimentManager() {
  const [experiment, setExperiment]   = useState(null)
  const [strategies, setStrategies]   = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)

  useEffect(() => {
    Promise.all([getExperiment(), listStrategies()])
      .then(([exp, strats]) => { setExperiment(exp); setStrategies(strats) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const champion   = strategies.find(s => s.status === 'champion')
  const challenger = strategies.find(s => s.status === 'challenger')
  const exp        = experiment

  function pct(n, d) { return d ? `${((n / d) * 100).toFixed(1)}%` : '—' }
  function rate(r)    { return r != null ? `${(r * 100).toFixed(1)}%` : '—' }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Experiment Manager</h1>
      <p className="text-gray-500 text-sm mb-6">Champion vs. challenger A/B experiment performance.</p>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      {/* Header */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Champion"         value={champion?.version ?? '—'}   color="green"  loading={loading} />
        <MetricCard title="Challenger"       value={challenger?.version ?? '—'} color="blue"   loading={loading} />
        <MetricCard title="Challenger Traffic" value={exp ? `${exp.challenger_traffic_pct ?? 0}%` : '—'} color="yellow" loading={loading} />
        <MetricCard title="Status"           value={exp?.status ?? '—'}          color="gray"   loading={loading} />
      </div>

      {exp && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Champion stats */}
          <div className="bg-white rounded-xl border p-5">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <h2 className="font-semibold">Champion — {champion?.version}</h2>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <MetricCard title="Decisions"     value={exp.champion_stats?.total_decisions ?? 0}    color="gray" />
              <MetricCard title="Approval Rate" value={rate(exp.champion_stats?.approval_rate)}      color="green" />
              <MetricCard title="Avg Confidence" value={rate(exp.champion_stats?.avg_confidence)}   color="blue" />
              <MetricCard title="Defaults"       value={exp.champion_stats?.default_count ?? 0}      color={exp.champion_stats?.default_count > 0 ? 'red' : 'gray'} />
            </div>
          </div>

          {/* Challenger stats */}
          <div className="bg-white rounded-xl border p-5">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              <h2 className="font-semibold">Challenger — {challenger?.version ?? 'None'}</h2>
            </div>
            {challenger ? (
              <div className="grid grid-cols-2 gap-3">
                <MetricCard title="Decisions"     value={exp.challenger_stats?.total_decisions ?? 0}  color="gray" />
                <MetricCard title="Approval Rate" value={rate(exp.challenger_stats?.approval_rate)}    color="blue" />
                <MetricCard title="Avg Confidence" value={rate(exp.challenger_stats?.avg_confidence)} color="blue" />
                <MetricCard title="Defaults"       value={exp.challenger_stats?.default_count ?? 0}    color={exp.challenger_stats?.default_count > 0 ? 'red' : 'gray'} />
              </div>
            ) : (
              <p className="text-gray-400 text-sm">No challenger strategy active.</p>
            )}
          </div>
        </div>
      )}

      {/* Lift table */}
      {exp?.champion_stats && exp?.challenger_stats && (
        <div className="bg-white rounded-xl border p-5 mt-6">
          <h2 className="font-semibold mb-3">Lift Analysis</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="pb-2">Metric</th>
                <th className="pb-2">Champion</th>
                <th className="pb-2">Challenger</th>
                <th className="pb-2">Delta</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['Approval Rate', exp.champion_stats.approval_rate, exp.challenger_stats.approval_rate],
                ['Avg Confidence', exp.champion_stats.avg_confidence, exp.challenger_stats.avg_confidence],
              ].map(([label, c, ch]) => {
                const delta = ((ch ?? 0) - (c ?? 0)) * 100
                return (
                  <tr key={label} className="border-b last:border-0">
                    <td className="py-2">{label}</td>
                    <td className="py-2">{rate(c)}</td>
                    <td className="py-2">{rate(ch)}</td>
                    <td className={`py-2 font-medium ${delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {delta >= 0 ? '+' : ''}{delta.toFixed(2)} pp
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
