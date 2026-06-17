import React, { useState } from 'react'
import MetricCard from '../components/MetricCard'
import { createSimulation, getSimulation } from '../api/client'

const DATE_RANGES = ['last_7_days', 'last_30_days', 'last_90_days', 'all']

export default function SimulationRunner() {
  const [form, setForm] = useState({
    strategy_version: 'v1.0.0',
    sample_size: 100,
    date_range: 'last_90_days',
  })
  const [result, setResult] = useState(null)
  const [simId, setSimId]   = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  async function run() {
    setRunning(true)
    setResult(null)
    setError(null)
    try {
      const sim = await createSimulation(form)
      const id = sim.simulation_id
      setSimId(id)

      // Poll until complete (max 60s)
      let attempts = 0
      const check = async () => {
        const data = await getSimulation(id)
        if (data.status === 'complete') {
          setResult(data)
          setRunning(false)
        } else if (data.status === 'failed') {
          setError(`Simulation failed: ${data.error_message || 'unknown'}`)
          setRunning(false)
        } else if (++attempts < 30) {
          setTimeout(check, 2000)
        } else {
          setError('Timed out waiting for simulation')
          setRunning(false)
        }
      }
      await check()
    } catch (e) {
      setError(e.message)
      setRunning(false)
    }
  }

  const baseline  = result?.baseline_distribution ?? {}
  const simulated = result?.simulated_distribution ?? {}
  const approvalRate = simulated.total > 0
    ? ((simulated.APPROVE ?? 0) / simulated.total * 100).toFixed(1) + '%'
    : '—'

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Simulation Runner</h1>
      <p className="text-gray-500 text-sm mb-6">Re-score historical decisions under a new strategy version to measure impact before deployment.</p>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Config form */}
        <div className="bg-white rounded-xl border p-5 lg:col-span-1">
          <h2 className="font-semibold mb-4">Configuration</h2>
          <div className="space-y-3">
            <label className="block text-sm">
              <span className="text-gray-700 font-medium">Strategy Version</span>
              <input value={form.strategy_version}
                onChange={e => setForm(f => ({...f, strategy_version: e.target.value}))}
                className="mt-1 block w-full border rounded px-2 py-1.5 text-sm font-mono" />
            </label>
            <label className="block text-sm">
              <span className="text-gray-700 font-medium">Sample Size</span>
              <input type="number" min={1} max={5000} value={form.sample_size}
                onChange={e => setForm(f => ({...f, sample_size: parseInt(e.target.value) || 100}))}
                className="mt-1 block w-full border rounded px-2 py-1.5 text-sm" />
            </label>
            <label className="block text-sm">
              <span className="text-gray-700 font-medium">Date Range</span>
              <select value={form.date_range}
                onChange={e => setForm(f => ({...f, date_range: e.target.value}))}
                className="mt-1 block w-full border rounded px-2 py-1.5 text-sm">
                {DATE_RANGES.map(r => <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>)}
              </select>
            </label>
            <button onClick={run} disabled={running}
              className="w-full bg-brand-500 hover:bg-brand-700 disabled:opacity-50 text-white text-sm py-2 rounded-lg font-medium mt-2">
              {running ? 'Running…' : 'Run Simulation'}
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-2">
          {running && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 text-center text-blue-700">
              <div className="animate-spin w-8 h-8 border-4 border-blue-300 border-t-blue-600 rounded-full mx-auto mb-3" />
              <p className="font-medium">Simulation running…</p>
              <p className="text-xs mt-1">This may take 1–2 minutes.</p>
            </div>
          )}
          {result && (
            <div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <MetricCard title="Cases Sampled"     value={result.sample_size}  color="gray" />
                <MetricCard title="Simulated Approval" value={approvalRate}        color="green" />
                <MetricCard title="Changed Decisions" value={result.changed_decisions?.length ?? 0} color="blue" />
                <MetricCard title="P-Value"           value={result.p_value != null ? result.p_value.toFixed(4) : '—'} color={result.p_value < 0.05 ? 'red' : 'gray'} />
              </div>
              <div className="bg-white rounded-xl border p-5 mb-3">
                <h3 className="font-semibold mb-3">Decision Distribution</h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-gray-500 border-b">
                      <th className="pb-2 text-left">Recommendation</th>
                      <th className="pb-2 text-right">Baseline</th>
                      <th className="pb-2 text-right">Simulated</th>
                      <th className="pb-2 text-right">Delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {['APPROVE', 'MANUAL_REVIEW', 'DECLINE'].map(rec => {
                      const b = baseline[rec] ?? 0
                      const s = simulated[rec] ?? 0
                      return (
                        <tr key={rec} className="border-b last:border-0">
                          <td className="py-2 font-mono text-xs">{rec}</td>
                          <td className="py-2 text-right">{b}</td>
                          <td className="py-2 text-right">{s}</td>
                          <td className={`py-2 text-right font-medium ${s - b > 0 ? 'text-green-600' : s - b < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                            {s - b > 0 ? '+' : ''}{s - b}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {simId && (
                <a href={`/api/v1/simulations/${simId}/report`} target="_blank" rel="noreferrer"
                  className="block text-center text-brand-500 hover:text-brand-700 text-sm font-medium">
                  View Full HTML Report →
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
