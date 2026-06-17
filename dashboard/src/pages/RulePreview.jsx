import React, { useState } from 'react'
import MetricCard from '../components/MetricCard'
import { createSimulation, getSimulation, listStrategies } from '../api/client'

const REC_COLOR = {
  APPROVE: 'text-green-700',
  DECLINE: 'text-red-700',
  MANUAL_REVIEW: 'text-yellow-700',
}

export default function RulePreview() {
  const [version, setVersion]         = useState('v1.0.0')
  const [comparing, setComparing]     = useState('v1.0.0')
  const [strategy, setStrategy]       = useState([])
  const [results, setResults]         = useState(null)
  const [running, setRunning]         = useState(false)
  const [error, setError]             = useState(null)

  async function runPreview() {
    setRunning(true)
    setResults(null)
    setError(null)
    try {
      // Run both versions in parallel
      const [simA, simB] = await Promise.all([
        createSimulation({ workflow_type: 'ORIGINATION', strategy_version: version,   dataset_name: 'golden_origination', num_cases: 50 }),
        createSimulation({ workflow_type: 'ORIGINATION', strategy_version: comparing, dataset_name: 'golden_origination', num_cases: 50 }),
      ])

      const poll = async (id) => {
        let attempts = 0
        while (attempts < 30) {
          const data = await getSimulation(id)
          if (data.status === 'COMPLETED' || data.status === 'FAILED') return data
          await new Promise(r => setTimeout(r, 2000))
          attempts++
        }
        return { status: 'FAILED', error: 'Timeout' }
      }

      const [resA, resB] = await Promise.all([poll(simA.simulation_id), poll(simB.simulation_id)])
      setResults({ current: { version, ...resA }, compare: { version: comparing, ...resB } })
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Rule Preview</h1>
      <p className="text-gray-500 text-sm mb-6">Compare two strategy versions on the same golden dataset before deploying.</p>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      <div className="bg-white rounded-xl border p-5 mb-6">
        <div className="flex gap-4 items-end">
          <label className="flex-1">
            <span className="text-sm font-medium text-gray-700">Current (edited)</span>
            <input value={version} onChange={e => setVersion(e.target.value)}
              className="mt-1 block w-full border rounded px-2 py-1.5 text-sm font-mono" />
          </label>
          <span className="text-gray-400 pb-2">vs.</span>
          <label className="flex-1">
            <span className="text-sm font-medium text-gray-700">Baseline</span>
            <input value={comparing} onChange={e => setComparing(e.target.value)}
              className="mt-1 block w-full border rounded px-2 py-1.5 text-sm font-mono" />
          </label>
          <button onClick={runPreview} disabled={running}
            className="bg-brand-500 hover:bg-brand-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg font-medium whitespace-nowrap">
            {running ? 'Running…' : 'Run Preview'}
          </button>
        </div>
      </div>

      {running && (
        <div className="text-center py-12 text-blue-600">
          <div className="animate-spin w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full mx-auto mb-3" />
          Running simulations…
        </div>
      )}

      {results && (
        <div className="grid grid-cols-2 gap-6">
          {[results.current, results.compare].map(r => (
            <div key={r.version} className="bg-white rounded-xl border p-5">
              <div className="font-semibold font-mono mb-4">{r.version}</div>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard title="Approval Rate" value={r.metrics?.approval_rate != null ? `${(r.metrics.approval_rate * 100).toFixed(1)}%` : '—'} color="green" />
                <MetricCard title="Avg Confidence" value={r.metrics?.avg_confidence != null ? `${(r.metrics.avg_confidence * 100).toFixed(0)}%` : '—'} color="blue" />
              </div>
              {r.metrics?.by_recommendation && (
                <div className="mt-4">
                  {Object.entries(r.metrics.by_recommendation).map(([rec, n]) => (
                    <div key={rec} className="flex justify-between text-sm py-1 border-b last:border-0">
                      <span className={`font-medium ${REC_COLOR[rec] ?? ''}`}>{rec}</span>
                      <span>{n}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
