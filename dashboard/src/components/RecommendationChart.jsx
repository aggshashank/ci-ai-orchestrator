import React from 'react'
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts'

const REC_COLORS = {
  APPROVE:       '#22c55e',
  DECLINE:       '#ef4444',
  MANUAL_REVIEW: '#f59e0b',
}

export function RecommendationBar({ data, xKey = 'date' }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="approvals"      name="Approve"       fill={REC_COLORS.APPROVE} />
        <Bar dataKey="declines"       name="Decline"       fill={REC_COLORS.DECLINE} />
        <Bar dataKey="manual_reviews" name="Manual Review" fill={REC_COLORS.MANUAL_REVIEW} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ApprovalRateLine({ data, xKey = 'date' }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={v => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 11 }} domain={[0, 1]} />
        <Tooltip formatter={v => `${(v * 100).toFixed(1)}%`} />
        <Line dataKey="approval_rate" name="Approval Rate" stroke="#3b82f6" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function RecommendationPie({ data }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={80}
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
        >
          {data.map((entry, i) => (
            <Cell key={i} fill={REC_COLORS[entry.name] ?? '#94a3b8'} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  )
}
