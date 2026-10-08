// Part 2: structured referral summary — viewed cleanly, printable, exportable
// as plain text. Renders only backend-generated data (no client scoring).

import { api } from '../lib/api.js'

const STATUS_LABELS = {
  pending: 'Pending',
  referred: 'Referred',
  accepted: 'Accepted',
  transferred: 'Transferred',
  completed: 'Completed',
}

export function StatusBadge({ status }) {
  return (
    <span className={`status-badge status-${status}`}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

export function PriorityBadge({ priority, urgency }) {
  const level = (priority || '').toLowerCase() || 'routine'
  return (
    <span className={`priority-badge priority-${level}`}>
      {level === 'emergency' ? 'Emergency' : level === 'urgent' ? 'Urgent' : 'Routine'}
      {urgency ? <span className="priority-code"> ({urgency})</span> : null}
    </span>
  )
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

function HospitalBlock({ entry, role }) {
  if (!entry) return null
  return (
    <div className={`summary-hospital role-${role}`}>
      <div className="summary-hospital-head">
        <span className={`rank-badge ${role === 'recommended' ? 'best' : ''}`}>
          {role === 'recommended' ? 'Recommended' : 'Alternative'}
        </span>
        <strong>{entry.name}</strong>
        {entry.suitability_score != null ? (
          <span className="score-badge quiet">
            Suitability <strong>{entry.suitability_score}</strong>/100
          </span>
        ) : null}
      </div>
      <p className="muted fine-print travel-line">
        Distance: <strong>{formatValue(entry.distance_km)} km</strong> · Estimated
        travel time:{' '}
        <strong>
          {entry.estimated_travel_minutes != null
            ? `~${Math.round(entry.estimated_travel_minutes)} min`
            : '—'}
        </strong>{' '}
        — {entry.travel_source === 'osrm' ? 'road routing (OSRM)' : 'straight-line estimate'}
      </p>
      {entry.reasons?.length ? (
        <ul className="reason-list fine-print">
          {entry.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

export default function ReferralSummary({ referral }) {
  const summary = referral.summary || {}
  const vitals = summary.vitals || {}
  const facilities = summary.required_facilities || {}
  const alternativeWhyNot = summary.why_alternatives || {}

  async function handleDownload() {
    try {
      const data = await api.referralSummaryText(referral.referral_id)
      const blob = new Blob([data.text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${referral.referral_id}.txt`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      window.print() // fall back to the browser print dialog
      console.warn('Text export failed:', error.message) // eslint-disable-line no-console
    }
  }

  return (
    <section className="card referral-summary printable">
      <header className="card-header">
        <h2>Referral summary</h2>
        <span className="muted">
          {referral.referral_id} · created {referral.created_at}
        </span>
      </header>

      <div className="summary-chips">
        <PriorityBadge priority={referral.priority} urgency={referral.urgency} />
        <StatusBadge status={referral.status} />
        <span className="chip">
          <strong>Case</strong> {referral.recommendation.replace(/_/g, ' ')}
        </span>
      </div>

      {/* Patient + presentation (clinic-assigned id only — no names) */}
      <dl className="summary-grid">
        <dt>Patient ID</dt>
        <dd>{formatValue(summary.patient_id)}</dd>
        <dt>Age</dt>
        <dd>{formatValue(summary.age_years)}</dd>
        <dt>Sex</dt>
        <dd>{formatValue(summary.sex)}</dd>
        <dt>Main complaint</dt>
        <dd>{formatValue(summary.chief_complaint)}</dd>
        <dt>Important clinical findings</dt>
        <dd className="summary-multiline">{formatValue(summary.clinical_findings)}</dd>
        <dt>Urgency level</dt>
        <dd>
          <PriorityBadge priority={referral.priority} urgency={referral.urgency} />
          {summary.urgency?.label ? <span> — {summary.urgency.label}</span> : null}
        </dd>
      </dl>

      <h3 className="subhead">Vital signs</h3>
      <div className="summary-chips">
        {Object.keys(vitals).length > 0 ? (
          Object.entries(vitals).map(([key, value]) => (
            <span key={key} className="chip">
              <strong>{key.replace(/_/g, ' ')}</strong> {value}
            </span>
          ))
        ) : (
          <span className="chip">—</span>
        )}
      </div>

      <h3 className="subhead">Reason for referral</h3>
      <ul className="reason-list">
        {(summary.reason_for_referral || []).map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>

      {/* Prompt 7: suggested referral level persisted with the record */}
      {summary.referral_level ? (
        <>
          <h3 className="subhead">Suggested referral level</h3>
          <dl className="summary-grid">
            <dt>Suggested referral level</dt>
            <dd>
              Level {summary.referral_level.level} — {formatValue(summary.referral_level_name)}
            </dd>
            <dt>Recommended action</dt>
            <dd>{formatValue(summary.referral_level_action)}</dd>
            <dt>Reason</dt>
            <dd className="summary-multiline">{formatValue(summary.referral_level_reason)}</dd>
          </dl>
          {summary.referral_level_rules?.length ? (
            <p className="muted fine-print">
              Triggered rules: {summary.referral_level_rules.join(', ')}
            </p>
          ) : null}
        </>
      ) : null}

      <div className="summary-chips summary-facilities">
        <span className="chip">
          <strong>Required specialty</strong> {formatValue(summary.required_specialty)}
        </span>
        <span className="chip">
          <strong>Emergency</strong> {facilities.emergency_level || 'none'}
        </span>
        <span className="chip">
          <strong>ICU</strong> {facilities.icu ? 'required' : 'not required'}
        </span>
        {facilities.diagnostics?.length ? (
          <span className="chip">
            <strong>Diagnostics</strong> {facilities.diagnostics.join(', ')}
          </span>
        ) : null}
        {facilities.treatment?.length ? (
          <span className="chip">
            <strong>Treatment</strong> {facilities.treatment.join(', ')}
          </span>
        ) : null}
      </div>

      <h3 className="subhead">Recommended hospital</h3>
      <HospitalBlock entry={summary.recommended_hospital} role="recommended" />

      <h3 className="subhead">Alternative hospital</h3>
      {summary.alternative_hospital ? (
        <HospitalBlock entry={summary.alternative_hospital} role="alternative" />
      ) : (
        <p className="muted fine-print">
          No second eligible hospital is available for this case.
        </p>
      )}

      {Object.keys(alternativeWhyNot).length > 0 ? (
        <>
          <h3 className="subhead">Why alternatives ranked lower</h3>
          <ul className="why-not-list">
            {Object.entries(alternativeWhyNot).map(([name, reasons]) => (
              <li key={name} className="why-not-item">
                <strong>Why not {name}:</strong>
                <ul className="reason-list fine-print">
                  {reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {summary.fallback_detail ? (
        <div className="fallback-block" role="status">
          <p className="fine-print">
            <strong>Fallback applied:</strong>{' '}
            {summary.fallback_detail.primary_name} was{' '}
            {summary.fallback_detail.primary_status}; referred to{' '}
            {summary.fallback_detail.fallback_name} — {summary.fallback_detail.reason}
          </p>
        </div>
      ) : null}

      <h3 className="subhead">Recommendation explanation</h3>
      <p className="summary-explanation">
        {formatValue(summary.recommendation_explanation)}
      </p>

      <div className="form-actions no-print">
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>
          Print / Save as PDF
        </button>
        <button type="button" className="btn btn-ghost" onClick={handleDownload}>
          Download .txt
        </button>
      </div>

      <div className="summary-disclaimers">
        {(summary.disclaimers || []).map((text) => (
          <p key={text} className="muted fine-print">
            {text}
          </p>
        ))}
        {summary.travel_estimate_note ? (
          <p className="muted fine-print">{summary.travel_estimate_note}</p>
        ) : null}
      </div>
    </section>
  )
}
