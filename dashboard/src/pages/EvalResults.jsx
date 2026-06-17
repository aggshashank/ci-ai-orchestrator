import React, { useState } from 'react'
import MetricCard from '../components/MetricCard'
import { createSimulation, getSimulation } from '../api/client'

const EVAL_SUITES = [
  { id: 'origination',   label: 'Origination',    dataset: 'golden_origination'   },
  { id: 'delinquency',   label: 'Delinquency',    dataset: 'golden_delinquency'   },
  { id: 'limit_review',  label: 'Limit Review',   dataset: 'golden_limit_review'  },
  { id: 'cross_sell',    label: 'Cross-Sell',     dataset: 'golden_cross_sell'    },
]

function StatusBadge({ status }) {
  const map = {
    PENDING:   'bg-gray-100 text-gray-600',
    RUNNING:   'bg-blue-100 text-blue-600',
    COMPLETED: 'bg-green-100 text-green-600',
    FAILED:    'bg-red-100 text-red-600',
  }
  return <span className={`text-xs px-2 py-0.5 rounded font-medium ${map[status] ?? map.PENDING}`}>{status}</span>
}

export default function EvalResults() {
  const [version, setVersion]   = useState('v1.0.0')
  const [results, setResults]   = useState({})
  const [running, setRunning]   = useState(false)
  const [error, setError]       = useState(null)

  async function runAllEvals() {
    setRunning(true)
    setError(null)
    const initial = {}
    EVAL_SUITES.forEach(s => { initial[s.id] = { status: 'RUNNING' } })
    setResults(initial)

    try {
      await Promise.all(EVAL_SUITES.map(async suite => {
        try {
          const sim = await createSimulation({
            workflow_type:    suite.id.toUpperCase().replace('_', '_'),
            strategy_version: version,
            dataset_name:     suite.dataset,
            num_cases:        50,
          })
          let attempts = 0
          const poll = async () => {
            const data = await getSimulation(sim.simulation_id)
            if (data.status === 'COMPLETED' || data.status === 'FAILED' || ++attempts > 30) {
              setResults(r => ({ ...r, [suite.id]: data }))
            } else {
              setTimeout(poll, 2000)
            }
          }
          await poll()
        } catch (e) {
          setResults(r => ({ ...r, [suite.id]: { status: 'FAILED', error: e.message } }))
        }
      }))
    } finally {
      setRunning(false)
    }
  }

  const completed = Object.values(results).filter(r => r.status === 'COMPLETED')
  const avgApproval = completed.length
    ? (completed.reduce((s, r) => s + (r.metrics?.approval_rate ?? 0), 0) / completed.length * 100).toFixed(1)
    : null

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Eval Results</h1>
          <p className="text-gray-500 text-sm">Run all golden-dataset suites against a strategy version</p>
        </div>
        <div className="flex gap-2 items-center">
          <input value={version} onChange={e => setVersion(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm font-mono w-28" placeholder="v1.0.0" />
          <button onClick={runAllEvals} disabled={running}
            className="bg-brand-500 hover:bg-brand-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg font-medium">
            {running ? 'Running…' : 'Run All Evals'}
          </button>
        </div>
      </div>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Suites"         value={EVAL_SUITES.length}             color="gray" />
        <MetricCard title="Completed"      value={completed.length}               color="green" />
        <MetricCard title="Failed"         value={Object.values(results).filter(r => r.status === 'FAILED').length} color="red" />
        <MetricCard title="Avg Approval"   value={avgApproval ? `${avgApproval}%` : '—'} color="blue" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {EVAL_SUITES.map(suite => {
          const r = results[suite.id]
          return (
            <div key={suite.id} className="bg-white rounded-xl border p-5">
              <div className="flex justify-between items-start mb-3">
                <h2 className="font-semibold">{suite.label}</h2>
                {r && <StatusBadge status={r.status} />}
              </div>
              {!r && <p className="text-gray-400 text-sm">Not run yet</p>}
              {r?.status === 'RUNNING' && (
                <div className="flex items-center gap-2 text-blue-600 text-sm">
                  <div className="animate-spin w-4 h-4 border-2 border-blue-300 border-t-blue-600 rounded-full" />
                  Running…
                </div>
              )}
              {r?.status === 'COMPLETED' && (
                <div className="grid grid-cols-3 gap-3 mt-2">
                  <div className="text-center">
                    <p className="text-xl font-bold text-green-600">{r.total_cases}</p>
                    <p className="text-xs text-gray-500">Cases</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xl font-bold text-blue-600">{(r.metrics?.approval_rate * 100)?.toFixed(1)}%</p>
                    <p className="text-xs text-gray-500">Approval</p>
                  </div>
                  <div className="text-center">
                    <p className={`text-xl font-bold ${r.error_count > 0 ? 'text-red-600' : 'text-gray-700'}`}>{r.error_count ?? 0}</p>
                    <p className="text-xs text-gray-500">Errors</p>
                  </div>
                </div>
              )}
              {r?.status === 'FAILED' && (
                <p className="text-red-600 text-sm">{r.error ?? 'Unknown error'}</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
