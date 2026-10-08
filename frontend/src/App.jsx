import { useState } from 'react'
import Layout from './components/Layout.jsx'
import AssessmentForm from './components/AssessmentForm.jsx'
import ResultView from './components/ResultView.jsx'

// Main flow: Patient Assessment -> Assessment Result -> Urgency -> Decision.
export default function App() {
  const [result, setResult] = useState(null)

  function handleReset() {
    setResult(null)
    window.scrollTo({ top: 0 })
  }

  return (
    <Layout>
      {result ? (
        <ResultView result={result} onReset={handleReset} />
      ) : (
        <AssessmentForm onResult={setResult} />
      )}
    </Layout>
  )
}
