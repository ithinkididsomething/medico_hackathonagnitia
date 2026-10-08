import { useState } from 'react'
import Layout from './components/Layout.jsx'
import AssessmentForm from './components/AssessmentForm.jsx'
import ResultView from './components/ResultView.jsx'
import ReferralDashboard from './components/ReferralDashboard.jsx'
import FlowSteps from './components/FlowSteps.jsx'
import KnowledgeReference from './components/KnowledgeReference.jsx'

// Complete workflow: Patient assessment -> Urgency -> Clinic capability check
// -> Manage locally | Referral required -> Matching -> Ranking -> Referral
// summary -> Referral tracking (dashboard).
export default function App() {
  const [view, setView] = useState('assess')
  const [result, setResult] = useState(null)

  function handleReset() {
    setResult(null)
    window.scrollTo({ top: 0 })
  }

  function handleNavigate(next) {
    setView(next)
    if (next === 'assess') setResult(null)
    window.scrollTo({ top: 0 })
  }

  return (
    <Layout view={view} onNavigate={handleNavigate}>
      {view === 'dashboard' ? (
        <ReferralDashboard onNavigate={handleNavigate} />
      ) : view === 'knowledge' ? (
        <KnowledgeReference />
      ) : result ? (
        <ResultView
          result={result}
          onReset={handleReset}
          onNavigate={handleNavigate}
        />
      ) : (
        <>
          <FlowSteps
            step={0}
            outcome="Start with a structured patient assessment — the flow below
            runs automatically from here."
          />
          <AssessmentForm onResult={setResult} />
        </>
      )}
    </Layout>
  )
}
