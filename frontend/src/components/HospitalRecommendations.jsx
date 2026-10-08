// Parts 3-6 + Prompt 3 UI: hospital recommendation view with travel-aware
// ranking. BEST MATCH first, then alternatives, then "why not" explanations,
// then excluded hospitals with reasons. Includes the referral map (Part 7).
// Explicitly capability-based (not "nearest hospital"): every score shows its
// factor breakdown and plain-language reasons. Data is SYNTHETIC.

import ReferralMap from './ReferralMap.jsx'

const FACTOR_ORDER = [
  'specialty_match',
  'emergency_capability',
  'icu_capability',
  'diagnostics_match',
  'treatment_match',
  'capacity',
  'distance',
  'travel_time',
]

const AVAILABILITY_LABELS = {
  open: 'Open',
  diverting: 'Diverting',
  closed: 'Closed',
}

const CAPACITY_LABELS = {
  open: 'Open capacity',
  limited: 'Limited capacity',
  full: 'At capacity',
}

const EMERGENCY_LABELS = { full: 'Full emergency', basic: 'Basic emergency', none: 'No emergency dept' }
const ICU_LABELS = { available: 'ICU available', limited: 'ICU limited', none: 'No ICU' }

function specialtyLabel(code) {
  return String(code || '').replace(/_/g, ' ')
}

function hospitalChips(hospital) {
  const chips = [
    `${EMERGENCY_LABELS[hospital.emergency_capability] || hospital.emergency_capability}`,
    `${ICU_LABELS[hospital.icu_capability] || hospital.icu_capability}`,
    `${CAPACITY_LABELS[hospital.capacity_status] || hospital.capacity_status} (${hospital.available_beds} beds)`,
    AVAILABILITY_LABELS[hospital.availability_status] || hospital.availability_status,
  ]
  return chips
}

function travelInfo(travel) {
  if (!travel) return null
  const minutes = travel.travel_minutes ?? travel.travel_minutes_placeholder ?? null
  const routed = travel.source === 'osrm'
  return {
    distanceKm: travel.distance_km ?? null,
    minutes,
    routed,
    note: travel.note || '',
  }
}

function TravelLine({ travel, prefix = '' }) {
  const info = travelInfo(travel)
  if (!info || info.distanceKm == null) return null
  const minutes = info.minutes != null ? `~${Math.round(info.minutes)} min` : 'time unknown'
  const source = info.routed
    ? 'road routing (OSRM)'
    : 'straight-line placeholder (road routing unavailable)'
  return (
    <p className="muted fine-print travel-line">
      {prefix}
      Distance: <strong>{info.distanceKm} km</strong> · Estimated travel time:{' '}
      <strong>{minutes}</strong> — {source}.
    </p>
  )
}

