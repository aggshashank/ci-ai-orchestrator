import React, { useState } from 'react'
import MetricCard from '../components/MetricCard'
import { createSimulation, getSimulation } from '../api/client'

const WORKFLOWS = ['ORIGINATION', 'DELINQUENCY', 'LIMIT_REVIEW', 'CROSS_SELL']

export default function SimulationRunner() {
  const [form, setForm] = useState({
    workflow_type: 'ORIGINATION',
    strategy_version: 'v1.0.0',
    dataset_name: 'golden_origination',
    num_cases: 100,
  })
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [pollId, setPollId] = useState(null)

  async function run() {
    setRunning(true)
    setResult(null)
    setError(null)
    try {
      const sim = await createSimulation(form)
      const id = sim.simulation_id
      setPollId(id)

      // Poll until complete (max 60s)
      let attempts = 0
      const check = async () => {
        const data = await getSimulation(id)
        if (data.status === 'COMPLETED') {
          setResult(data)
          setRunning(false)
        } else if (data.status === 'FAILED') {
          setError(`Simulation failed: ${data.error || 'unknown'}`)
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

  const metrics = result?.metrics ?? {}

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Simulation Runner</h1>
      <p className="text-gray-500 text-sm mb-6">Run strategy versions against golden datasets to measure impact before deployment.</p>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Config form */}
        <div className="bg-white rounded-xl border p-5 lg:col-span-1">
          <h2 className="font-semibold mb-4">Configuration</h2>
          <div className="space-y-3">
            <label className="block text-sm">
              <span className="text-gray-700 font-medium">Workflow</span>
              <select value={form.workflow_type}
                onChange={e => setForm(f => ({...f, workflow_type: e.target.value}))}
                className="mt-1 block w-full border rounded px-2 py-1.5 text-sm">
                {WORKFLOWS.map(w => <option key={w}>{w}</option>)}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-gray-700 font-medium">Strategy Version</span>
              <input value={form.strategy_version}
                onChange={e => setForm(f => ({...f, strategy_version: e.target.value}))}
                className="mt-1 block w-full border rounded px-2 py-1.5 text-sm" />
            </label>
            <label className="block text-sm">
              <span className="text-gray-700 font-medium">Dataset</span>
              <input value={form.dataset_name}
                onChange={e => setForm(f => ({...f, dataset_name: e.target.value}))}
                className="mt-1 block w-full border rounded px-2 py-1.5 text-sm" />
            </label>
            <label className="block text-sm">
              <span className="text-gray-700 font-medium">Cases</span>
              <input type="number" value={form.num_cases}
                onChange={e => setForm(f => ({...f, num_cases: parseInt(e.target.value)}))}
                className="mt-1 block w-full border rounded px-2 py-1.5 text-sm" />
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
                <MetricCard title="Total Cases"    value={result.total_cases}   color="gray" />
                <MetricCard title="Approval Rate"  value={metrics.approval_rate != null ? `${(metrics.approval_rate * 100).toFixed(1)}%` : '—'} color="green" />
                <MetricCard title="Avg Confidence" value={metrics.avg_confidence != null ? `${(metrics.avg_confidence * 100).toFixed(0)}%` : '—'} color="blue" />
                <MetricCard title="Errors"         value={result.error_count ?? 0} color={result.error_count > 0 ? 'red' : 'gray'} />
              </div>
              <div className="bg-white rounded-xl border p-5">
                <h3 className="font-semibold mb-2">Recommendation Breakdown</h3>
                <div className="flex gap-6 text-sm">
                  {Object.entries(metrics.by_recommendation ?? {}).map(([rec, cnt]) => (
                    <div key={rec} className="text-center">
                      <p className="text-2xl font-bold">{cnt}</p>
                      <p className="text-xs text-gray-500">{rec}</p>
                    </div>
                  ))}
                </div>
              </div>
              {result.report_url && (
                <a href={`/api/v1/simulations/${result.simulation_id}/report`} target="_blank" rel="noreferrer"
                  className="mt-3 block text-center text-brand-500 hover:text-brand-700 text-sm font-medium">
                  View Full Report →
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
