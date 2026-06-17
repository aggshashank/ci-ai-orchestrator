const BASE = '/api/v1'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json()
}

// Strategies
export const listStrategies   = ()          => request('/strategies').then(r => r.versions ?? r)
export const getStrategy      = (v)         => request(`/strategies/${v}`)
export const getStrategyDiff  = (from, to)  => request(`/strategies/diff?from=${from}&to=${to}`)
export const getStrategyRules = (v)         => request(`/strategies/${v}/rules`)
export const updateRules      = (v, body)   => request(`/strategies/${v}/rules`, { method: 'PUT', body })
export const deployStrategy   = (body)      => request('/strategies/deploy', { method: 'POST', body })
export const activateStrategy = (v)         => request(`/strategies/${v}/activate`, { method: 'PUT' })

// Simulations
export const createSimulation = (body)      => request('/simulations', { method: 'POST', body })
export const getSimulation    = (id)        => request(`/simulations/${id}`)
export const getSimReport     = (id)        => fetch(`${BASE}/simulations/${id}/report`).then(r => r.text())

// Experiments
export const getExperiment    = ()          => request('/experiments')

// Decisions / audit
export const getReviewQueue   = ()          => request('/review-queue')
export const getAudit         = (corrId)    => request(`/audit/${corrId}`)
export const submitReview     = (corrId, b) => request(`/review/${corrId}/decision`, { method: 'POST', body: b })

// Customer
export const getCustomer      = (id, refresh = false) => request(`/customers/${id}/profile${refresh ? '?refresh=true' : ''}`)

// Fairness
export const getFairnessLatest = ()         => request('/governance/fairness/latest')
export const runFairness       = (days)     => request('/governance/fairness/run', { method: 'POST', body: { period_days: days } })
export const getFairnessReport = ()         => fetch(`${BASE}/governance/fairness/latest/report`).then(r => r.text())

// Drift / retrain
export const getDrift          = (days)     => request(`/governance/drift?window_days=${days}`)
export const triggerRetrain    = (days, dry)=> request(`/governance/retrain?window_days=${days}&dry_run=${dry}`, { method: 'POST' })

// Analytics
export const getAnalyticsTrends   = (days) => request(`/analytics/trends?days=${days}`)
export const getAnalyticsSegments = (days) => request(`/analytics/segments?days=${days}`)
export const getStrategyPerf      = (days) => request(`/analytics/strategy-performance?days=${days}`)
export const getRevenueImpact     = (from, to) => request(`/analytics/revenue-impact?from=${from}&to=${to}`)
