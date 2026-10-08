// API service layer: every backend call goes through here.
// With VITE_API_BASE_URL empty (dev), requests hit the Vite /api proxy.

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, fields = {}) {
    super(message)
    this.name = 'ApiError'
    this.fields = fields // { 'vitals.heart_rate': 'message', ... } for 422s
  }
}

// Map FastAPI validation paths to form field names used by AssessmentForm.
const FIELD_ALIASES = {
  patient_id: 'patientId',
  age_years: 'age',
  chief_complaint: 'chiefComplaint',
  clinical_findings: 'clinicalFindings',
  illness_details: 'illnessDetails',
  known_specialty: 'knownSpecialty',
  emergency_indicator: 'emergencyIndicator',
  'vitals.heart_rate': 'heartRate',
  'vitals.systolic_bp': 'systolicBp',
  'vitals.diastolic_bp': 'diastolicBp',
  'vitals.respiratory_rate': 'respiratoryRate',
  'vitals.oxygen_saturation': 'oxygenSaturation',
  'vitals.temperature_c': 'temperatureC',
}

function fieldsFromDetail(detail) {
  const fields = {}
  if (!Array.isArray(detail)) return fields
  for (const item of detail) {
    const path = Array.isArray(item?.loc) ? item.loc.slice(1).join('.') : ''
    const key = FIELD_ALIASES[path] || path
    if (key && !fields[key]) fields[key] = item.msg
  }
  return fields
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    })
  } catch {
    // fetch itself failed: backend down, proxy missing, network offline.
    throw new ApiError(
      `Cannot reach the backend for ${path}. Check that the API server is running, then retry.`
    )
  }

  if (response.status === 204) return null

  let body = null
  try {
    body = await response.json()
  } catch {
    // Non-JSON response (e.g. proxy error page) — fall through to the status error.
  }

  if (!response.ok) {
    const detail = body?.detail
    const fields = fieldsFromDetail(detail)
    let message
    if (Object.keys(fields).length > 0) {
      message = 'Please correct the highlighted fields.'
    } else if (typeof detail === 'string') {
      message = detail
    } else if (response.status >= 500) {
      message = 'The server encountered a problem handling this request. Please retry; if it persists, check the API logs.'
    } else {
      message = `Request failed with status ${response.status}`
    }
    throw new ApiError(message, fields)
  }

  return body
}

export const api = {
  health: () => request('/api/health'),
  assess: (assessment) =>
    request('/api/assessments', { method: 'POST', body: JSON.stringify(assessment) }),
  listAssessments: (limit = 50) => request(`/api/assessments?limit=${limit}`),
  getAssessment: (id) => request(`/api/assessments/${id}`),
  score: (input, rules) =>
    request('/api/rules/score', {
      method: 'POST',
      body: JSON.stringify(rules ? { input, rules } : { input }),
    }),
  mapsConfig: () => request('/api/maps/config'),
  route: (origin, destination, profile) =>
    request('/api/route', {
      method: 'POST',
      body: JSON.stringify({ origin, destination, ...(profile ? { profile } : {}) }),
    }),
  listLocations: () => request('/api/locations'),
  // Clinic resources + hospital matching (Prompt 2)
  listHospitals: () => request('/api/hospitals'),
  getClinic: () => request('/api/clinics/current'),
  updateClinic: (patch) =>
    request('/api/clinics/current', { method: 'PATCH', body: JSON.stringify(patch) }),
  resetClinic: () => request('/api/clinics/current', { method: 'DELETE' }),
  matchHospitals: (body) =>
    request('/api/referrals/match', { method: 'POST', body: JSON.stringify(body) }),
  // Referral records + dashboard (Prompt 4)
  createReferral: (body) =>
    request('/api/referrals', { method: 'POST', body: JSON.stringify(body) }),
  listReferrals: (filters = {}) => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) {
      if (value) params.set(key, value)
    }
    const qs = params.toString()
    return request(`/api/referrals${qs ? `?${qs}` : ''}`)
  },
  getReferral: (ref) => request(`/api/referrals/${encodeURIComponent(ref)}`),
  updateReferralStatus: (ref, body) =>
    request(`/api/referrals/${encodeURIComponent(ref)}/status`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  referralSummaryText: (ref) =>
    request(`/api/referrals/${encodeURIComponent(ref)}/summary.txt`),
  // Rural Diagnostic Risk & Context Knowledge (Prompt 8)
  listKnowledgeConditions: () => request('/api/knowledge/conditions'),
  getKnowledgeCondition: (id) => request(`/api/knowledge/conditions/${id}`),
  listSystemicDrivers: () => request('/api/knowledge/systemic-drivers'),
  listInjuryRisks: () => request('/api/knowledge/injury-risks'),
  getKnowledgeMetadata: () => request('/api/knowledge/metadata'),
  getKnowledgeReviewQueue: () => request('/api/knowledge/review-queue'),
}