function FactorBreakdown({ factorScores }) {
  const factors = FACTOR_ORDER.filter((key) => factorScores?.[key]).map((key) => [key, factorScores[key]])
  if (factors.length === 0) return null
  return (
    <table className="factor-table">
      <thead>
        <tr>
          <th>Scoring factor</th>
          <th>Points</th>
          <th>Why</th>
        </tr>
      </thead>
      <tbody>
        {factors.map(([key, factor]) => (
          <tr key={key}>
            <td>{factor.label || key}</td>
            <td>
              <strong>{factor.earned}</strong> / {factor.possible}
            </td>
            <td>{factor.reason}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function FallbackDetail({ detail, note }) {
  if (!detail && !note) return null
  return (
    <div className="fallback-block" role="status">
      {detail ? (
        <dl className="fallback-grid">
          <dt>Primary hospital</dt>
          <dd>{detail.primary_name}</dd>
          <dt>Status</dt>
          <dd className="fallback-status">{detail.primary_status}</dd>
          <dt>Fallback</dt>
          <dd>{detail.fallback_name || 'None — no eligible hospital remains'}</dd>
          <dt>Reason</dt>
          <dd>{detail.reason}</dd>
        </dl>
      ) : (
        <p className="fallback-note"><strong>Fallback applied:</strong> {note}</p>
      )}
    </div>
  )
}

function WhyNotList({ entries }) {
  const items = (entries || []).filter((entry) => entry.why_not?.length)
  if (items.length === 0) return null
  return (
    <section className="why-not-section">
      <h3 className="subhead">Why not the other hospitals</h3>
      <ul className="why-not-list">
        {items.map((entry) => (
          <li key={entry.hospital.hospital_id} className="why-not-item">
            <strong>Why not {entry.hospital.name}:</strong>
            <ul className="reason-list fine-print">
              {entry.why_not.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  )
}

function BestMatchCard({ match, requirements }) {
  const { hospital } = match
  return (
    <div className="hospital-best">
      <div className="hospital-best-head">
        <span className="rank-badge best">Best match</span>
        <h3>{hospital.name} recommended</h3>
        <span className="score-badge">
          Suitability <strong>{match.total_score}</strong>/100
        </span>
      </div>

      <div className="summary-chips">
        {hospitalChips(hospital).map((chip) => (
          <span key={chip} className="chip cap-chip">{chip}</span>
        ))}
      </div>

      {requirements?.required_specialty ? (
        <p className="hospital-specialty">
          Required specialty: <strong>{specialtyLabel(requirements.required_specialty)}</strong>
          {hospital.specialties?.includes(requirements.required_specialty) ? ' (available)' : ''}
        </p>
      ) : null}

      <h4 className="subhead">Why this hospital</h4>
      <ul className="reason-list">
        {match.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>

      <TravelLine travel={match.travel} />

      <details className="rule-details">
        <summary>Show suitability score breakdown</summary>
        <FactorBreakdown factorScores={match.factor_scores} />
      </details>

      <p className="muted fine-print">{match.explanation}</p>
    </div>
  )
}

function AlternativeCard({ match, rank }) {
  const { hospital } = match
  return (
    <li className="hospital-alt">
      <div className="hospital-alt-head">
        <span className="rank-badge">{rank}</span>
        <strong>{hospital.name}</strong>
        <span className="score-badge quiet">
          Suitability <strong>{match.total_score}</strong>/100
        </span>
      </div>
      <div className="summary-chips">
        {hospitalChips(hospital).map((chip) => (
          <span key={chip} className="chip cap-chip">{chip}</span>
        ))}
      </div>
      <ul className="reason-list fine-print">
        {match.reasons.slice(0, 4).map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
      <TravelLine travel={match.travel} />
    </li>
  )
}

export default function HospitalRecommendations({ match }) {
  if (!match) return null

  const {
    best_match: best,
    alternatives = [],
    excluded = [],
    requirements,
    fallback_detail: fallbackDetail,
  } = match

  // "Why not" targets: runner-up eligible hospitals + excluded candidates.
  const whyNotEntries = best ? [...alternatives, ...excluded] : excluded

  return (
    <section className="card hospital-panel">
      <header className="card-header">
        <h2>Hospital recommendations</h2>
        <span className="muted">
          {match.eligible_count} suitable / {match.evaluated_count} evaluated
        </span>
      </header>

      <div className="requirements-chips summary-chips">
        <span className="chip"><strong>Specialty</strong> {specialtyLabel(requirements?.required_specialty)}</span>
        <span className="chip"><strong>Emergency</strong> {requirements?.needs_emergency}</span>
        {requirements?.needs_icu ? <span className="chip"><strong>ICU</strong> required</span> : null}
        {requirements?.required_diagnostics?.length ? (
          <span className="chip"><strong>Diagnostics</strong> {requirements.required_diagnostics.join(', ')}</span>
        ) : null}
        {requirements?.required_treatment?.length ? (
          <span className="chip"><strong>Treatments</strong> {requirements.required_treatment.join(', ')}</span>
        ) : null}
      </div>

      <FallbackDetail detail={fallbackDetail} note={match.fallback_note} />

      {best ? (
        <BestMatchCard match={best} requirements={requirements} />
      ) : (
        <div className="hospital-empty">
          <p>
            <strong>
              No suitable facility found based on the currently configured
              capabilities and simulated availability.
            </strong>{' '}
            None of the configured hospitals passed the hard capability
            constraints for this case — no recommendation is fabricated. Review
            the exclusion reasons below and arrange escalation manually.
          </p>
        </div>
      )}

      {alternatives.length > 0 ? (
        <>
          <h3 className="subhead">Alternative suitable hospitals</h3>
          <ol className="hospital-alts">
            {alternatives.map((alt, index) => (
              <AlternativeCard key={alt.hospital.hospital_id} match={alt} rank={index + 2} />
            ))}
          </ol>
        </>
      ) : null}

      <WhyNotList entries={whyNotEntries} />

      {/* Referral map (Part 7): clinic, recommended + alternatives, route. */}
      <ReferralMap match={match} />

      {excluded.length > 0 ? (
        <details className="rule-details hospital-excluded">
          <summary>Excluded hospitals and why ({excluded.length})</summary>
          <ul className="excluded-list">
            {excluded.map((entry) => (
              <li key={entry.hospital.hospital_id}>
                <strong>{entry.hospital.name}</strong>
                <ul>
                  {entry.exclusion_reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
                {entry.missing_capabilities?.length ? (
                  <p className="muted fine-print">
                    Missing: {entry.missing_capabilities.join(', ')}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <p className="muted fine-print">{match.travel_estimate_note}</p>
      <p className="muted fine-print">{match.summary_explanation}</p>
      <p className="muted fine-print">{match.weights_disclaimer}</p>
      <p className="muted fine-print">{match.data_disclaimer}</p>
      <p className="muted fine-print">
        Selected for capability fit for this case - not simply the nearest hospital.
        Recommendations must be reviewed by a qualified healthcare professional.
      </p>
    </section>
  )
}
