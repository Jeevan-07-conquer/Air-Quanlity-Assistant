import { escapeHtml } from "../state.js";

export function formatMetric(value) {
  if (value === null || value === undefined) return "Unavailable";
  return Number.isInteger(value) ? String(value) : String(value);
}

export function describeAqi(aqi) {
  if (aqi === null || aqi === undefined) {
    return { band: "Unavailable", hint: "Waiting for a verified station reading." };
  }
  if (aqi <= 50) return { band: "Clean Air", hint: "Good air — normal outdoor activities are fine." };
  if (aqi <= 100) return { band: "Moderate Haze", hint: "Acceptable air — sensitive people should watch for symptoms." };
  if (aqi <= 150) return { band: "Poor for Sensitive Groups", hint: "Children, seniors, and sensitive lungs should cut back long outdoor effort." };
  if (aqi <= 200) return { band: "Unhealthy Air", hint: "Everyone may feel irritation — limit outdoor exertion and keep windows shut." };
  if (aqi <= 300) return { band: "Very Unhealthy Smog", hint: "Heavy smog — shift workouts indoors and protect vulnerable family members." };
  return { band: "Severe Winter Smog", hint: "Hazardous air — avoid outdoor exertion and stay in filtered indoor air." };
}

export function formatRiskLabel(risk) {
  const labels = {
    low: "Low Risk",
    moderate: "Moderate Risk",
    high: "Elevated Risk",
    very_high: "High Risk",
    severe: "Severe Risk",
    unknown: "Unverified",
  };
  return labels[risk] || "Unknown";
}

const LOCATION_PIN_SVG =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:-2px;"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>';

/**
 * Right-hand Weather-style Hero AQI Card + Quick City Switcher (Image 1 right column).
 */
export function renderWeatherSidebarCard(telemetry, policy, cities, selectedCityId, { onRefresh, isRefreshing = false } = {}) {
  const m = telemetry?.measurements || {};
  const f = telemetry?.freshness || {};
  const st = telemetry?.station || {};
  const loc = telemetry?.location || {};
  const s = telemetry?.source || {};
  const aqiDesc = describeAqi(m.aqi);
  const risk = policy?.riskCategory || "unknown";

  const freshnessBadgeClass = `badge-${f.status || "unavailable"}`;
  const freshnessLabel =
    f.status === "live"
      ? `Live (${f.ageMinutes} min ago)`
      : f.status === "recent"
      ? `Updated ${f.ageMinutes} min ago`
      : f.status === "stale"
      ? `Older reading (${f.ageMinutes} min ago)`
      : "Unavailable";

  return `
    <div class="hero-sidebar-stack" data-testid="telemetry-region" aria-label="Live Station Reading">
      <section class="hero-aqi-card">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:var(--space-2); flex-wrap:wrap;">
          <span class="muted-copy" style="display:inline-flex; align-items:center; gap:6px;">${LOCATION_PIN_SVG} ${escapeHtml(loc.city || "City")}</span>
          <span class="badge ${escapeHtml(freshnessBadgeClass)}" data-testid="freshness-badge">
            ${escapeHtml(freshnessLabel)}
          </span>
        </div>

        <div class="hero-aqi-big tabular-num" data-testid="metric-aqi">
          ${escapeHtml(formatMetric(m.aqi))} <span style="font-size:var(--text-base); font-weight:500;">AQI</span>
        </div>
        <div style="display:flex; align-items:center; gap:var(--space-2); flex-wrap:wrap;">
          <strong>${escapeHtml(aqiDesc.band)}</strong>
          <span class="badge badge-${escapeHtml(risk)}" data-testid="risk-badge">${escapeHtml(formatRiskLabel(risk))}</span>
        </div>
        <p class="muted-copy" style="margin:var(--space-2) 0 0; font-size:var(--text-xs);">
          Station: ${escapeHtml(st.name || "Unknown")}
        </p>

        <div class="submetrics-mini">
          <div>
            <div class="metric-label">Fine Dust (PM2.5)</div>
            <div style="font-size:var(--text-xl); font-weight:700;" class="tabular-num" data-testid="metric-pm25">
              ${escapeHtml(formatMetric(m.pm25))}
            </div>
            <div class="muted-copy" style="font-size:0.7rem;">Deep-lung particles</div>
          </div>
          <div>
            <div class="metric-label">Coarse Dust (PM10)</div>
            <div style="font-size:var(--text-xl); font-weight:700;" class="tabular-num" data-testid="metric-pm10">
              ${escapeHtml(formatMetric(m.pm10))}
            </div>
            <div class="muted-copy" style="font-size:0.7rem;">Road dust &amp; pollen</div>
          </div>
        </div>

        <div class="provenance-bar" data-testid="provenance-bar" style="margin-top:var(--space-3); padding-top:var(--space-3); gap:var(--space-2);">
          <span><strong>Source:</strong> ${escapeHtml(s.provider || "Provider")}</span>
          <span class="tabular-num"><strong>Measured:</strong> ${escapeHtml(s.observedAt || "—")}</span>
        </div>

        ${
          onRefresh
            ? `
          <div style="margin-top:var(--space-3);">
            <button type="button" class="btn btn-secondary" style="width:100%;" id="refresh-telemetry-btn" ${
              isRefreshing ? "disabled" : ""
            }>${isRefreshing ? "Refreshing station…" : "↻ Refresh live reading"}</button>
          </div>
        `
            : ""
        }
      </section>

      ${(cities || [])
        .map(
          (c) => `
        <button
          type="button"
          class="city-mini-card"
          data-switch-city="${escapeHtml(c.id)}"
          aria-pressed="${c.id === selectedCityId ? "true" : "false"}"
        >
          <div>
            <div style="font-size:0.7rem; color:var(--color-ink-secondary);">${escapeHtml(c.region)}</div>
            <strong>${escapeHtml(c.name)}</strong>
          </div>
          <span class="muted-copy">${c.id === selectedCityId ? "Active" : "Switch →"}</span>
        </button>
      `
        )
        .join("")}
    </div>
  `;
}

export function renderTelemetryCard(telemetry, policy, options = {}) {
  return renderWeatherSidebarCard(telemetry, policy, [], null, options);
}
