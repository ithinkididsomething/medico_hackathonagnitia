// Part 4: clinic-staff referral dashboard — filterable list/table, full detail
// view, and explicit audited status changes. Status authority is the backend.

import { useState } from 'react'
import { api } from '../lib/api.js'
import { useAsync } from '../hooks/useAsync.js'
import ReferralSummary, { PriorityBadge, StatusBadge } from './ReferralSummary.jsx'

// Display-only; the backend enforces the actual state machine.
const NEXT_STATUSES = {
  pending: ['referred'],
  referred: ['accepted', 'transferred'],
  accepted: ['transferred', 'completed'],
  transferred: ['completed'],
  completed: [],
}

const STATUS_HINTS = {
  pending: 'Waiting to be sent to a hospital.',
  referred: 'Referred — awaiting hospital response.',
  accepted: 'Hospital accepted the referral.',
  transferred: 'Patient transferred to the hospital.',
  completed: 'Episode completed.',
}

const EMPTY_FILTERS = {
  urgency: '',
  status: '',
  recommendation: '',
  date_from: '',
  date_to: '',
}

function FilterBar({ filters, onChange, counts }) {
  return (
    <div className="filter-bar" role="group" aria-label="Referral filters">
      <label className="field filter-field">
        <span>Priority</span>
        <select
          value={filters.urgency}
          onChange={(event) => onChange({ ...filters, urgency: event.target.value })}
        >
          <option value="">All priorities</option>
          <option value="RED">Emergency (RED)</option>
          <option value="ORANGE">Urgent (ORANGE)</option>
          <option value="GREEN">Routine (GREEN)</option>
        </select>
      </label>
      <label className="field filter-field">
        <span>Status</span>
        <select
          value={filters.status}
          onChange={(event) => onChange({ ...filters, status: event.target.value })}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="referred">Referred</option>
          <option value="accepted">Accepted</option>
          <option value="transferred">Transferred</option>
          <option value="completed">Completed</option>
        </select>
      </label>
      <label className="field filter-field">
        <span>Recommendation</span>
        <select
          value={filters.recommendation}
          onChange={(event) => onChange({ ...filters, recommendation: event.target.value })}
        >
          <option value="">All recommendations</option>
          <option value="immediate_referral">Immediate referral</option>
          <option value="referral_recommended">Referral recommended</option>
        </select>
      </label>
      <label className="field filter-field">
        <span>From date</span>
        <input
          type="date"
          value={filters.date_from}
          onChange={(event) => onChange({ ...filters, date_from: event.target.value })}
        />
      </label>
      <label className="field filter-field">
        <span>To date</span>
        <input
          type="date"
          value={filters.date_to}
          onChange={(event) => onChange({ ...filters, date_to: event.target.value })}
        />
      </label>
      <button
        type="button"
        className="btn btn-ghost filter-reset"
        onClick={() => onChange({ ...EMPTY_FILTERS })}
        disabled={Object.values(filters).every((value) => !value)}
      >
        Clear filters
      </button>
      {counts ? (
        <span className="muted fine-print filter-counts">
          {counts.urgency} priority · {counts.status} status
        </span>
      ) : null}
    </div>
  )
}

function StatusEditor({ referral, onUpdated, onError }) {
  const [status, setStatus] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const options = NEXT_STATUSES[referral.status] || []

  async function handleSubmit(event) {
    event.preventDefault()
    if (!status) return
    setBusy(true)
    onError(null)
    try {
      const updated = await api.updateReferralStatus(referral.referral_id, {
        status,
        note: note.trim(),
      })
      setStatus('')
      setNote('')
      onUpdated(updated)
    } catch (error) {
      onError(error.message)
    } finally {
      setBusy(false)
    }
  }

  if (options.length === 0) {
    return (
      <p className="muted fine-print" role="status">
        {STATUS_HINTS[referral.status]} This referral is closed — no further status
        changes are allowed.
      </p>
    )
  }

  return (
    <form className="status-editor" onSubmit={handleSubmit}>
      <label className="field filter-field">
        <span>Move to status</span>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">Choose a status…</option>
          {options.map((option) => (
            <option key={option} value={option}>
              {option.charAt(0).toUpperCase() + option.slice(1)}
            </option>
          ))}
        </select>
      </label>
      <label className="field filter-field">
        <span>Note (recorded in the audit trail)</span>
        <input
          type="text"
          value={note}
          maxLength={500}
          placeholder="e.g. ambulance dispatched"
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      <button
        type="submit"
        className="btn btn-primary"
        disabled={!status || busy}
      >
        {busy ? 'Saving…' : 'Update status'}
      </button>
    </form>
  )
}

