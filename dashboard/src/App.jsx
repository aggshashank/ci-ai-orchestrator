import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import StrategyDashboard  from './pages/StrategyDashboard'
import SimulationRunner   from './pages/SimulationRunner'
import ExperimentManager  from './pages/ExperimentManager'
import DecisionExplorer   from './pages/DecisionExplorer'
import FairnessReport     from './pages/FairnessReport'
import EvalResults        from './pages/EvalResults'
import RuleEditor         from './pages/RuleEditor'
import RulePreview        from './pages/RulePreview'
import RuleDeployment     from './pages/RuleDeployment'
import AnalyticsDashboard from './pages/AnalyticsDashboard'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/strategy" replace />} />
          <Route path="strategy"   element={<StrategyDashboard />} />
          <Route path="simulation" element={<SimulationRunner />} />
          <Route path="experiment" element={<ExperimentManager />} />
          <Route path="decisions"  element={<DecisionExplorer />} />
          <Route path="fairness"   element={<FairnessReport />} />
          <Route path="evals"      element={<EvalResults />} />
          <Route path="rules"      element={<RuleEditor />} />
          <Route path="rules/preview"  element={<RulePreview />} />
          <Route path="rules/deploy"   element={<RuleDeployment />} />
          <Route path="analytics"  element={<AnalyticsDashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
