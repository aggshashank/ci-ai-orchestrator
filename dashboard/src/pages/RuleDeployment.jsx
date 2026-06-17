import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listStrategies, deployStrategy, activateStrategy } from '../api/client'

export default function RuleDeployment() {
  const navigate = useNavigate()
  const [strategies, setStrategies] = useState([])
  const [form, setForm] = useState({
    source_version: 'v1.0.0',
    new_version: '',
    changelog: [''],
  })
  const [deploying, setDeploying] = useState(false)
  const [deployed, setDeployed]   = useState(null)
  const [activating, setActiv]    = useState(false)
  const [error, setError]         = useState(null)

  useEffect(() => {
    listStrategies()
      .then(s => {
        setStrategies(s)
        const champion = s.find(x => x.status === 'champion')
        if (champion) setForm(f => ({ ...f, source_version: champion.version }))
      })
      .catch(e => setError(e.message))
  }, [])

  function addChangelog() {
    setForm(f => ({ ...f, changelog: [...f.changelog, ''] }))
  }
  function setChangelogItem(i, v) {
    setForm(f => {
      const cl = [...f.changelog]
      cl[i] = v
      return { ...f, changelog: cl }
    })
  }
  function removeChangelogItem(i) {
    setForm(f => ({ ...f, changelog: f.changelog.filter((_, idx) => idx !== i) }))
  }

  async function deploy() {
    setDeploying(true)
    setError(null)
    try {
      const body = {
        source_version: form.source_version,
        new_version:    form.new_version,
        changelog:      form.changelog.filter(c => c.trim()),
      }
      const res = await deployStrategy(body)
      setDeployed(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setDeploying(false)
    }
  }

  async function activate(version) {
    setActiv(true)
    try {
      await activateStrategy(version)
      navigate('/strategy')
    } catch (e) {
      setError(e.message)
      setActiv(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Deploy Strategy</h1>
      <p className="text-gray-500 text-sm mb-6">Create a new versioned strategy and optionally activate it as champion.</p>

      {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded mb-4 text-sm">{error}</div>}

      {!deployed ? (
        <div className="max-w-lg">
          <div className="bg-white rounded-xl border p-5 space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Source Version</label>
              <select value={form.source_version}
                onChange={e => setForm(f => ({...f, source_version: e.target.value}))}
                className="mt-1 block w-full border rounded px-2 py-1.5 text-sm">
                {strategies.map(s => <option key={s.version}>{s.version}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">New Version</label>
              <input value={form.new_version}
                onChange={e => setForm(f => ({...f, new_version: e.target.value}))}
                placeholder="e.g. v1.2.0"
                className="mt-1 block w-full border rounded px-2 py-1.5 text-sm font-mono" />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Changelog</label>
              <div className="mt-1 space-y-2">
                {form.changelog.map((c, i) => (
                  <div key={i} className="flex gap-2">
                    <input value={c} onChange={e => setChangelogItem(i, e.target.value)}
                      placeholder={`Change ${i + 1}`}
                      className="flex-1 border rounded px-2 py-1.5 text-sm" />
                    <button onClick={() => removeChangelogItem(i)} className="text-gray-400 hover:text-red-600 px-2">✕</button>
                  </div>
                ))}
                <button onClick={addChangelog} className="text-sm text-brand-500 hover:text-brand-700">+ Add entry</button>
              </div>
            </div>
            <div className="pt-2">
              <div className="bg-yellow-50 border border-yellow-200 rounded p-3 text-xs text-yellow-800 mb-3">
                This will copy rules from <strong>{form.source_version}</strong> → <strong>{form.new_version || 'new version'}</strong>.
                Any unsaved edits in the Rule Editor will NOT be included — save first.
              </div>
              <button onClick={deploy} disabled={deploying || !form.new_version}
                className="w-full bg-brand-500 hover:bg-brand-700 disabled:opacity-50 text-white text-sm py-2 rounded-lg font-medium">
                {deploying ? 'Deploying…' : 'Create Strategy Version'}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="max-w-lg">
          <div className="bg-green-50 border border-green-200 rounded-xl p-5">
            <p className="text-green-700 font-semibold mb-1">Strategy {deployed.new_version} created.</p>
            <p className="text-green-600 text-sm mb-4">{deployed.message}</p>
            <div className="flex gap-3">
              <button onClick={() => activate(deployed.new_version)} disabled={activating}
                className="flex-1 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm py-2 rounded-lg font-medium">
                {activating ? 'Activating…' : 'Activate as Champion'}
              </button>
              <button onClick={() => navigate('/strategy')}
                className="flex-1 border border-green-600 text-green-700 text-sm py-2 rounded-lg font-medium hover:bg-green-100">
                Go to Strategy Dashboard
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
