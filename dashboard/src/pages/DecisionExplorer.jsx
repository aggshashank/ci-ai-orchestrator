import React, { useState, useEffect } from 'react'
import AgentTracePanel from '../components/AgentTracePanel'
import DecisionTimeline from '../components/DecisionTimeline'
import { getAudit, getReviewQueue, submitReview } from '../api/client'

const REC_COLOR = {
  APPROVE: 'bg-green-100 text-green-700',
  DECLINE: 'bg-red-100 text-red-700',
  MANUAL_REVIEW: 'bg-yellow-100 text-yellow-700',
}

export default function DecisionExplorer() {
  const [corrId, setCorrId]           = useState('')
  const [audit, setAudit]             = useState(null)
  const [queue, setQueue]             = useState([])
  const [queueLoading, setQueueLoad]  = useState(true)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)
  const [reviewForm, setReviewForm]   = useState({ decision: 'APPROVE', reviewer: '', notes: '' })
  const [reviewSent, setReviewSent]   = useState(false)

  useEffect(() => {
    getReviewQueue()
      .then(setQueue)
      .catch(e => console.warn(e))
      .finally(() => setQueueLoad(false))
  }, [])

  async function lookup(id) {
    const q = id ?? corrId
    if (!q) return
    setLoading(true)
    setAudit(null)
    setError(null)
    setReviewSent(false)
    try {
      const data = await getAudit(q)
      setAudit(data)
      setCorrId(q)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function sendReview() {
    try {
      await submitReview(corrId, reviewForm)
      setReviewSent(true)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Decision Explorer</h1>
      <p className="text-gray-500 text-sm mb-6">Inspect full agent traces and submit underwriter decisions.</p>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Search + review queue */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border p-5">
            <h2 className="font-semibold mb-3">Lookup Decision</h2>
            <div className="flex gap-2">
              <input value={corrId} onChange={e => setCorrId(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && lookup()}
                placeholder="APP-xxxx-xxxx"
                className="flex-1 border rounded px-2 py-1.5 text-sm font-mono" />
              <button onClick={() => lookup()} disabled={loading}
                className="bg-gray-900 text-white text-sm px-3 py-1.5 rounded font-medium">
                {loading ? '…' : 'Load'}
              </button>
            </div>
          </div>

          <div className="bg-white rounded-xl border p-5">
            <h2 className="font-semibold mb-3">Review Queue</h2>
            {queueLoading && <p className="text-gray-400 text-sm">Loading…</p>}
            {!queueLoading && queue.length === 0 && <p className="text-gray-400 text-sm">Queue is empty</p>}
            <ul className="space-y-2">
              {queue.map(item => (
                <li key={item.correlation_id}>
                  <button onClick={() => lookup(item.correlation_id)}
                    className="w-full text-left px-3 py-2 rounded border hover:bg-gray-50 text-sm">
                    <p className="font-mono text-xs text-gray-600">{item.correlation_id}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{new Date(item.created_at).toLocaleString()}</p>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Audit trace */}
        <div className="lg:col-span-2">
          {audit ? (
            <div className="bg-white rounded-xl border p-5">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <p className="font-mono text-xs text-gray-500">{audit.correlation_id}</p>
                  <div className="flex gap-2 items-center mt-1">
                    <span className={`text-sm font-bold px-2 py-0.5 rounded ${REC_COLOR[audit.risk_decision?.recommendation] ?? ''}`}>
                      {audit.risk_decision?.recommendation}
                    </span>
                    <span className="text-xs text-gray-500">
                      {(audit.risk_decision?.confidence * 100)?.toFixed(0)}% confidence
                    </span>
                  </div>
                </div>
                <DecisionTimeline audit={audit} />
              </div>

              <AgentTracePanel audit={audit} />

              {/* Underwriter review form */}
              {audit.risk_decision?.recommendation === 'MANUAL_REVIEW' && !reviewSent && (
                <div className="mt-6 pt-4 border-t">
                  <h3 className="font-semibold text-sm mb-3">Submit Underwriter Decision</h3>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs text-gray-600">Decision</label>
                      <select value={reviewForm.decision}
                        onChange={e => setReviewForm(f => ({...f, decision: e.target.value}))}
                        className="mt-1 block w-full border rounded px-2 py-1.5 text-sm">
                        <option>APPROVE</option>
                        <option>DECLINE</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gray-600">Reviewer ID</label>
                      <input value={reviewForm.reviewer}
                        onChange={e => setReviewForm(f => ({...f, reviewer: e.target.value}))}
                        className="mt-1 block w-full border rounded px-2 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label className="text-xs text-gray-600">&nbsp;</label>
                      <button onClick={sendReview}
                        className="mt-1 w-full bg-green-600 hover:bg-green-700 text-white text-sm py-1.5 rounded font-medium">
                        Submit
                      </button>
                    </div>
                  </div>
                  <textarea value={reviewForm.notes}
                    onChange={e => setReviewForm(f => ({...f, notes: e.target.value}))}
                    placeholder="Notes (optional)"
                    rows={2}
                    className="mt-2 w-full border rounded px-2 py-1.5 text-sm" />
                </div>
              )}
              {reviewSent && (
                <div className="mt-4 bg-green-50 text-green-700 px-4 py-2 rounded text-sm font-medium">
                  Decision submitted successfully.
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-xl border p-8 text-center text-gray-400">
              <p className="text-4xl mb-3">🔍</p>
              <p>Enter a correlation ID or select from the review queue</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
