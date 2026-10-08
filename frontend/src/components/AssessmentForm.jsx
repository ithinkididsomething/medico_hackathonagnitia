import { useState } from 'react'
import { ApiError, api } from '../lib/api.js'
import { Field, SelectField, TextArea, TextInput } from './ui.jsx'

const EMPTY = {
  patientId: '',
  age: '',
  sex: '',
  chiefComplaint: '',
  heartRate: '',
  systolicBp: '',
  diastolicBp: '',
  respiratoryRate: '',
  oxygenSaturation: '',
  temperatureC: '',
  clinicalFindings: '',
  illnessDetails: '',
  knownSpecialty: '',
  emergencyIndicator: false,
}

const NUMERIC_FIELDS = {
  heartRate: { label: 'Heart rate', min: 20, max: 300, unit: 'bpm' },
  systolicBp: { label: 'Systolic blood pressure', min: 40, max: 300, unit: 'mmHg' },
  diastolicBp: { label: 'Diastolic blood pressure', min: 20, max: 200, unit: 'mmHg' },
  respiratoryRate: { label: 'Respiratory rate', min: 4, max: 80, unit: 'breaths/min' },
  oxygenSaturation: { label: 'Oxygen saturation', min: 50, max: 100, unit: '%' },
  temperatureC: { label: 'Temperature', min: 30, max: 45, unit: '°C' },
}

const SEX_OPTIONS = [
  { value: 'female', label: 'Female' },
  { value: 'male', label: 'Male' },
  { value: 'other', label: 'Other' },
  { value: 'unknown', label: 'Unknown' },
]

const SPECIALTY_OPTIONS = [
  { value: 'internal_medicine', label: 'Internal medicine' },
  { value: 'cardiology', label: 'Cardiology' },
  { value: 'surgery', label: 'Surgery' },
  { value: 'orthopedics', label: 'Orthopedics' },
  { value: 'pediatrics', label: 'Pediatrics' },
  { value: 'obstetrics_gynaecology', label: 'Obstetrics & gynaecology' },
  { value: 'neurology', label: 'Neurology' },
  { value: 'emergency_medicine', label: 'Emergency medicine' },
  { value: 'other', label: 'Other' },
]

function validate(values) {
  const errors = {}

  const patientId = values.patientId.trim()
  if (!patientId) {
    errors.patientId = 'Patient ID is required.'
  } else if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(patientId) || patientId.length > 40) {
    errors.patientId = 'Use up to 40 letters, numbers, dots, dashes or underscores (no spaces).'
  }

  const age = values.age.trim()
  if (!age) {
    errors.age = 'Age is required.'
  } else if (!/^\d+$/.test(age)) {
    errors.age = 'Age must be a whole number of years.'
  } else if (Number(age) > 120) {
    errors.age = 'Age must be between 0 and 120 years.'
  }

  if (!values.sex) errors.sex = 'Sex is required.'

  const complaint = values.chiefComplaint.trim()
  if (!complaint) {
    errors.chiefComplaint = 'Main symptoms/complaint is required.'
  } else if (complaint.length < 3) {
    errors.chiefComplaint = 'Describe the main complaint in at least 3 characters.'
  }

  for (const [key, rule] of Object.entries(NUMERIC_FIELDS)) {
    const raw = String(values[key]).trim()
    if (raw === '') {
      errors[key] = `${rule.label} is required.`
      continue
    }
    const number = Number(raw)
    if (Number.isNaN(number)) {
      errors[key] = `${rule.label} must be a number.`
    } else if (number < rule.min || number > rule.max) {
      errors[key] = `${rule.label} must be between ${rule.min} and ${rule.max} ${rule.unit}.`
    }
  }

  const systolic = Number(values.systolicBp)
  const diastolic = Number(values.diastolicBp)
  if (
    !errors.systolicBp &&
    !errors.diastolicBp &&
    Number.isFinite(systolic) &&
    Number.isFinite(diastolic) &&
    systolic < diastolic
  ) {
    errors.systolicBp = 'Systolic must not be lower than diastolic.'
  }

  return errors
}

function toPayload(values) {
  return {
    patient_id: values.patientId.trim(),
    age_years: Number(values.age),
    sex: values.sex,
    chief_complaint: values.chiefComplaint.trim(),
    vitals: {
      heart_rate: Number(values.heartRate),
      systolic_bp: Number(values.systolicBp),
      diastolic_bp: Number(values.diastolicBp),
      respiratory_rate: Number(values.respiratoryRate),
      oxygen_saturation: Number(values.oxygenSaturation),
      temperature_c: Number(values.temperatureC),
    },
    clinical_findings: values.clinicalFindings.trim() || null,
    illness_details: values.illnessDetails.trim() || null,
    known_specialty: values.knownSpecialty || null,
    emergency_indicator: values.emergencyIndicator,
  }
}

