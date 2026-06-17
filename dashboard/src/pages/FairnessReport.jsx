import React, { useState, useEffect } from 'react'
import MetricCard from '../components/MetricCard'
import { getFairnessLatest, runFairness } from '../api/client'

function ViolationRow({ seg }) {
  return (
    <tr className={seg.violation ? 'bg-red-50' : 'bg-green-50'}>
      <td className="px-3 py-2 text-xs font-mono">{seg.segment_name}</td>
      <td className="px-3 py-2 text-xs">{seg.segment_value}</td>
      <td className="px-3 py-2 text-xs text-center">{seg.total_decisions}</td>
      <td className="px-3 py-2 text-xs text-center">{(seg.approval_rate * 100).toFixed(1)}%</td>
      <td className="px-3 py-2 text-xs text-center">{(seg.ratio_to_best * 100).toFixed(1)}%</td>
      <td className="px-3 py-2 text-xs text-center">
        {seg.violation
          ? <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs font-bold">VIOLATION</span>
          : <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs font-bold">PASS</span>
        }
      </td>
    </tr>
  )
}

export default function FairnessReport() {
  const [report, setReport]     = useState(null)
  const [loading, setLoading]   = useState(true)
  const [running, setRunning]   = useState(false)
  const [error, setError]       = useState(null)
  const [days, setDays]         = useState(30)

  const load = () => {
    setLoading(true)
    getFairnessLatest()
      .then(setReport)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function trigger() {
    setRunning(true)
    try {
      const r = await runFairness(days)
      setReport(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  const segments   = report?.segments ?? []
  const violations = segments.filter(s => s.violation)

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Fairness Report</h1>
          <p className="text-gray-500 text-sm">4/5ths rule (disparate impact) analysis by segment</p>
        </div>
        <div className="flex gap-2 items-center">
          <select value={days} onChange={e => setDays(Number(e.target.value))}
            className="border rounded px-2 py-1.5 text-sm">
            {[7, 14, 30, 60, 90].map(d => <option key={d} value={d}>{d}d</option>)}
          </select>
          <button onClick={trigger} disabled={running}
            className="bg-brand-500 hover:bg-brand-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg font-medium">
            {running ? 'Running…' : 'Run Analysis'}
          </button>
        </div>
      </div>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Total Decisions"    value={report?.total_decisions ?? '—'} color="gray"   loading={loading} />
        <MetricCard title="Overall Approval"   value={report?.overall_approval_rate != null ? `${(report.overall_approval_rate * 100).toFixed(1)}%` : '—'} color="green" loading={loading} />
        <MetricCard title="Violations"         value={report?.violations_count ?? violations.length} color={violations.length > 0 ? 'red' : 'green'} loading={loading} />
        <MetricCard title="Analysis Period"    value={report ? `${report.period_days}d` : '—'} color="blue" loading={loading} />
      </div>

      {violations.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4">
          <p className="text-red-700 font-semibold text-sm">
            ⚠️ {violations.length} disparate impact violation{violations.length > 1 ? 's' : ''} detected.
            Segments with approval rate below 80% of the best-performing group.
          </p>
        </div>
      )}

      {report && (
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold mb-3">Segment Analysis</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[640px]">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b">
                  <th className="px-3 pb-2">Segment</th>
                  <th className="px-3 pb-2">Value</th>
                  <th className="px-3 pb-2 text-center">Decisions</th>
                  <th className="px-3 pb-2 text-center">Approval Rate</th>
                  <th className="px-3 pb-2 text-center">Ratio to Best</th>
                  <th className="px-3 pb-2 text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {segments.map((seg, i) => <ViolationRow key={i} seg={seg} />)}
              </tbody>
            </table>
          </div>
          {report.report_date && (
            <p className="text-xs text-gray-400 mt-3">
              Report generated: {new Date(report.report_date).toLocaleString()}
            </p>
          )}
        </div>
      )}

      {!loading && !report && (
        <div className="bg-white rounded-xl border p-8 text-center text-gray-400">
          <p className="text-4xl mb-3">⚖️</p>
          <p>No fairness report found. Click "Run Analysis" to generate one.</p>
        </div>
      )}
    </div>
  )
}
