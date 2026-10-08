import HealthBadge from './HealthBadge.jsx'

const NAV_ITEMS = [
  { id: 'assess', label: 'New assessment' },
  { id: 'dashboard', label: 'Referral dashboard' },
  { id: 'knowledge', label: 'Clinical reference' },
]

export default function Layout({ children, view = 'assess', onNavigate }) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">medico</span>
          <span className="brand-tag">referral decision support</span>
        </div>
        <nav className="main-nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-tab${view === item.id ? ' is-active' : ''}`}
              aria-current={view === item.id ? 'page' : undefined}
              onClick={() => onNavigate?.(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <HealthBadge />
      </header>

      <div className="safety-banner" role="note">
        <strong>Decision-support prototype — not a medical device.</strong> All
        recommendations must be reviewed by a qualified healthcare professional.
        Rules are demonstration-only and not clinically validated.
      </div>

      <main className="app-main">{children}</main>

      <footer className="app-footer">
        Prototype · React · FastAPI · SQLite/PostgreSQL-ready · No patient names or
        contact details are collected
      </footer>
    </div>
  )
}
