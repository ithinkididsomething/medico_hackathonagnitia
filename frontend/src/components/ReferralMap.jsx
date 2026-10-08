// Prompt 3 Part 7: referral map screen (OpenStreetMap via Leaflet).
// Shows the clinic, the recommended hospital, alternatives, excluded
// candidates, and the routed polyline to the recommended hospital.
// Clicking a marker reveals the hospital's capabilities + ranking info.

import { useEffect, useMemo, useState } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { api } from '../lib/api.js'

const DEFAULT_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const DEFAULT_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

// divIcon pins avoid bundler problems with Leaflet's default image markers.
function pinIcon(kind) {
  return L.divIcon({
    className: 'map-pin-wrap',
    html: `<div class="map-pin pin-${kind}"><span></span></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 22],
    popupAnchor: [0, -20],
  })
}

const ICONS = {
  clinic: pinIcon('clinic'),
  best: pinIcon('best'),
  alt: pinIcon('alt'),
  excluded: pinIcon('excluded'),
}

function FitBounds({ points }) {
  const map = useMap()
  useEffect(() => {
    if (!points || points.length === 0) return
    const bounds = L.latLngBounds(points.map((p) => [p.latitude, p.longitude]))
    map.fitBounds(bounds, { padding: [36, 36], maxZoom: 15 })
  }, [map, points])
  return null
}

function travelLine(travel) {
  const coords = travel?.route_coordinates
  if (!coords || coords.length < 2) return null
  return coords.map((c) => [c.latitude, c.longitude])
}

function travelSummary(travel) {
  if (!travel) return 'Travel estimate unavailable.'
  const minutes = travel.travel_minutes ?? travel.travel_minutes_placeholder
  const mins = minutes != null ? `~${Math.round(minutes)} min` : 'time unknown'
  const km = travel.distance_km != null ? `${travel.distance_km} km` : 'distance unknown'
  const routed = travel.source === 'osrm' ? 'road routing (OSRM)' : 'straight-line placeholder'
  return `${km}, ${mins} — ${routed}`
}

function HospitalPopup({ role, name, hospital, match }) {
  const specialty = hospital.specialties?.join(', ') || 'none listed'
  const diagnostics = hospital.diagnostics?.join(', ') || 'none listed'
  const treatments = hospital.treatment_capabilities?.join(', ') || 'none listed'
  return (
    <Popup>
      <div className="map-popup">
        <strong className={`map-popup-title role-${role}`}>{name}</strong>
        <div className="map-popup-role">
          {role === 'best' && 'Recommended hospital (best match)'}
          {role === 'alt' && `Alternative #${match?.rank ?? ''}`.trim()}
          {role === 'excluded' && 'Evaluated but excluded'}
          {role === 'clinic' && 'Current clinic (routing origin)'}
        </div>
        {role !== 'clinic' ? (
          <ul className="map-popup-list">
            {match?.total_score != null && (
              <li>Suitability score: <strong>{match.total_score}/100</strong></li>
            )}
            <li>Specialties: {specialty}</li>
            <li>Emergency: {hospital.emergency_capability} · ICU: {hospital.icu_capability}</li>
            <li>Capacity: {hospital.capacity_status} ({hospital.available_beds} beds), {hospital.availability_status}</li>
            <li>Diagnostics: {diagnostics}</li>
            <li>Treatments: {treatments}</li>
            {match?.travel && <li>Travel: {travelSummary(match.travel)}</li>}
          </ul>
        ) : null}
        {match?.why_not?.length ? (
          <div className="map-popup-why">
            <em>Why not:</em>
            <ul className="map-popup-list">
              {match.why_not.slice(0, 3).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {match?.reasons?.length ? (
          <div className="map-popup-why">
            <em>Why this hospital:</em>
            <ul className="map-popup-list">
              {match.reasons.slice(0, 3).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Popup>
  )
}

export default function ReferralMap({ match }) {
  const [config, setConfig] = useState(null)
  const [configError, setConfigError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .mapsConfig()
      .then((cfg) => {
        if (!cancelled) setConfig(cfg)
      })
      .catch((error) => {
        if (!cancelled) setConfigError(error.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const clinic = match?.clinic_location || null
  const best = match?.best_match || null
  const alternatives = match?.alternatives || []
  const excluded = match?.excluded || []

  const markers = useMemo(() => {
    const list = []
    if (clinic) {
      list.push({ key: 'clinic', kind: 'clinic', location: clinic, title: 'Clinic' })
    }
    const push = (entry, kind) => {
      const h = entry.hospital
      if (h.latitude == null || h.longitude == null) return
      list.push({
        key: `${kind}-${h.hospital_id}`,
        kind,
        location: { latitude: h.latitude, longitude: h.longitude },
        title: h.name,
        hospital: h,
        match: entry,
      })
    }
    if (best) push(best, 'best')
    alternatives.forEach((alt) => push(alt, 'alt'))
    excluded.forEach((entry) => push(entry, 'excluded'))
    return list
  }, [clinic, best, alternatives, excluded])

  const polyline = best ? travelLine(best.travel) : null
  const center = clinic || { latitude: 23.2599, longitude: 77.4126 }
  const boundPoints = useMemo(() => markers.map((m) => m.location), [markers])

  if (!match) return null

  return (
    <section className="card referral-map-card">
      <header className="card-header">
        <h3>Referral map</h3>
        <span className="muted fine-print">
          OpenStreetMap · capability-based ranking, not nearest-first
        </span>
      </header>

      {configError ? (
        <p className="muted fine-print">Map configuration unavailable: {configError}</p>
      ) : null}

      <div className="map-legend">
        <span className="legend-item"><span className="map-pin-demo pin-clinic" /> Clinic</span>
        <span className="legend-item"><span className="map-pin-demo pin-best" /> Recommended</span>
        <span className="legend-item"><span className="map-pin-demo pin-alt" /> Alternative</span>
        <span className="legend-item"><span className="map-pin-demo pin-excluded" /> Excluded</span>
      </div>

      <MapContainer
        className="referral-map"
        center={[center.latitude, center.longitude]}
        zoom={12}
        scrollWheelZoom
      >
        <TileLayer
          url={config?.tile_url || DEFAULT_TILE_URL}
          attribution={config?.attribution || DEFAULT_ATTRIBUTION}
        />
        <FitBounds points={boundPoints} />

        {markers.map((marker) => (
          <Marker
            key={marker.key}
            position={[marker.location.latitude, marker.location.longitude]}
            icon={ICONS[marker.kind]}
          >
            {marker.kind === 'clinic' ? (
              <Popup>
                <div className="map-popup">
                  <strong className="map-popup-title role-clinic">Clinic</strong>
                  <div className="map-popup-role">Routing origin — configurable demo location</div>
                </div>
              </Popup>
            ) : (
              <HospitalPopup
                role={marker.kind}
                name={marker.hospital.name}
                hospital={marker.hospital}
                match={{
                  ...marker.match,
                  rank:
                    marker.kind === 'alt'
                      ? alternatives.findIndex(
                          (a) => a.hospital.hospital_id === marker.hospital.hospital_id
                        ) + 2
                      : undefined,
                }}
              />
            )}
          </Marker>
        ))}

        {polyline ? (
          <Polyline
            positions={polyline}
            pathOptions={{ color: '#b91c1c', weight: 4, opacity: 0.85 }}
          />
        ) : null}
      </MapContainer>

      {best?.travel ? (
        <p className="muted fine-print map-travel-line">
          Route to <strong>{best.hospital.name}</strong>: {travelSummary(best.travel)}.
          {best.travel.note ? ` ${best.travel.note}` : ''}
        </p>
      ) : (
        <p className="muted fine-print map-travel-line">
          No route to display yet — travel estimates appear when routing is available.
        </p>
      )}
      {config?.routing_enabled === false ? (
        <p className="muted fine-print">Live road routing is currently disabled on the server.</p>
      ) : null}
    </section>
  )
}
