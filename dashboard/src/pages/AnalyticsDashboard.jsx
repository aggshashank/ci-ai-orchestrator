import React, { useState, useEffect } from 'react'
import MetricCard from '../components/MetricCard'
import { RecommendationBar, ApprovalRateLine } from '../components/RecommendationChart'
import { getAnalyticsTrends, getAnalyticsSegments, getStrategyPerf, getRevenueImpact } from '../api/client'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'

export default function AnalyticsDashboard() {
  const [days, setDays]         = useState(30)
  const [trends, setTrends]     = useState(null)
  const [segments, setSegments] = useState(null)
  const [perf, setPerf]         = useState(null)
  const [revenue, setRevenue]   = useState(null)
  const [revFrom, setRevFrom]   = useState('')
  const [revTo, setRevTo]       = useState('')
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      getAnalyticsTrends(days),
      getAnalyticsSegments(days),
      getStrategyPerf(90),
    ])
      .then(([t, s, p]) => {
        setTrends(t)
        setSegments(s)
        setPerf(p)
        const versions = (p.strategy_performance ?? []).map(x => x.strategy_version)
        if (versions.length >= 2) {
          setRevFrom(versions[versions.length - 2])
          setRevTo(versions[versions.length - 1])
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [days])

  async function calcRevenue() {
    if (!revFrom || !revTo) return
    try {
      const r = await getRevenueImpact(revFrom, revTo)
      setRevenue(r)
    } catch (e) {
      setError(e.message)
    }
  }

  const daily = trends?.daily_approval_rate ?? []
  const latestDay = daily[daily.length - 1]
  const stratPerf = perf?.strategy_performance ?? []

  // Channel data for bar chart
  const channelData = Object.entries(segments?.by_channel ?? {}).map(([ch, v]) => ({
    channel: ch, ...v,
  }))

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-gray-500 text-sm">Approval trends, segment breakdowns, strategy performance</p>
        </div>
        <div className="flex rounded border overflow-hidden">
          {[7, 14, 30, 60, 90].map(d => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${days === d ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      {/* Top metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Total Decisions"    value={latestDay?.total ?? '—'}    color="gray"   loading={loading} />
        <MetricCard title="Today Approval Rate" value={latestDay ? `${(latestDay.approval_rate * 100).toFixed(1)}%` : '—'} color="green" loading={loading} />
        <MetricCard title="Strategy Versions"  value={stratPerf.length}            color="blue"   loading={loading} />
        <MetricCard title="Rolling Default"    value={trends?.rolling_default_rate?.[trends.rolling_default_rate.length - 1]?.default_rate != null ? `${(trends.rolling_default_rate[trends.rolling_default_rate.length - 1].default_rate * 100).toFixed(2)}%` : '—'} color="yellow" loading={loading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Daily volume */}
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold mb-3">Daily Decision Volume</h2>
          {loading ? <div className="h-60 bg-gray-100 animate-pulse rounded" /> : <RecommendationBar data={daily} />}
        </div>

        {/* Approval rate trend */}
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold mb-3">Daily Approval Rate</h2>
          {loading ? <div className="h-52 bg-gray-100 animate-pulse rounded" /> : <ApprovalRateLine data={daily} />}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Channel breakdown */}
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold mb-3">Approval Rate by Channel</h2>
          {loading ? <div className="h-52 bg-gray-100 animate-pulse rounded" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={channelData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="channel" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={v => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 11 }} domain={[0, 1]} />
                <Tooltip formatter={v => `${(v * 100).toFixed(1)}%`} />
                <Bar dataKey="approval_rate" name="Approval Rate" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Strategy performance */}
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold mb-3">Strategy Performance (90d)</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b">
                  <th className="pb-2">Version</th>
                  <th className="pb-2 text-center">Total</th>
                  <th className="pb-2 text-center">Approval</th>
                  <th className="pb-2 text-center">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {stratPerf.map(s => (
                  <tr key={s.strategy_version} className="border-b last:border-0">
                    <td className="py-2 font-mono text-xs">{s.strategy_version}</td>
                    <td className="py-2 text-center">{s.total}</td>
                    <td className="py-2 text-center">{(s.approval_rate * 100).toFixed(1)}%</td>
                    <td className="py-2 text-center">{(s.avg_confidence * 100).toFixed(0)}%</td>
                  </tr>
                ))}
                {!loading && stratPerf.length === 0 && (
                  <tr><td colSpan={4} className="py-4 text-center text-gray-400 text-sm">No data</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Revenue impact */}
      <div className="bg-white rounded-xl border p-5">
        <h2 className="font-semibold mb-3">Revenue Impact Estimator</h2>
        <div className="flex gap-3 items-end mb-4">
          <label className="flex-1">
            <span className="text-xs text-gray-600">From version</span>
            <input value={revFrom} onChange={e => setRevFrom(e.target.value)}
              className="mt-1 block w-full border rounded px-2 py-1.5 text-sm font-mono" />
          </label>
          <span className="text-gray-400 pb-2">→</span>
          <label className="flex-1">
            <span className="text-xs text-gray-600">To version</span>
            <input value={revTo} onChange={e => setRevTo(e.target.value)}
              className="mt-1 block w-full border rounded px-2 py-1.5 text-sm font-mono" />
          </label>
          <button onClick={calcRevenue}
            className="bg-gray-900 text-white text-sm px-3 py-1.5 rounded font-medium whitespace-nowrap">
            Calculate
          </button>
        </div>
        {revenue && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard title="Approval Rate Delta" value={`${revenue.approval_rate_delta >= 0 ? '+' : ''}${(revenue.approval_rate_delta * 100).toFixed(2)} pp`} color={revenue.approval_rate_delta >= 0 ? 'green' : 'red'} />
            <MetricCard title="New Approvals" value={revenue.projected_new_approvals >= 0 ? `+${revenue.projected_new_approvals}` : revenue.projected_new_approvals} color={revenue.projected_new_approvals >= 0 ? 'green' : 'red'} />
            <MetricCard title="Revenue Impact" value={`$${revenue.estimated_revenue_impact.toLocaleString()}`} sub={`${revenue.projection_months}mo projection`} color={revenue.estimated_revenue_impact >= 0 ? 'green' : 'red'} />
            <MetricCard title="Avg CLV Used" value={`$${revenue.avg_clv_used.toLocaleString()}`} color="gray" />
          </div>
        )}
        {revenue && (
          <p className="text-xs text-gray-400 mt-3">{revenue.note}</p>
        )}
      </div>
    </div>
  )
}
