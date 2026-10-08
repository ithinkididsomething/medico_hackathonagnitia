import { useState, useEffect } from 'react'
import { api } from '../lib/api.js'

export default function KnowledgeReference() {
  const [activeTab, setActiveTab] = useState('conditions')
  const [conditions, setConditions] = useState([])
  const [drivers, setDrivers] = useState([])
  const [injuryRisks, setInjuryRisks] = useState([])
  const [reviewQueue, setReviewQueue] = useState([])
  const [metadata, setMetadata] = useState(null)
  
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  const [expandedCondition, setExpandedCondition] = useState(null)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      setError(null)
      try {
        const [condsRes, driversRes, risksRes, queueRes, metaRes] = await Promise.all([
          api.listKnowledgeConditions(),
          api.listSystemicDrivers(),
          api.listInjuryRisks(),
          api.getKnowledgeReviewQueue(),
          api.getKnowledgeMetadata()
        ])
        setConditions(condsRes.conditions || [])
        setDrivers(driversRes.systemic_drivers || [])
        setInjuryRisks(risksRes.injury_risks || [])
        setReviewQueue(queueRes.review_queue || [])
        setMetadata(metaRes.metadata || null)
      } catch (err) {
        setError(err.message || 'Failed to load clinical reference data.')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="card loading-state" style={{ padding: '2rem', textAlign: 'center' }}>
        <p className="muted">Loading clinical and diagnostic reference dataset…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card error-state" style={{ padding: '2rem', textAlign: 'center' }}>
        <p className="error" role="alert">{error}</p>
      </div>
    )
  }

  return (
    <div className="knowledge-reference">
      {/* Overview Stats Header */}
      {metadata ? (
        <section className="card stats-header" style={{ marginBottom: '1.5rem', backgroundColor: '#f8fafc' }}>
          <header className="card-header">
            <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#1e293b' }}>Clinical Knowledge &amp; Diagnostic Risks</h1>
            <span className="badge badge-primary">v{metadata.version}</span>
          </header>
          <p className="muted" style={{ margin: '0.5rem 0 1rem 0', fontSize: '0.875rem' }}>
            Authoritative, evidence-tagged reference registry for rural clinicians.
            Provides clinical context regarding systemic constraints, diagnostic overlaps (mimics), and injury risks.
          </p>
          <div className="summary-chips" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
            <span className="chip" style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0' }}>
              <strong>Conditions</strong> {metadata.condition_count}
            </span>
            <span className="chip" style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0' }}>
              <strong>Confusion Overlaps</strong> {metadata.diagnostic_confusion_relationship_count}
            </span>
            <span className="chip" style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0' }}>
              <strong>Systemic Drivers</strong> {metadata.systemic_driver_count}
            </span>
            <span className="chip" style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0' }}>
              <strong>Injury Risks</strong> {metadata.injury_risk_relationship_count}
            </span>
            <span className="chip" style={{ backgroundColor: '#fef2f2', border: '1px solid #fee2e2', color: '#991b1b' }}>
              <strong>Unresolved / In Review</strong> {metadata.claims_requiring_review}
            </span>
          </div>
        </section>
      ) : null}

      {/* Tabs Selector */}
      <div className="main-nav" style={{ marginBottom: '1.5rem', borderBottom: '1px solid #e2e8f0', display: 'flex', gap: '0.5rem' }}>
        <button
          type="button"
          className={`nav-tab${activeTab === 'conditions' ? ' is-active' : ''}`}
          onClick={() => setActiveTab('conditions')}
        >
          Conditions &amp; Mimics
        </button>
        <button
          type="button"
          className={`nav-tab${activeTab === 'drivers' ? ' is-active' : ''}`}
          onClick={() => setActiveTab('drivers')}
        >
          Systemic Constraints ({drivers.length})
        </button>
        <button
          type="button"
          className={`nav-tab${activeTab === 'injuryRisks' ? ' is-active' : ''}`}
          onClick={() => setActiveTab('injuryRisks')}
        >
          Injury Risks ({injuryRisks.length})
        </button>
        <button
          type="button"
          className={`nav-tab${activeTab === 'reviewQueue' ? ' is-active' : ''}`}
          onClick={() => setActiveTab('reviewQueue')}
          style={{ position: 'relative' }}
        >
          Review Queue ({reviewQueue.length})
          {reviewQueue.length > 0 ? (
            <span style={{ position: 'absolute', top: '-4px', right: '-4px', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ef4444' }} />
          ) : null}
        </button>
      </div>

      {/* Content Rendering ---------------------------------------------------- */}

      {/* TABS 1: CONDITIONS */}
      {activeTab === 'conditions' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '1.5rem' }}>
          {/* Conditions List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {conditions.map((cond) => (
              <button
                key={cond.condition_id}
                type="button"
                className="card"
                onClick={() => setExpandedCondition(cond)}
                style={{
                  textAlign: 'left',
                  cursor: 'pointer',
                  padding: '1rem',
                  border: expandedCondition?.condition_id === cond.condition_id ? '2px solid var(--color-primary, #0d9488)' : '1px solid #e2e8f0',
                  backgroundColor: expandedCondition?.condition_id === cond.condition_id ? '#f0fdfa' : '#fff',
                  transition: 'all 0.15s ease'
                }}
              >
                <strong style={{ display: 'block', fontSize: '0.95rem' }}>{cond.canonical_name}</strong>
                <span className="muted fine-print">{cond.category.replace(/_/g, ' ')}</span>
              </button>
            ))}
          </div>

          {/* Condition Detail */}
          <div>
            {expandedCondition ? (
              <section className="card" style={{ padding: '1.5rem' }}>
                <header className="card-header" style={{ marginBottom: '1rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem' }}>
                  <h2 style={{ margin: 0 }}>{expandedCondition.canonical_name}</h2>
                  <span className="badge quiet">{expandedCondition.condition_id}</span>
                </header>

                <p style={{ fontSize: '0.95rem', lineHeight: '1.5', marginBottom: '1rem' }}>
                  {expandedCondition.description}
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                  <div>
                    <h3 className="subhead">Typical Symptoms</h3>
                    <ul className="reason-list fine-print">
                      {expandedCondition.symptoms.map((s, idx) => <li key={idx}>{s}</li>)}
                    </ul>
                  </div>
                  <div>
                    <h3 className="subhead">Required Resources</h3>
                    <div className="summary-chips" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                      {(expandedCondition.rural_context?.resource_dependencies || []).map((dep, idx) => (
                        <span key={idx} className="chip quiet">{dep}</span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Overlaps / Mimics Section */}
                <h3 className="subhead" style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1rem', marginTop: '1rem' }}>
                  Diagnostic Overlaps &amp; Mimics
                </h3>
                {expandedCondition.diagnostic_confusion?.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.5rem' }}>
                    {expandedCondition.diagnostic_confusion.map((conf, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '1rem',
                          border: '1px solid #e2e8f0',
                          borderRadius: '6px',
                          backgroundColor: '#f8fafc'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                          <strong style={{ fontSize: '1rem', color: '#1e293b' }}>
                            {conf.confused_with_name}
                          </strong>
                          {conf.unresolved_condition_reference ? (
                            <span
                              className="badge"
                              style={{
                                backgroundColor: '#fef2f2',
                                color: '#991b1b',
                                border: '1px solid #fee2e2',
                                fontSize: '0.75rem',
                                padding: '0.1rem 0.4rem'
                              }}
                            >
                              Requires Review
                            </span>
                          ) : (
                            <span
                              className="badge"
                              style={{
                                backgroundColor: '#f0fdfa',
                                color: '#115e59',
                                border: '1px solid #ccfbf1',
                                fontSize: '0.75rem',
                                padding: '0.1rem 0.4rem'
                              }}
                            >
                              Documented relationship
                            </span>
                          )}
                        </div>

                        <p style={{ fontSize: '0.875rem', margin: '0 0 0.5rem 0', color: '#475569' }}>
                          <strong>Why confusion occurs:</strong> {conf.why_confusion_can_occur}
                        </p>

                        <div style={{ marginBottom: '0.5rem' }}>
                          <span style={{ fontSize: '0.8rem', fontWeight: 'bold', display: 'block', textTransform: 'uppercase', color: '#64748b' }}>
                            Distinguishing Information
                          </span>
                          <ul className="reason-list fine-print" style={{ margin: '0.2rem 0' }}>
                            {(conf.distinguishing_information || []).map((info, i) => (
                              <li key={i}>{info}</li>
                            ))}
                          </ul>
                        </div>

                        {conf.source_refs?.length > 0 ? (
                          <div style={{ fontSize: '0.75rem', borderTop: '1px dashed #e2e8f0', paddingTop: '0.4rem', color: '#64748b' }}>
                            <strong>Evidence Status:</strong> {conf.evidence_status?.replace(/_/g, ' ')} · 
                            <strong> Source:</strong> {conf.source_refs.map(s => s.source_name).join(', ')}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="muted fine-print">No specific mimics documented in the knowledge repository.</p>
                )}

                {/* Cultural somatics (e.g. Depression "taaqat ki kami") */}
                {expandedCondition.rural_context?.cultural_context ? (
                  <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#fffbeb', borderLeft: '4px solid #d97706', borderRadius: '4px' }}>
                    <h4 style={{ margin: '0 0 0.25rem 0', color: '#92400e', fontSize: '0.9rem' }}>
                      Cultural Somatic Presentation Notes
                    </h4>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#78350f' }}>
                      <strong>Phrases:</strong> {(expandedCondition.rural_context.cultural_context.somatic_phrases || []).join(', ')}
                      <br />
                      <strong>Notes:</strong> {expandedCondition.rural_context.cultural_context.notes}
                    </p>
                  </div>
                ) : null}

                {/* Sources list */}
                {expandedCondition.sources?.length > 0 ? (
                  <div style={{ marginTop: '1.5rem', borderTop: '1px dashed #cbd5e1', paddingTop: '0.75rem', fontSize: '0.75rem' }}>
                    <strong>Sources/Provenance:</strong>
                    <ul style={{ margin: '0.25rem 0 0 0', paddingLeft: '1rem', color: '#64748b' }}>
                      {expandedCondition.sources.map((src, idx) => (
                        <li key={idx}>
                          {src.source_name} ({src.source_type}) {src.source_url ? <a href={src.source_url} target="_blank" rel="noreferrer" style={{ textDecoration: 'underline' }}>View</a> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </section>
            ) : (
              <div className="card" style={{ padding: '3rem', textAlign: 'center', backgroundColor: '#f8fafc', border: '2px dashed #cbd5e1' }}>
                <p className="muted">Select a condition from the left list to explore clinical mimics, resource dependencies, and evidence provenance.</p>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* TABS 2: SYSTEMIC DRIVERS */}
      {activeTab === 'drivers' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {drivers.map((driver) => (
            <section key={driver.driver_id} className="card" style={{ padding: '1.5rem' }}>
              <header className="card-header" style={{ marginBottom: '0.5rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#1e293b' }}>
                  {driver.driver_id} · {driver.name}
                </h3>
                <span className="badge" style={{ backgroundColor: '#f1f5f9', color: '#475569' }}>
                  {driver.evidence_status?.replace(/_/g, ' ')}
                </span>
              </header>

              <p style={{ fontSize: '0.95rem', margin: '0 0 1rem 0' }}>{driver.description}</p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', borderTop: '1px solid #edf2f7', paddingTop: '1rem' }}>
                <div>
                  <h4 className="subhead" style={{ fontSize: '0.85rem' }}>Diagnostic Impacts &amp; Examples</h4>
                  {driver.diagnostic_impacts?.map((di, idx) => (
                    <div key={idx} style={{ marginBottom: '0.5rem' }}>
                      <strong style={{ fontSize: '0.85rem', display: 'block', color: '#334155' }}>
                        {di.impact}
                      </strong>
                      <ul className="reason-list fine-print" style={{ marginTop: '0.2rem' }}>
                        {(di.examples || []).map((ex, i) => <li key={i}>{ex}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>

                <div>
                  <h4 className="subhead" style={{ fontSize: '0.85rem' }}>Affected Capabilities &amp; Referrals</h4>
                  <div style={{ marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', display: 'block', color: '#64748b' }}>
                      Capabilities Affected:
                    </span>
                    <div className="summary-chips" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.2rem' }}>
                      {(driver.affected_capabilities || []).map((cap, i) => (
                        <span key={i} className="chip quiet">{cap}</span>
                      ))}
                    </div>
                  </div>

                  <div style={{ marginTop: '0.75rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', display: 'block', color: '#64748b' }}>
                      Referral Implications:
                    </span>
                    <ul className="reason-list fine-print" style={{ marginTop: '0.2rem' }}>
                      {(driver.referral_implications || []).map((ri, i) => <li key={i}>{ri}</li>)}
                    </ul>
                  </div>
                </div>
              </div>

              {driver.source_refs?.length > 0 ? (
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '1rem', borderTop: '1px dashed #cbd5e1', paddingTop: '0.4rem' }}>
                  <strong>Source:</strong> {driver.source_refs.map(s => s.source_name).join(', ')}
                </div>
              ) : null}
            </section>
          ))}
        </div>
      ) : null}

      {/* TABS 3: INJURY RISKS */}
      {activeTab === 'injuryRisks' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {injuryRisks.map((risk) => (
            <section key={risk.risk_id} className="card" style={{ padding: '1.5rem' }}>
              <header className="card-header" style={{ marginBottom: '0.5rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#1e293b' }}>
                  {risk.risk_id} · {risk.canonical_name}
                </h3>
                <span className="badge badge-primary">{risk.injury_type}</span>
              </header>

              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.5rem' }}>
                <div>
                  <h4 className="subhead" style={{ fontSize: '0.85rem' }}>Clinical Challenge</h4>
                  <p style={{ fontSize: '0.875rem', color: '#475569', margin: '0 0 1rem 0', lineHeight: '1.5' }}>
                    {risk.why_difficult_clinically}
                  </p>

                  <h4 className="subhead" style={{ fontSize: '0.85rem' }}>Diagnostic Guidance</h4>
                  <p style={{ fontSize: '0.875rem', color: '#475569', margin: '0 0 1rem 0', lineHeight: '1.5' }}>
                    {risk.imaging_or_diagnostic_relevance}
                  </p>
                </div>

                <div style={{ backgroundColor: '#f8fafc', padding: '1rem', borderRadius: '6px' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 'bold', display: 'block', color: '#64748b' }}>
                    Possible Confusion Targets (Mimics):
                  </span>
                  <div className="summary-chips" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', margin: '0.4rem 0 1rem 0' }}>
                    {(risk.possible_confusion_targets || []).map((t, idx) => (
                      <span key={idx} className="chip" style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0' }}>{t}</span>
                    ))}
                  </div>

                  <span style={{ fontSize: '0.75rem', fontWeight: 'bold', display: 'block', color: '#64748b' }}>
                    Worsening Indicators / Warning signs:
                  </span>
                  <p style={{ fontSize: '0.85rem', color: '#b91c1c', margin: '0.2rem 0 1rem 0', fontWeight: '500' }}>
                    {risk.persistence_or_worsening_warning}
                  </p>

                  <span style={{ fontSize: '0.75rem', fontWeight: 'bold', display: 'block', color: '#64748b' }}>
                    Referral &amp; Urgency Recommendation:
                  </span>
                  <p style={{ fontSize: '0.85rem', color: '#1e293b', margin: '0.2rem 0 0 0', fontWeight: '500' }}>
                    {risk.referral_urgency_relevance}
                  </p>
                </div>
              </div>

              {risk.source_refs?.length > 0 ? (
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '1rem', borderTop: '1px dashed #cbd5e1', paddingTop: '0.4rem' }}>
                  <strong>Authoritative Source:</strong> {risk.source_refs.map(s => s.source_name).join(', ')} ({risk.evidence_status?.replace(/_/g, ' ')})
                </div>
              ) : null}
            </section>
          ))}
        </div>
      ) : null}

      {/* TABS 4: REVIEW QUEUE */}
      {activeTab === 'reviewQueue' ? (
        <section className="card" style={{ padding: '1.5rem' }}>
          <header className="card-header" style={{ marginBottom: '1rem' }}>
            <h2 style={{ margin: 0 }}>Knowledge Review Queue</h2>
            <span className="badge badge-primary">{reviewQueue.length} items</span>
          </header>
          
          <p className="muted" style={{ fontSize: '0.875rem', marginBottom: '1.5rem' }}>
            Under Section 22 and Section 20 guidelines, claims that lack complete authoritative
            sources or refer to missing condition models are held in this queue. They are NOT shown
            to clinicians as established medical fact. Developers must resolve these condition ID
            references or provide validated literature sources.
          </p>

          {reviewQueue.length > 0 ? (
            <div className="table-wrapper">
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #cbd5e1', textAlign: 'left', color: '#475569' }}>
                    <th style={{ padding: '0.75rem' }}>Review ID</th>
                    <th style={{ padding: '0.75rem' }}>Category</th>
                    <th style={{ padding: '0.75rem' }}>Problematic Claim / Reference</th>
                    <th style={{ padding: '0.75rem' }}>Resolution Context</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewQueue.map((item, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid #edf2f7', verticalAlign: 'top' }}>
                      <td style={{ padding: '0.75rem', fontWeight: 'bold', color: '#ef4444' }}>{item.review_id}</td>
                      <td style={{ padding: '0.75rem' }}>
                        <span className="badge quiet">{item.type?.replace(/_/g, ' ')}</span>
                      </td>
                      <td style={{ padding: '0.75rem' }}>
                        <strong>{item.claim || `Unresolved Ref: ${item.target_id}`}</strong>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                          Origin Condition: {item.condition_id}
                        </div>
                      </td>
                      <td style={{ padding: '0.75rem', color: '#475569' }}>
                        {item.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '2rem', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px' }}>
              <p style={{ margin: 0, color: '#166534', fontWeight: 'bold' }}>Review queue is clean!</p>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#15803d' }}>All referenced conditions are resolved and validated.</p>
            </div>
          )}
        </section>
      ) : null}
    </div>
  )
}
