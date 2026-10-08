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
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })

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
  listLocations: () => request('/api/locations'),
}
