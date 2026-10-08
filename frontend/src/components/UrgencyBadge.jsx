const TONE = { GREEN: 'green', ORANGE: 'orange', RED: 'red' }

export default function UrgencyBadge({ level, label, size = 'md' }) {
  return (
    <span className={`urgency-badge tone-${TONE[level] || 'green'} size-${size}`}>
      {level}
      {label ? <span className="urgency-label"> · {label}</span> : null}
    </span>
  )
}
