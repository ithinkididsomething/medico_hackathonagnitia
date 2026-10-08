// Small reusable form primitives shared by the assessment screens.

export function Field({ label, required, hint, error, htmlFor, children }) {
  return (
    <div className={`field ${error ? 'has-error' : ''}`}>
      <label htmlFor={htmlFor}>
        {label}
        {required ? <span className="req" aria-hidden="true"> *</span> : null}
      </label>
      {children}
      {hint && !error ? <span className="hint">{hint}</span> : null}
      {error ? <span className="error-text" role="alert">{error}</span> : null}
    </div>
  )
}

export function TextInput({ id, value, onChange, placeholder, type = 'text', inputMode, step, min, max }) {
  return (
    <input
      id={id}
      name={id}
      type={type}
      inputMode={inputMode}
      step={step}
      min={min}
      max={max}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

export function TextArea({ id, value, onChange, placeholder, rows = 3 }) {
  return (
    <textarea
      id={id}
      name={id}
      rows={rows}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

export function SelectField({ id, value, onChange, options, placeholder }) {
  return (
    <select id={id} name={id} value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">{placeholder}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}
