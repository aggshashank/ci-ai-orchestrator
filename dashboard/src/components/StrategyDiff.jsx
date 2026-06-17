import React from 'react'

function DiffRow({ key_, old_, new_ }) {
  const changed = JSON.stringify(old_) !== JSON.stringify(new_)
  return (
    <tr className={changed ? 'bg-yellow-50' : ''}>
      <td className="px-3 py-1.5 font-mono text-xs text-gray-600 border-b w-48">{key_}</td>
      <td className="px-3 py-1.5 font-mono text-xs border-b text-red-700 w-1/2">
        {old_ !== undefined ? JSON.stringify(old_, null, 2) : <span className="text-gray-400">—</span>}
      </td>
      <td className="px-3 py-1.5 font-mono text-xs border-b text-green-700 w-1/2">
        {new_ !== undefined ? JSON.stringify(new_, null, 2) : <span className="text-gray-400">—</span>}
      </td>
    </tr>
  )
}

export default function StrategyDiff({ diff }) {
  if (!diff) return <p className="text-gray-500 text-sm">Select two versions to compare.</p>

  const { from_version, to_version, changed_thresholds = [], changed_weights = [], added_rules = [], removed_rules = [] } = diff

  return (
    <div>
      <div className="flex gap-4 mb-4 text-sm">
        <span className="bg-red-100 text-red-700 px-3 py-1 rounded">{from_version}</span>
        <span className="text-gray-400">→</span>
        <span className="bg-green-100 text-green-700 px-3 py-1 rounded">{to_version}</span>
      </div>

      {changed_thresholds.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-bold uppercase text-gray-500 mb-1">Changed Thresholds</h4>
          <table className="w-full text-sm border rounded overflow-hidden">
            <thead className="bg-gray-100">
              <tr>
                <th className="text-left px-3 py-2 text-xs">Rule / Field</th>
                <th className="text-left px-3 py-2 text-xs text-red-600">Before</th>
                <th className="text-left px-3 py-2 text-xs text-green-600">After</th>
              </tr>
            </thead>
            <tbody>
              {changed_thresholds.map((c, i) => (
                <DiffRow key={i} key_={c.rule || c.field} old_={c.old_value} new_={c.new_value} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {changed_weights.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-bold uppercase text-gray-500 mb-1">Weight Changes</h4>
          <table className="w-full text-sm border rounded overflow-hidden">
            <thead className="bg-gray-100">
              <tr>
                <th className="text-left px-3 py-2 text-xs">Signal</th>
                <th className="text-left px-3 py-2 text-xs text-red-600">Before</th>
                <th className="text-left px-3 py-2 text-xs text-green-600">After</th>
              </tr>
            </thead>
            <tbody>
              {changed_weights.map((w, i) => (
                <DiffRow key={i} key_={w.signal} old_={w.old_weight} new_={w.new_weight} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {added_rules.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-bold uppercase text-gray-500 mb-1">Added Rules</h4>
          {added_rules.map((r, i) => (
            <div key={i} className="bg-green-50 border border-green-200 rounded px-3 py-1.5 text-xs font-mono mb-1">{r}</div>
          ))}
        </div>
      )}

      {removed_rules.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-bold uppercase text-gray-500 mb-1">Removed Rules</h4>
          {removed_rules.map((r, i) => (
            <div key={i} className="bg-red-50 border border-red-200 rounded px-3 py-1.5 text-xs font-mono mb-1 line-through">{r}</div>
          ))}
        </div>
      )}

      {changed_thresholds.length === 0 && changed_weights.length === 0 &&
       added_rules.length === 0 && removed_rules.length === 0 && (
        <p className="text-gray-500 text-sm">No differences found between these versions.</p>
      )}
    </div>
  )
}
