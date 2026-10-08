// Prompt 7: visual four-step rural referral-level bar + details card.
//
// Backend-driven: `level` is the referral_level payload from the API
// (never hard-coded here). The active step is highlighted strongly, lower
// steps are marked passed, higher steps stay visible but subdued. Status is
// never conveyed by color alone — every step shows its number, label,
// tagline and text state ("current", "passed", "upcoming").

const STEPS = [
  { level: 1, label: 'Home / Observe', glyph: '⌂' },
  { level: 2, label: 'Clinic / PHC', glyph: '+' },
  { level: 3, label: 'Urgent Referral', glyph: '!' },
  { level: 4, label: 'Emergency Hospital', glyph: '✚' },
]

function stepState(step, current) {
  if (step === current) return 'current'
  if (step < current) return 'passed'
  return 'upcoming'
}

function stepTone(step) {
  if (step <= 1) return 'tone-green'
  if (step === 2) return 'tone-accent'
  if (step === 3) return 'tone-orange'
  return 'tone-red'
}

export default function ReferralLevelBar({ level }) {
  if (!level || typeof level.level !== 'number') return null
  const current = level.level

  return (
    <section className="card referral-level-card" aria-labelledby="referral-level-heading">
      <header className="card-header">
        <h2 id="referral-level-heading">Suggested referral level</h2>
        <span className="muted">Decision-support recommendation · based on entered information</span>
      </header>

      {/* Visual bar ------------------------------------------------------ */}
      <ol className="rl-bar" aria-label="Referral levels 1 to 4">
        {STEPS.map((step) => {
          const state = stepState(step.level, current)
          return (
            <li
              key={step.level}
              className={`rl-step ${stepTone(step.level)} is-${state}`}
              aria-current={state === 'current' ? 'step' : undefined}
            >
              <span className="rl-glyph" aria-hidden="true">{step.glyph}</span>
              <span className="rl-number" aria-hidden="true">{step.level}</span>
              <span className="rl-step-body">
                <span className="rl-step-label">
                  Level {step.level} — {step.label}
                </span>
                <span className="rl-step-state">
                  {state === 'current'
                    ? 'Current level'
                    : state === 'passed'
                      ? 'Passed'
                      : `Step ${step.level} of 4`}
                </span>
              </span>
              {step.level < 4 ? <span className="rl-link" aria-hidden="true" /> : null}
            </li>
          )
        })}
      </ol>

      {/* Current-level headline ------------------------------------------- */}
      <div className={`rl-current ${stepTone(current)}`} role="status">
        <p className="rl-current-kicker">Current: Level {current}</p>
        <p className="rl-current-name">{level.name}</p>
        {level.tagline ? <p className="rl-current-tagline">{level.tagline}</p> : null}
        {level.action ? (
          <p className="rl-current-action">
            <strong>Suggested action:</strong> {level.action}
          </p>
        ) : null}
      </div>

      {/* Details card (Prompt 7 §7) ---------------------------------------- */}
      <div className="rl-details">
        <h3 className="subhead">Level {current} — {level.name}</h3>
        {level.description ? <p>{level.description}</p> : null}
        {level.reason ? (
          <p className="rl-why">
            <strong>Why:</strong> {level.reason}
          </p>
        ) : null}
        {level.triggered_rules?.length ? (
          <p className="muted fine-print">
            Triggered assessment rules: {level.triggered_rules.join(', ')}
          </p>
        ) : (
          <p className="muted fine-print">
            No higher-level criteria were triggered by the entered information.
          </p>
        )}
        <div className="summary-chips">
          <span className="chip">
            <strong>Referral</strong> {level.referral_recommended ? 'recommended' : 'not normally required'}
          </span>
          <span className="chip">
            <strong>Emergency transport</strong>{' '}
            {level.emergency_transport ? 'consider now' : 'not indicated'}
          </span>
        </div>
        {level.disclaimer ? <p className="muted fine-print">{level.disclaimer}</p> : null}
      </div>
    </section>
  )
}
