import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listStrategies, getStrategyRules, updateRules } from '../api/client'

const RULE_FILES = ['credit_rules', 'fraud_rules', 'policy_rules', 'synthesis_weights']

function JsonEditor({ value, onChange }) {
  const [text, setText] = useState(JSON.stringify(value, null, 2))
  const [parseError, setParseError] = useState(null)

  useEffect(() => { setText(JSON.stringify(value, null, 2)) }, [value])

  function handle(v) {
    setText(v)
    try {
      onChange(JSON.parse(v))
      setParseError(null)
    } catch {
      setParseError('Invalid JSON')
    }
  }

  return (
    <div className="relative">
      <textarea
        value={text}
        onChange={e => handle(e.target.value)}
        rows={20}
        className={`w-full font-mono text-xs border rounded p-3 focus:outline-none focus:ring-2 ${parseError ? 'border-red-400 focus:ring-red-200' : 'focus:ring-blue-200'}`}
        spellCheck={false}
      />
      {parseError && <p className="text-red-600 text-xs mt-1">{parseError}</p>}
    </div>
  )
}

export default function RuleEditor() {
  const navigate = useNavigate()
  const [strategies, setStrategies]   = useState([])
  const [version, setVersion]         = useState('')
  const [ruleFile, setRuleFile]       = useState('credit_rules')
  const [rules, setRules]             = useState(null)
  const [edited, setEdited]           = useState(null)
  const [loading, setLoading]         = useState(false)
  const [saving, setSaving]           = useState(false)
  const [saved, setSaved]             = useState(false)
  const [error, setError]             = useState(null)

  useEffect(() => {
    listStrategies()
      .then(strats => {
        setStrategies(strats)
        const champion = strats.find(s => s.status === 'champion')
        setVersion(champion?.version ?? strats[0]?.version ?? '')
      })
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (!version) return
    setLoading(true)
    setRules(null)
    setEdited(null)
    setSaved(false)
    getStrategyRules(version)
      .then(data => {
        setRules(data)
        setEdited(data[ruleFile])
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [version])

  useEffect(() => {
    if (rules) setEdited(rules[ruleFile])
  }, [ruleFile])

  async function save() {
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      await updateRules(version, { rule_file: ruleFile, content: edited })
      setSaved(true)
      setRules(r => ({ ...r, [ruleFile]: edited }))
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const isDirty = JSON.stringify(rules?.[ruleFile]) !== JSON.stringify(edited)

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Rule Editor</h1>
          <p className="text-gray-500 text-sm">Edit strategy rules and thresholds in-browser</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => navigate('/rules/preview')}
            className="border border-gray-300 text-gray-700 text-sm px-3 py-2 rounded-lg font-medium hover:bg-gray-50">
            Preview Impact
          </button>
          <button onClick={() => navigate('/rules/deploy')}
            className="border border-gray-300 text-gray-700 text-sm px-3 py-2 rounded-lg font-medium hover:bg-gray-50">
            Deploy…
          </button>
        </div>
      </div>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}
      {saved  && <div className="bg-green-50 text-green-700 px-4 py-2 rounded mb-4 text-sm">Saved successfully.</div>}

      {/* Toolbar */}
      <div className="flex gap-3 mb-4">
        <select value={version} onChange={e => setVersion(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm font-mono">
          {strategies.map(s => <option key={s.version}>{s.version}</option>)}
        </select>
        <div className="flex rounded border overflow-hidden">
          {RULE_FILES.map(f => (
            <button key={f} onClick={() => setRuleFile(f)}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${ruleFile === f ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-100'}`}>
              {f.replace('_', ' ')}
            </button>
          ))}
        </div>
        <button onClick={save} disabled={!isDirty || saving}
          className="ml-auto bg-brand-500 hover:bg-brand-700 disabled:opacity-40 text-white text-sm px-4 py-1.5 rounded-lg font-medium">
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>

      {loading && <div className="animate-pulse bg-gray-100 rounded h-80" />}
      {!loading && edited !== undefined && edited !== null && (
        <div className="bg-white rounded-xl border p-4">
          {isDirty && (
            <div className="text-xs text-yellow-600 bg-yellow-50 border border-yellow-200 rounded px-3 py-1.5 mb-3">
              Unsaved changes. Save before deploying.
            </div>
          )}
          <JsonEditor value={edited} onChange={setEdited} />
        </div>
      )}
    </div>
  )
}
