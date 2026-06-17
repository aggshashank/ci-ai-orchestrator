import React from 'react'

const AGENTS = [
  { key: 'credit_agent',         label: 'Credit Agent',        color: 'bg-blue-500' },
  { key: 'fraud_agent',          label: 'Fraud Agent',         color: 'bg-purple-500' },
  { key: 'policy_rag_agent',     label: 'Policy RAG',          color: 'bg-indigo-500' },
  { key: 'risk_decision',        label: 'Risk Decision',       color: 'bg-orange-500' },
  { key: 'explainability_agent', label: 'Explainability',      color: 'bg-teal-500' },
]

export default function DecisionTimeline({ audit }) {
  if (!audit) return null

  return (
    <div className="mt-4">
      <h4 className="text-xs font-bold uppercase text-gray-500 mb-3">Agent Execution Timeline</h4>
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-gray-200" />

        {AGENTS.map(({ key, label, color }, idx) => {
          const hasData = key === 'credit_agent'   ? !!audit.credit_result
                        : key === 'fraud_agent'    ? !!audit.fraud_result
                        : key === 'policy_rag_agent' ? !!audit.policy_context
                        : key === 'risk_decision'  ? !!audit.risk_decision
                        : !!audit.explanation

          return (
            <div key={key} className="flex items-start gap-4 mb-4 relative">
              <div className={`w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center z-10 text-white text-xs font-bold ${hasData ? color : 'bg-gray-300'}`}>
                {idx + 1}
              </div>
              <div className="flex-1">
                <p className={`text-sm font-medium ${hasData ? 'text-gray-900' : 'text-gray-400'}`}>{label}</p>
                <p className="text-xs text-gray-500">{hasData ? 'Completed' : 'Not run'}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
