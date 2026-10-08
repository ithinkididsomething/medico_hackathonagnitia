import UrgencyBadge from './UrgencyBadge.jsx'

export default function ResultView({ result, onReset }) {
  const { urgency, decision, assessment } = result
  const reasons = urgency.explanations || []
  const firedRules = (urgency.rule_details || []).filter((rule) => rule.triggered)

  return (
    <div className="result-flow">
      {/* 1. Assessment summary ------------------------------------------------ */}
      <section className="card">
        <header className="card-header">
          <h1>Assessment result</h1>
          <span className="muted">#{result.id} · {result.created_at}</span>
        </header>
        <div className="summary-chips">
          <span className="chip"><strong>ID</strong> {assessment.patient_id}</span>
          <span className="chip"><strong>Age</strong> {assessment.age_years}</span>
          <span className="chip"><strong>Sex</strong> {assessment.sex}</span>
          {assessment.known_specialty ? (
            <span className="chip"><strong>Specialty</strong> {assessment.known_specialty}</span>
          ) : null}
        </div>
        <p className="summary-complaint">{assessment.chief_complaint}</p>
      </section>

      {/* 2. Urgency ----------------------------------------------------------- */}
      <section className={`card urgency-card tone-${urgency.level.toLowerCase()}`}>
        <header className="card-header">
          <h2>Urgency</h2>
          <span className="muted">score {urgency.score} · {urgency.rules_source} rules</span>
        </header>

        <div className={`urgency-band tone-${urgency.level.toLowerCase()}`}>
          <span className="urgency-level">{urgency.level}</span>
          <span className="urgency-label-big">{urgency.label}</span>
        </div>

        <h3 className="subhead">Reasons</h3>
        {reasons.length > 0 ? (
          <ul className="reason-list">
            {reasons.map((text) => <li key={text}>{text}</li>)}
          </ul>
        ) : (
          <p className="muted">No demonstration rule was triggered for this assessment.</p>
        )}

        <details className="rule-details">
          <summary>Show all rules used ({urgency.rule_details.length})</summary>
          <table>
            <thead>
              <tr>
                <th>Rule</th>
                <th>Severity</th>
                <th>Triggered</th>
                <th>Score</th>
                <th>Explanation</th>
              </tr>
            </thead>
            <tbody>
              {urgency.rule_details.map((rule) => (
                <tr key={rule.rule_id} className={rule.triggered ? 'is-triggered' : ''}>
                  <td>{rule.rule_id}</td>
                  <td><UrgencyBadge level={rule.severity} /></td>
                  <td>{rule.triggered ? 'yes' : 'no'}</td>
                  <td>{rule.score}</td>
                  <td>{rule.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted fine-print">{urgency.disclaimer}</p>
        </details>
      </section>

      {/* 3. Decision ---------------------------------------------------------- */}
      <section className={`card decision-card tone-${urgency.level.toLowerCase()}`}>
        <header className="card-header">
          <h2>Initial clinic decision</h2>
        </header>
        <p className={`decision-label tone-${urgency.level.toLowerCase()}`}>{decision.label}</p>
        <p>{decision.note}</p>
        <p className="muted fine-print">{decision.basis}</p>
        <p className="muted fine-print">
          Recommendations must be reviewed by a qualified healthcare professional.
        </p>
      </section>

      <div className="form-actions">
        <button type="button" className="btn btn-primary" onClick={onReset}>
          New assessment
        </button>
      </div>
    </div>
  )
}
