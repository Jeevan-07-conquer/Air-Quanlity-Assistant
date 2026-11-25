import { escapeHtml } from "../state.js";

const LOADING_STEPS = [
  "Checking the latest reading",
  "Applying your household context",
  "Building today’s plan",
];

export function renderMultiStepLoader(activeIndex = 0, { hasPreviousResult = false } = {}) {
  return `
    <section class="state-panel" role="status" aria-live="polite" aria-label="Preparing daily air quality plan">
      <p class="eyebrow">Analysis in progress</p>
      <h2 class="section-title">Preparing today’s guidance</h2>
      <p class="muted-copy">
        ${
          hasPreviousResult
            ? "Preserving your previous verified reading below while fetching the latest update."
            : "Environmental measurements are verified before any personalized guidance is assembled."
        }
      </p>
      <ol class="loader-steps">
        ${LOADING_STEPS.map((label, idx) => {
          const status = idx < activeIndex ? "done" : idx === activeIndex ? "active" : "pending";
          return `
            <li class="loader-step" data-status="${status}">
              <span class="step-dot" aria-hidden="true"></span>
              <span>${escapeHtml(label)}</span>
            </li>
          `;
        }).join("")}
      </ol>
    </section>
  `;
}

export function renderEmptyState() {
  return `
    <section class="state-panel" aria-label="No analysis loaded yet">
      <p class="eyebrow">Ready when you are</p>
      <h2 class="section-title">Select a city or sample profile to view today’s plan</h2>
      <p class="muted-copy">
        Choose one of the supported Indian cities or load a labeled sample profile to see verified readings and personalized guidance.
      </p>
      <div class="mt-4">
        <button type="button" class="btn btn-primary" data-action="go-landing">
          Choose city or sample profile
        </button>
      </div>
    </section>
  `;
}

export function renderStaleBanner({ ageMinutes, observedAt } = {}) {
  return `
    <section class="state-panel state-panel-warning" role="status" data-testid="stale-warning" aria-label="Stale telemetry warning">
      <div class="row-between">
        <span class="badge badge-stale">Stale reading (${escapeHtml(ageMinutes ?? "120+")} min old)</span>
        <span class="muted-copy tabular-num">Last observed: ${escapeHtml(observedAt || "Unknown")}</span>
      </div>
      <p class="mt-3 m-0">
        <strong>What happened:</strong> The monitoring station has not reported a recent update.
        <strong>What remains trustworthy:</strong> The last verified values are shown with conservative safety guidance until a fresh reading arrives.
      </p>
    </section>
  `;
}

export function renderDegradedBanner(degradedReason) {
  const map = {
    ai_timeout: {
      badge: "AI timeout — Deterministic fallback",
      title: "AI personalization timed out",
      msg: "Verified station readings and deterministic policy guidance remain active below.",
    },
    ai_schema_validation_failed: {
      badge: "AI validation fallback",
      title: "AI output did not pass safety checks",
      msg: "Showing deterministic policy-based guidance so you never see unverified numbers or unsafe claims.",
    },
    ai_unavailable: {
      badge: "AI unavailable — Deterministic fallback",
      title: "Personalized AI layer is temporarily unavailable",
      msg: "Showing verified telemetry and deterministic household safety recommendations.",
    },
    provider_timeout: {
      badge: "Provider timeout — Cached reading",
      title: "Live telemetry provider timed out",
      msg: "Preserving the last verified station reading with stale caution.",
    },
  };
  const info = map[degradedReason] || {
    badge: "Degraded mode",
    title: "Operating in safe fallback mode",
    msg: "Verified facts and conservative guidance are displayed transparently.",
  };

  return `
    <section class="state-panel state-panel-warning" role="status" data-testid="degraded-banner">
      <span class="badge badge-stale">${escapeHtml(info.badge)}</span>
      <h2 class="section-title mt-2">${escapeHtml(info.title)}</h2>
      <p class="m-0">${escapeHtml(info.msg)}</p>
    </section>
  `;
}

export function renderUnavailableState({ cityName = "Selected city", reason = "" } = {}) {
  return `
    <section class="state-panel state-panel-neutral" role="status" data-testid="unavailable-state">
      <span class="badge badge-unavailable">Unavailable</span>
      <h2 class="section-title mt-3">
        No trustworthy air-quality reading is available for ${escapeHtml(cityName)}
      </h2>
      <p class="muted-copy">
        ${escapeHtml(reason || "Because verified station readings could not be confirmed, location-specific AI guidance is paused. We never invent current AQI numbers.")}
      </p>
      <div class="mt-4 row-wrap-md">
        <button type="button" class="btn btn-primary" data-action="retry-analysis">Retry reading</button>
        <button type="button" class="btn btn-secondary" data-action="go-landing">Choose another city</button>
      </div>
    </section>
  `;
}

export function renderErrorState({ detail, hasPreviousResult = false } = {}) {
  return `
    <section class="state-panel state-panel-error" role="alert" data-testid="error-state">
      <p class="eyebrow">Request error</p>
      <h2 class="section-title">Could not refresh today’s analysis</h2>
      <p>${escapeHtml(detail || "A temporary network or server error occurred.")}</p>
      <p class="muted-copy mt-2">
        ${
          hasPreviousResult
            ? "Your previous verified result remains displayed below."
            : "Please try again or switch to another supported city."
        }
      </p>
      <div class="mt-4 row-wrap-md">
        <button type="button" class="btn btn-primary" data-action="retry-analysis">Retry request</button>
        <button type="button" class="btn btn-secondary" data-action="go-landing">Change city</button>
      </div>
    </section>
  `;
}
