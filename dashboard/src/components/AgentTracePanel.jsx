import React, { useState } from 'react'

const RISK_COLOR = {
  HIGH:   'text-red-600 bg-red-50',
  MEDIUM: 'text-yellow-600 bg-yellow-50',
  LOW:    'text-green-600 bg-green-50',
}
const REC_COLOR = {
  APPROVE:       'text-green-700 bg-green-100',
  DECLINE:       'text-red-700 bg-red-100',
  MANUAL_REVIEW: 'text-yellow-700 bg-yellow-100',
}

function Section({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border rounded-lg mb-2">
      <button className="w-full flex justify-between items-center px-4 py-2.5 text-sm font-medium text-left"
        onClick={() => setOpen(o => !o)}>
        {title} <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="px-4 pb-3 text-sm">{children}</div>}
    </div>
  )
}

export default function AgentTracePanel({ audit }) {
  if (!audit) return null
  const { credit_result, fraud_result, policy_context, risk_decision, explanation } = audit

  return (
    <div className="mt-4 space-y-1">
      <Section title="Credit Agent" defaultOpen>
        <div className="flex gap-2 items-center mb-1">
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${RISK_COLOR[credit_result?.riskLevel] ?? ''}`}>
            {credit_result?.riskLevel}
          </span>
          <span className="text-gray-600">Score: {(credit_result?.score * 100)?.toFixed(0)}%</span>
        </div>
        <p className="text-gray-700">{credit_result?.reason}</p>
      </Section>

      <Section title="Fraud Agent">
        <div className="flex gap-2 items-center mb-1">
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${RISK_COLOR[fraud_result?.fraudRisk] ?? ''}`}>
            {fraud_result?.fraudRisk}
          </span>
        </div>
        <p className="text-gray-700">{fraud_result?.reason}</p>
        {fraud_result?.indicators?.length > 0 && (
          <p className="text-xs text-gray-500 mt-1">Indicators: {fraud_result.indicators.join(', ')}</p>
        )}
      </Section>

      <Section title="Policy RAG Agent">
        <p className="text-gray-700">{policy_context?.action}</p>
        {policy_context?.rules?.map((r, i) => <p key={i} className="text-xs text-gray-500">• {r}</p>)}
      </Section>

      <Section title="Risk Decision" defaultOpen>
        <div className="flex gap-2 items-center mb-1">
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${REC_COLOR[risk_decision?.recommendation] ?? ''}`}>
            {risk_decision?.recommendation}
          </span>
          <span className="text-gray-500 text-xs">Confidence: {(risk_decision?.confidence * 100)?.toFixed(0)}%</span>
        </div>
        {risk_decision?.reasons?.map((r, i) => <p key={i} className="text-xs text-gray-600">• {r}</p>)}
      </Section>

      <Section title="Explainability">
        <p className="text-gray-700 mb-1">{explanation?.plain_language_summary}</p>
        {explanation?.adverse_action_codes?.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {explanation.adverse_action_codes.map(c => (
              <span key={c.code} className="bg-red-50 text-red-700 text-xs px-2 py-0.5 rounded border border-red-200">
                {c.code} — {c.description}
              </span>
            ))}
          </div>
        )}
      </Section>
    </div>
  )
}
