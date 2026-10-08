import HealthBadge from './HealthBadge.jsx'

export default function Layout({ children }) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">medico</span>
          <span className="brand-tag">referral decision support</span>
        </div>
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
