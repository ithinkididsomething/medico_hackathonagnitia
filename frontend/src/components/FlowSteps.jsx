// Part 1: the complete referral workflow, shown as a step strip so clinic
// staff always know where the current case is in the flow.

const FLOW = [
  'Patient assessment',
  'Urgency assessment',
  'Clinic capability check',
  'Hospital capability matching',
  'Availability & travel time',
  'Hospital ranking',
  'Referral summary',
  'Referral tracking',
]

export default function FlowSteps({ step = 0, outcome = '' }) {
  return (
    <nav className="flow-steps" aria-label="Referral workflow">
      <ol className="flow-list">
        {FLOW.map((label, index) => {
          const state =
            index < step ? 'is-done' : index === step ? 'is-active' : 'is-todo'
          return (
            <li
              key={label}
              className={`flow-item ${state}`}
              aria-current={state === 'is-active' ? 'step' : undefined}
            >
              <span className="flow-dot" aria-hidden="true">
                {state === 'is-done' ? '✓' : index + 1}
              </span>
              <span className="flow-label">{label}</span>
            </li>
          )
        })}
      </ol>
      {outcome ? <p className="flow-outcome">{outcome}</p> : null}
    </nav>
  )
}
