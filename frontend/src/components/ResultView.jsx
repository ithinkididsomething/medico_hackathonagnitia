import { useState } from 'react'
import { api } from '../lib/api.js'
import ClinicCapabilityCard from './ClinicCapabilityCard.jsx'
import FlowSteps from './FlowSteps.jsx'
import HospitalRecommendations from './HospitalRecommendations.jsx'
import ReferralLevelBar from './ReferralLevelBar.jsx'
import ReferralSummary from './ReferralSummary.jsx'
import UrgencyBadge from './UrgencyBadge.jsx'

export default function ResultView({ result, onReset, onNavigate }) {
  const { urgency, decision, assessment } = result
  const reasons = urgency.explanations || []
  const firedRules = (urgency.rule_details || []).filter((rule) => rule.triggered)
  const needsReferral = ['referral_recommended', 'immediate_referral'].includes(decision.code)

  const [matches, setMatches] = useState(result.hospital_matches || null)
  const [matchError, setMatchError] = useState(null)
  const [matching, setMatching] = useState(false)

  const [referral, setReferral] = useState(null)
  const [referralBusy, setReferralBusy] = useState(false)
  const [referralError, setReferralError] = useState(null)

  async function handleFindHospitals() {
    setMatching(true)
    setMatchError(null)
    try {
      const payload = await api.matchHospitals({ assessment_id: result.id })
      setMatches(payload)
    } catch (error) {
      setMatchError(error.message || 'Hospital matching failed.')
    } finally {
      setMatching(false)
    }
  }

  async function handleCreateReferral() {
    setReferralBusy(true)
    setReferralError(null)
    try {
      const created = await api.createReferral({ assessment_id: result.id })
      setReferral(created)
      window.scrollTo({ top: 0 })
    } catch (error) {
      setReferralError(error.message || 'Referral record could not be created.')
    } finally {
      setReferralBusy(false)
    }
  }

  // Position in the end-to-end flow (Part 1).
  const flowStep = referral ? 7 : needsReferral ? (matches ? 6 : 3) : 3
  const flowOutcome = referral
    ? `Referral ${referral.referral_id} created — track its status in the referral dashboard.`
    : !needsReferral
      ? 'Outcome: the clinic can manage this patient locally — no referral required.'
      : matches
        ? 'Next: create the referral record to generate the structured summary.'
        : 'Next: run hospital capability matching for the derived requirements.'

  return (
    <div className="result-flow">
      <FlowSteps step={flowStep} outcome={flowOutcome} />

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

      {/* 1b. Suggested referral level (Prompt 7) — primary visual element. */}
      {result.referral_level ? (
        <ReferralLevelBar level={result.referral_level} />
      ) : null}

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

      {/* 4. Case requirements -------------------------------------------------- */}
      {result.requirements ? (
        <section className="card">
          <header className="card-header">
            <h2>Derived case requirements</h2>
            <span className="muted">{result.requirements.rules_source} rules</span>
          </header>
          <div className="summary-chips">
            <span className="chip"><strong>Specialty</strong> {result.requirements.required_specialty}</span>
            <span className="chip"><strong>Emergency</strong> {result.requirements.needs_emergency}</span>
            {result.requirements.needs_icu ? (
              <span className="chip"><strong>ICU</strong> required</span>
            ) : (
              <span className="chip"><strong>ICU</strong> not required</span>
            )}
            {result.requirements.required_diagnostics?.length ? (
              <span className="chip"><strong>Diagnostics</strong> {result.requirements.required_diagnostics.join(', ')}</span>
            ) : null}
            {result.requirements.required_treatment?.length ? (
              <span className="chip"><strong>Treatments</strong> {result.requirements.required_treatment.join(', ')}</span>
            ) : null}
          </div>
          <ul className="reason-list fine-print">
            {result.requirements.explanations.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
          <p className="muted fine-print">{result.requirements.disclaimer}</p>
        </section>
      ) : null}

      {/* 5. Clinic capability (Part 1) ------------------------------------------ */}
      <ClinicCapabilityCard capability={result.clinic_capability} />

      {/* 5b. Clinical & Diagnostic Context (Advisory) -------------------------- */}
      {result.knowledge_context && (result.knowledge_context.notices?.length > 0 || result.knowledge_context.resource_sensitivity_notes?.length > 0) ? (
        <section className="card diagnostic-context-card">
          <header className="card-header">
            <h2>Clinical &amp; Diagnostic Context</h2>
            <span className="muted">Advisory decision support</span>
          </header>
          
          {result.knowledge_context.notices?.map((notice, idx) => (
            <div key={idx} className="alert alert-info" style={{ marginBottom: '1rem', padding: '0.75rem', borderLeft: '4px solid var(--color-primary, #0d9488)', backgroundColor: '#f0fdfa', borderRadius: '4px' }}>
              <p style={{ margin: 0 }}>{notice}</p>
            </div>
          ))}

          {result.knowledge_context.resource_sensitivity_notes?.length > 0 ? (
            <div style={{ marginTop: '1rem' }}>
              <h3 className="subhead">Resource Sensitivity &amp; Risks</h3>
              <ul className="reason-list fine-print">
                {result.knowledge_context.resource_sensitivity_notes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {result.knowledge_context.relevant_mimics?.length > 0 ? (
            <div style={{ marginTop: '1.5rem' }}>
              <h3 className="subhead" style={{ marginBottom: '0.5rem' }}>Potential Symptom Overlaps (Mimics)</h3>
              <div className="table-wrapper">
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                      <th style={{ padding: '0.5rem' }}>Potential Mimic</th>
                      <th style={{ padding: '0.5rem' }}>Why Overlaps</th>
                      <th style={{ padding: '0.5rem' }}>Distinguishing Clinical Info</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.knowledge_context.relevant_mimics.map((mimic, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #edf2f7' }}>
                        <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>
                          {mimic.confused_with}
                          <div style={{ fontSize: '0.75rem', fontWeight: 'normal', color: '#718096' }}>
                            Evidence: {mimic.evidence_status?.replace(/_/g, ' ')}
                          </div>
                        </td>
                        <td style={{ padding: '0.5rem' }}>{mimic.why}</td>
                        <td style={{ padding: '0.5rem' }}>
                          <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                            {(mimic.distinguishing_info || []).map((info, i) => (
                              <li key={i}>{info}</li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
          <p className="muted fine-print" style={{ marginTop: '1rem', borderTop: '1px dashed #e2e8f0', paddingTop: '0.5rem' }}>
            {result.knowledge_context.disclaimer}
          </p>
        </section>
      ) : null}

      {/* 6. Hospital recommendations (Parts 3-6) -------------------------------- */}
      {matches ? (
        <HospitalRecommendations match={matches} />
      ) : needsReferral ? (
        <section className="card">
          <header className="card-header">
            <h2>Hospital recommendations</h2>
          </header>
          <p className="muted">
            Matching was not included in this result. Run it to rank suitable hospitals
            for the derived requirements.
          </p>
          {matchError ? <p className="error" role="alert">{matchError}</p> : null}
          <div className="form-actions">
            <button type="button" className="btn btn-primary" onClick={handleFindHospitals} disabled={matching}>
              {matching ? 'Matching…' : 'Find suitable hospitals'}
            </button>
          </div>
        </section>
      ) : null}

      {/* 7. Referral summary + record (Parts 2-3) ------------------------------ */}
      {needsReferral && matches && referral ? (
        <>
          <ReferralSummary referral={referral} />
          <div className="form-actions no-print">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onNavigate?.('dashboard')}
            >
              Open referral dashboard
            </button>
            <button type="button" className="btn btn-ghost" onClick={onReset}>
              New assessment
            </button>
          </div>
        </>
      ) : needsReferral && matches ? (
        <section className="card">
          <header className="card-header">
            <h2>Referral summary</h2>
          </header>
          {matches.best_match ? (
            <p className="muted">
              Create the referral record to generate the structured summary
              (patient, findings, urgency, required specialty, recommended +
              alternative hospital, travel time and the full explanation) and
              start status tracking.
            </p>
          ) : (
            <div className="hospital-empty">
              <p>
                <strong>
                  No suitable facility found based on the currently configured
                  capabilities and simulated availability.
                </strong>{' '}
                A referral record cannot be created — arrange escalation manually
                and review the exclusion reasons below.
              </p>
            </div>
          )}
          {referralError ? (
            <p className="error form-error" role="alert">
              {referralError}
            </p>
          ) : null}
          <div className="form-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleCreateReferral}
              disabled={referralBusy || !matches.best_match}
            >
              {referralBusy ? 'Creating referral…' : 'Create referral record'}
            </button>
          </div>
        </section>
      ) : null}

      <div className="form-actions">
        <button type="button" className="btn btn-primary" onClick={onReset}>
          New assessment
        </button>
        {needsReferral ? (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => onNavigate?.('dashboard')}
          >
            Referral dashboard
          </button>
        ) : null}
      </div>
    </div>
  )
}
