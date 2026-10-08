import { api } from '../lib/api.js'
import { useAsync } from '../hooks/useAsync.js'

export default function HealthBadge() {
  const { data, error, loading, reload } = useAsync(api.health, [])

  let label = 'checking…'
  let tone = 'pending'
  if (error) {
    label = 'backend offline'
    tone = 'error'
  } else if (!loading && data) {
    label = data.status === 'ok' ? 'backend online' : `backend ${data.status}`
    tone = data.status === 'ok' ? 'ok' : 'warn'
  }

  return (
    <button
      type="button"
      className={`health-badge tone-${tone}`}
      onClick={reload}
      title="Click to re-check /api/health"
    >
      <span className="dot" aria-hidden="true" />
      {label}
      {error ? <span className="health-detail"> — {error}</span> : null}
    </button>
  )
}