function ReferralDetail({ referral, onBack, onChanged, onError }) {
  return (
    <div className="detail-flow">
      <div className="detail-toolbar no-print">
        <button type="button" className="btn btn-ghost" onClick={onBack}>
          ← Back to list
        </button>
        <span className="muted fine-print">
          {STATUS_HINTS[referral.status] || ''}
        </span>
      </div>

      <ReferralSummary referral={referral} />

      <section className="card no-print">
        <header className="card-header">
          <h2>Status tracking</h2>
          <span className="muted">Explicit transitions only — every change is audited</span>
        </header>

        <StatusEditor
          referral={referral}
          onUpdated={onChanged}
          onError={onError}
        />

        <h3 className="subhead">Status history</h3>
        <table className="history-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Change</th>
              <th>Note</th>
              <th>By</th>
            </tr>
          </thead>
          <tbody>
            {referral.status_history.map((event) => (
              <tr key={event.id}>
                <td>{event.created_at}</td>
                <td>
                  {event.from_status ? `${event.from_status} → ` : ''}
                  <strong>{event.to_status}</strong>
                </td>
                <td>{event.note || '—'}</td>
                <td>{event.changed_by}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}

export default function ReferralDashboard({ onNavigate }) {
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS })
  const [selectedRef, setSelectedRef] = useState(null)
  const [actionError, setActionError] = useState(null)

  const activeFilters = Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value)
  )
  const filterKey = JSON.stringify(activeFilters)

  const list = useAsync(() => api.listReferrals(activeFilters), [filterKey])
  const detail = useAsync(
    () => (selectedRef ? api.getReferral(selectedRef) : Promise.resolve(null)),
    [selectedRef]
  )

  const counts = list.data
    ? {
        urgency: Object.values(list.data.counts?.by_urgency || {}).reduce(
          (sum, n) => sum + n,
          0
        ),
        status: Object.values(list.data.counts?.by_status || {}).reduce(
          (sum, n) => sum + n,
          0
        ),
      }
    : null

  async function handleStatusChanged(updated) {
    setActionError(null)
    setSelectedRef(updated.referral_id)
    detail.reload()
    list.reload()
  }

  if (selectedRef) {
    return (
      <div className="dashboard">
        <div className="page-head">
          <h1>Referral record</h1>
        </div>
        {actionError ? (
          <p className="error form-error" role="alert">
            {actionError}
          </p>
        ) : null}
        {detail.loading ? (
          <p className="muted" role="status">
            Loading referral…
          </p>
        ) : detail.error ? (
          <div className="error-state" role="alert">
            <p>{detail.error}</p>
            <button type="button" className="btn btn-ghost" onClick={detail.reload}>
              Retry
            </button>
          </div>
        ) : detail.data ? (
          <ReferralDetail
            referral={detail.data}
            onBack={() => {
              setSelectedRef(null)
              setActionError(null)
            }}
            onChanged={handleStatusChanged}
            onError={setActionError}
          />
        ) : null}
      </div>
    )
  }

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Referral dashboard</h1>
          <p className="muted">
            Track every referral from pending through completed, with a full audit
            trail.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => onNavigate?.('assess')}
        >
          New assessment
        </button>
      </div>

      <FilterBar filters={filters} onChange={setFilters} counts={counts} />

      {list.loading ? (
        <p className="muted" role="status">
          Loading referrals…
        </p>
      ) : list.error ? (
        <div className="error-state" role="alert">
          <p>{list.error}</p>
          <button type="button" className="btn btn-ghost" onClick={list.reload}>
            Retry
          </button>
        </div>
      ) : list.data && list.data.referrals.length > 0 ? (
        <>
          <p className="muted fine-print">
            Showing {list.data.count} referral{list.data.count === 1 ? '' : 's'}
            {Object.keys(list.data.applied_filters).length
              ? ' (filtered)'
              : ''}
          </p>
          <div className="table-scroll">
            <table className="referral-table">
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Priority</th>
                  <th>Recommendation</th>
                  <th>Hospital</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {list.data.referrals.map((referral) => (
                  <tr key={referral.referral_id}>
                    <td data-label="Case">
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => setSelectedRef(referral.referral_id)}
                      >
                        {referral.referral_id}
                      </button>
                      <span className="muted fine-print cell-sub">
                        {referral.patient_id}
                      </span>
                    </td>
                    <td data-label="Priority">
                      <PriorityBadge
                        priority={referral.priority}
                        urgency={referral.urgency}
                      />
                    </td>
                    <td data-label="Recommendation">
                      {referral.recommendation.replace(/_/g, ' ')}
                    </td>
                    <td data-label="Hospital">
                      {referral.recommended_hospital_name || '—'}
                    </td>
                    <td data-label="Status">
                      <StatusBadge status={referral.status} />
                    </td>
                    <td data-label="Created" className="fine-print">
                      {referral.created_at}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost btn-small"
                        onClick={() => setSelectedRef(referral.referral_id)}
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="empty-state" role="status">
          <p>{list.data?.empty_state_message || 'No referrals recorded yet.'}</p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onNavigate?.('assess')}
          >
            Start an assessment
          </button>
        </div>
      )}
    </div>
  )
}
