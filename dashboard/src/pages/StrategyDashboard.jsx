import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import MetricCard from '../components/MetricCard'
import StrategyDiff from '../components/StrategyDiff'
import { listStrategies, getStrategyDiff, getExperiment } from '../api/client'

function Badge({ status }) {
  const map = {
    champion: 'bg-green-100 text-green-700',
    challenger: 'bg-blue-100 text-blue-700',
    archived: 'bg-gray-100 text-gray-500',
  }
  return <span className={`text-xs px-2 py-0.5 rounded font-medium ${map[status] ?? map.archived}`}>{status}</span>
}

export default function StrategyDashboard() {
  const navigate = useNavigate()
  const [strategies, setStrategies]   = useState([])
  const [experiment, setExperiment]   = useState(null)
  const [diff, setDiff]               = useState(null)
  const [compareFrom, setCompareFrom] = useState('')
  const [compareTo, setCompareTo]     = useState('')
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)

  useEffect(() => {
    Promise.all([listStrategies(), getExperiment()])
      .then(([strats, exp]) => {
        setStrategies(Array.isArray(strats) ? strats : [])
        setExperiment(exp)
        const versions = (Array.isArray(strats) ? strats : []).map(s => s.version)
        if (versions.length >= 2) {
          setCompareFrom(versions[versions.length - 2])
          setCompareTo(versions[versions.length - 1])
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleCompare() {
    if (!compareFrom || !compareTo) return
    try {
      const d = await getStrategyDiff(compareFrom, compareTo)
      setDiff(d)
    } catch (e) {
      setError(e.message)
    }
  }

  const champion   = strategies.find(s => s.is_active === true)
  const challenger = experiment?.experiment_enabled ? strategies.find(s => s.version === experiment.challenger_strategy) : null

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Strategy Dashboard</h1>
          <p className="text-gray-500 text-sm">Manage champion/challenger decisioning strategies</p>
        </div>
        <button onClick={() => navigate('/rules')}
          className="bg-brand-500 hover:bg-brand-700 text-white text-sm px-4 py-2 rounded-lg font-medium">
          Edit Rules
        </button>
      </div>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Champion Version" value={champion?.version ?? '—'} color="green" loading={loading} />
        <MetricCard title="Challenger Version" value={challenger?.version ?? 'None'} color="blue" loading={loading} />
        <MetricCard title="Experiment Traffic" value={experiment ? `${experiment.challenger_percentage ?? 0}%` : '—'} sub="to challenger" color="yellow" loading={loading} />
        <MetricCard title="Total Strategies" value={strategies.length} color="gray" loading={loading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Strategy list */}
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold mb-3">Registered Versions</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="pb-2">Version</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Registered</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map(s => (
                <tr key={s.version} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="py-2.5 font-mono text-xs">{s.version}</td>
                  <td className="py-2.5"><Badge status={s.is_active ? 'champion' : 'archived'} /></td>
                  <td className="py-2.5 text-gray-500 text-xs">{s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
              {!loading && strategies.length === 0 && (
                <tr><td colSpan={3} className="py-4 text-center text-gray-400 text-sm">No strategies registered</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Diff viewer */}
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold mb-3">Version Diff</h2>
          <div className="flex gap-2 mb-4">
            <select value={compareFrom} onChange={e => setCompareFrom(e.target.value)}
              className="border rounded px-2 py-1.5 text-sm flex-1">
              {strategies.map(s => <option key={s.version}>{s.version}</option>)}
            </select>
            <span className="self-center text-gray-400">→</span>
            <select value={compareTo} onChange={e => setCompareTo(e.target.value)}
              className="border rounded px-2 py-1.5 text-sm flex-1">
              {strategies.map(s => <option key={s.version}>{s.version}</option>)}
            </select>
            <button onClick={handleCompare}
              className="bg-gray-900 text-white text-sm px-3 py-1.5 rounded font-medium whitespace-nowrap">
              Compare
            </button>
          </div>
          <StrategyDiff diff={diff} />
        </div>
      </div>
    </div>
  )
}
