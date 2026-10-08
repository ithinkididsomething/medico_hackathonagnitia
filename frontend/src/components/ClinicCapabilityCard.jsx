// Part 1 UI: can the current clinic potentially manage this case locally?
// Shows the configured clinic profile, the verdict, met requirements and gaps.

export default function ClinicCapabilityCard({ capability }) {
  if (!capability) return null

  const { clinic, can_manage_locally: canManage, met_requirements: met = [], missing_capabilities: missing = [], reasons = [], disclaimer } = capability

  return (
    <section className="card clinic-card">
      <header className="card-header">
        <h2>Clinic resources</h2>
        <span className="muted">{clinic?.name}</span>
      </header>

      <div className={`clinic-verdict ${canManage ? 'tone-green' : 'tone-orange'}`}>
        <strong>
          {canManage
            ? 'This clinic can potentially manage the case locally'
            : 'Referral needed - this clinic cannot cover all requirements'}
        </strong>
      </div>

      <div className="summary-chips">
        {(clinic?.capabilities || []).map((code) => (
          <span key={code} className="chip cap-chip">
            {code.replace(/_/g, ' ')}
          </span>
        ))}
      </div>

      {met.length > 0 ? (
        <>
          <h3 className="subhead">Requirements covered locally</h3>
          <ul className="reason-list">
            {met.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}

      {missing.length > 0 ? (
        <>
          <h3 className="subhead">Missing at this clinic</h3>
          <div className="summary-chips">
            {missing.map((item) => (
              <span key={item} className="chip cap-chip missing">{item}</span>
            ))}
          </div>
        </>
      ) : null}

      <h3 className="subhead">Why</h3>
      <ul className="reason-list">
        {reasons.map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>

      <p className="muted fine-print">{disclaimer}</p>
    </section>
  )
}