export default function AssessmentForm({ onResult }) {
  const [values, setValues] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [busy, setBusy] = useState(false)

  function setValue(key, value) {
    setValues((current) => ({ ...current, [key]: value }))
    setErrors((current) => {
      if (!current[key]) return current
      const next = { ...current }
      delete next[key]
      return next
    })
    setFormError(null)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const found = validate(values)
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length > 0) return

    setBusy(true)
    try {
      const result = await api.assess(toPayload(values))
      onResult(result)
    } catch (error) {
      if (error instanceof ApiError && Object.keys(error.fields).length > 0) {
        setErrors((current) => ({ ...current, ...error.fields }))
      } else {
        setFormError(error.message || 'Assessment could not be submitted.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card assessment-form" onSubmit={handleSubmit} noValidate>
      <header className="card-header">
        <h1>Patient assessment</h1>
        <span className="muted">Synthetic / demo data only — no names or contact details</span>
      </header>

      <section className="form-section">
        <h2>Patient</h2>
        <div className="form-grid">
          <Field label="Patient ID" required htmlFor="patientId" error={errors.patientId}
                 hint="Clinic-assigned identifier">
            <TextInput id="patientId" value={values.patientId} onChange={(v) => setValue('patientId', v)} placeholder="e.g. SYN-001" />
          </Field>
          <Field label="Age (years)" required htmlFor="age" error={errors.age}>
            <TextInput id="age" type="number" inputMode="numeric" min="0" max="120"
                       value={values.age} onChange={(v) => setValue('age', v)} placeholder="e.g. 45" />
          </Field>
          <Field label="Sex" required htmlFor="sex" error={errors.sex}>
            <SelectField id="sex" value={values.sex} onChange={(v) => setValue('sex', v)}
                         options={SEX_OPTIONS} placeholder="Select…" />
          </Field>
        </div>
      </section>

      <section className="form-section">
        <h2>Main symptoms / complaint</h2>
        <Field label="Describe the presenting complaint" required htmlFor="chiefComplaint"
               error={errors.chiefComplaint}>
          <TextArea id="chiefComplaint" rows={3} value={values.chiefComplaint}
                    onChange={(v) => setValue('chiefComplaint', v)}
                    placeholder="e.g. productive cough and fever for 3 days" />
        </Field>
      </section>

      <section className="form-section">
        <h2>Vital signs</h2>
        <div className="form-grid vitals-grid">
          <Field label="Heart rate (bpm)" required htmlFor="heartRate" error={errors.heartRate}>
            <TextInput id="heartRate" type="number" inputMode="numeric" value={values.heartRate}
                       onChange={(v) => setValue('heartRate', v)} placeholder="e.g. 78" />
          </Field>
          <Field label="Systolic BP (mmHg)" required htmlFor="systolicBp" error={errors.systolicBp}>
            <TextInput id="systolicBp" type="number" inputMode="numeric" value={values.systolicBp}
                       onChange={(v) => setValue('systolicBp', v)} placeholder="e.g. 120" />
          </Field>
          <Field label="Diastolic BP (mmHg)" required htmlFor="diastolicBp" error={errors.diastolicBp}>
            <TextInput id="diastolicBp" type="number" inputMode="numeric" value={values.diastolicBp}
                       onChange={(v) => setValue('diastolicBp', v)} placeholder="e.g. 80" />
          </Field>
          <Field label="Respiratory rate" required htmlFor="respiratoryRate" error={errors.respiratoryRate}>
            <TextInput id="respiratoryRate" type="number" inputMode="numeric" value={values.respiratoryRate}
                       onChange={(v) => setValue('respiratoryRate', v)} placeholder="e.g. 16" />
          </Field>
          <Field label="Oxygen saturation (%)" required htmlFor="oxygenSaturation" error={errors.oxygenSaturation}>
            <TextInput id="oxygenSaturation" type="number" inputMode="decimal" value={values.oxygenSaturation}
                       onChange={(v) => setValue('oxygenSaturation', v)} placeholder="e.g. 98" />
          </Field>
          <Field label="Temperature (°C)" required htmlFor="temperatureC" error={errors.temperatureC}>
            <TextInput id="temperatureC" type="number" inputMode="decimal" value={values.temperatureC}
                       onChange={(v) => setValue('temperatureC', v)} placeholder="e.g. 37.0" />
          </Field>
        </div>
      </section>

      <section className="form-section">
        <h2>Clinical details</h2>
        <Field label="Relevant clinical findings" htmlFor="clinicalFindings" error={errors.clinicalFindings}>
          <TextArea id="clinicalFindings" value={values.clinicalFindings}
                    onChange={(v) => setValue('clinicalFindings', v)}
                    placeholder="e.g. chest auscultation findings, level of consciousness" />
        </Field>
        <Field label="Injury / illness details" htmlFor="illnessDetails" error={errors.illnessDetails}>
          <TextArea id="illnessDetails" value={values.illnessDetails}
                    onChange={(v) => setValue('illnessDetails', v)}
                    placeholder="e.g. history, onset, suspected injury" />
        </Field>
        <div className="form-grid">
          <Field label="Known required specialty (if any)" htmlFor="knownSpecialty" error={errors.knownSpecialty}>
            <SelectField id="knownSpecialty" value={values.knownSpecialty}
                         onChange={(v) => setValue('knownSpecialty', v)}
                         options={SPECIALTY_OPTIONS} placeholder="Not known" />
          </Field>
        </div>
        <label className="checkbox emergency-check">
          <input
            type="checkbox"
            checked={values.emergencyIndicator}
            onChange={(event) => setValue('emergencyIndicator', event.target.checked)}
          />
          <span>
            <strong>Explicit emergency indicator</strong> (e.g. unresponsive, collapsed, severe
            distress) — demonstration field
          </span>
        </label>
      </section>

      {formError ? <p className="error form-error" role="alert">{formError}</p> : null}

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Assessing…' : 'Run assessment'}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => { setValues(EMPTY); setErrors({}); setFormError(null) }}
          disabled={busy}
        >
          Clear form
        </button>
      </div>

      <p className="muted fine-print">
        Decision-support prototype. Output must be reviewed by a qualified healthcare
        professional. Rules are demonstration-only and not clinically validated.
      </p>
    </form>
  )
}
