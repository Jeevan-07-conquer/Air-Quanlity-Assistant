import { escapeHtml } from "../state.js";
import { describeAqi, renderWeatherSidebarCard } from "./telemetryCard.js";
import {
  renderDegradedBanner,
  renderEmptyState,
  renderErrorState,
  renderMultiStepLoader,
  renderStaleBanner,
  renderUnavailableState,
} from "./states.js";
import { renderProfileView } from "./profileForm.js";

const SIMULATE_OPTIONS = [
  { id: "normal", label: "Standard (Verified)" },
  { id: "stale", label: "Stale reading" },
  { id: "partial_pm", label: "Partial PM10 missing" },
  { id: "provider_timeout", label: "Provider timeout" },
  { id: "provider_quota", label: "Provider quota exceeded" },
  { id: "no_station", label: "No station data" },
  { id: "ai_timeout", label: "AI timeout (fallback)" },
  { id: "ai_invalid_json", label: "AI invalid JSON (fallback)" },
  { id: "ai_unavailable", label: "AI unavailable (fallback)" },
];

const QUICK_QUESTIONS = [
  "Can my child or senior go outside today?",
  "When is it safe to open windows?",
  "How can I lower indoor smoke without a purifier?",
  "What is the safest commute option right now?",
];

const PERIOD_ICONS = {
  morning:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v4"/><path d="m4.93 10.93 2.83 2.83"/><path d="m19.07 10.93-2.83 2.83"/><path d="M2 18h20"/><path d="M16 18a4 4 0 0 0-8 0"/></svg>',
  afternoon:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>',
  evening:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 18a5 5 0 0 0-10 0"/><path d="M2 18h20"/><path d="M12 9V2"/><path d="m4.22 10.22 1.42 1.42"/><path d="m19.78 10.22-1.42 1.42"/></svg>',
  night:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>',
};

function carouselOffsetAttr(index, activeIndex, total) {
  let diff = index - activeIndex;
  if (total > 2) {
    if (diff > total / 2) diff -= total;
    if (diff < -total / 2) diff += total;
  }
  if (Math.abs(diff) > 2) return 'data-hidden="true"';
  return `data-offset="${diff}"`;
}

function buildFlowCards(analysis) {
  const { plan } = analysis;
  const cards = [
    {
      tag: "Most Important Action",
      badgeClass: `badge-${plan.priority?.level || "moderate"}`,
      badgeText: (plan.priority?.level || "moderate").replace("_", " "),
      title: plan.priority?.title || "Priority Action",
      subtitle: "Top recommendation for your household today",
      body: plan.priority?.action || "",
      detailLabel: "Why this matters",
      detailText: plan.priority?.reason || "",
      extra: null,
    },
  ];

  for (const slot of plan.timeline || []) {
    const firstAct = slot.actions?.[0];
    cards.push({
      tag: `${slot.period.toUpperCase()} (${slot.window})`,
      badgeClass: `badge-${slot.risk}`,
      badgeText: slot.risk.replace("_", " "),
      title: firstAct?.title || `${slot.period} plan`,
      subtitle: slot.recommendation,
      body: firstAct ? firstAct.action : slot.recommendation,
      detailLabel: "Indoor backup",
      detailText: slot.indoorAlternative,
      extra: firstAct || null,
    });
  }

  cards.push({
    tag: "Indoor Air Hacks",
    badgeClass: "badge-sample",
    badgeText: `${(plan.indoorAirPlan || []).length} steps`,
    title: "Protect your home air",
    subtitle: "Practical indoor filtration & smoke reduction",
    body: (plan.indoorAirPlan || []).map((i) => `${i.title}: ${i.action}`).join(" • "),
    detailLabel: "Caution",
    detailText: plan.indoorAirPlan?.[0]?.caution || "Avoid indoor smoke and incense.",
    extra: null,
  });

  cards.push({
    tag: "Sustainable Commute",
    badgeClass: "badge-sample",
    badgeText: `${(plan.mobilityOptions || []).length} options`,
    title: "Lower-emission travel choices",
    subtitle: "Commute alternatives tailored to your routine",
    body: (plan.mobilityOptions || []).map((m) => `${m.option} (${m.whyItHelps})`).join(" • "),
    detailLabel: "Trade-off",
    detailText: plan.mobilityOptions?.[0]?.tradeoff || "May require adjusting departure time.",
    extra: null,
  });

  return cards;
}

function renderEvaluatorBar(activeMode, isLoading) {
  return `
    <details class="preview-toolbar">
      <summary style="cursor:pointer; font-weight:600;">
        Developer &amp; QA Testing Tools (simulate stale data or service failures)
      </summary>
      <div style="display:flex; flex-wrap:wrap; gap:var(--space-3); align-items:center; margin-top:var(--space-3);">
        <label for="simulate-mode-select" style="font-weight:600;">
          Simulation mode:
        </label>
        <select id="simulate-mode-select" class="select-input" style="width:auto; min-height:36px;" ${
          isLoading ? "disabled" : ""
        }>
          ${SIMULATE_OPTIONS.map(
            (opt) => `
            <option value="${opt.id}" ${activeMode === opt.id ? "selected" : ""}>
              ${escapeHtml(opt.label)}
            </option>
          `
          ).join("")}
        </select>
      </div>
    </details>
  `;
}

function renderWeatherHero(analysis, state, actions) {
  const { telemetry, policy, plan, degradedMode } = analysis;
  const aqiDesc = describeAqi(telemetry?.measurements?.aqi);
  const timeline = plan?.timeline || [];
  const activePlanIdx = state.planCarouselIndex;

  return `
    <section class="weather-hero-grid" aria-label="Today's Air Quality Overview">
      <div class="hero-forecast-pane">
        <div>
          <div style="display:flex; flex-wrap:wrap; justify-content:space-between; gap:var(--space-2); align-items:center;">
            <span class="condition-pill">
              ${degradedMode ? "Safety Rules Active" : "Live Station + AI Plan"} • ${escapeHtml(aqiDesc.band)}
            </span>
            <span class="badge badge-${escapeHtml(plan.confidence?.level || "medium")}">
              Confidence: ${escapeHtml(plan.confidence?.level || "medium")}
            </span>
          </div>

          <h1 class="hero-headline" style="margin-top:var(--space-4);">
            ${escapeHtml(aqiDesc.band)}
          </h1>
          <p class="lead-copy" data-testid="plan-headline">
            ${escapeHtml(plan.headline)}
          </p>
          <p class="muted-copy" style="margin:0;">
            ${escapeHtml(aqiDesc.hint)}
          </p>
        </div>

        <div class="hero-wave-strip">
          <div class="strip-windows" role="group" aria-label="Daily window quick jump">
            ${timeline
              .map((slot, idx) => {
                const targetCarouselIndex = idx + 1;
                return `
                  <button
                    type="button"
                    class="strip-slot"
                    data-jump-flow="${targetCarouselIndex}"
                    aria-pressed="${activePlanIdx === targetCarouselIndex ? "true" : "false"}"
                  >
                    <div style="font-size:1.1rem;">${PERIOD_ICONS[slot.period] || "•"}</div>
                    <div style="font-size:var(--text-xs); font-weight:600; text-transform:capitalize;">${escapeHtml(slot.period)}</div>
                    <div class="tabular-num" style="font-size:0.7rem; color:var(--color-ink-muted);">${escapeHtml(slot.window)}</div>
                  </button>
                `;
              })
              .join("")}
          </div>
          <svg viewBox="0 0 600 46" width="100%" height="40" preserveAspectRatio="none" aria-hidden="true">
            <path
              d="M0,32 C95,10 155,38 250,20 C340,4 420,38 510,18 C550,10 580,22 600,26"
              fill="none"
              stroke="rgba(139, 224, 239, 0.55)"
              stroke-width="2.2"
            />
          </svg>
        </div>
      </div>

      ${renderWeatherSidebarCard(telemetry, policy, state.cities, state.selectedCityId, {
        onRefresh: actions.onRefreshAnalysis,
        isRefreshing: state.isLoading,
      })}
    </section>
  `;
}

function renderSpatialActionFlow(analysis, state) {
  const cards = buildFlowCards(analysis);
  const activeIdx = ((state.planCarouselIndex % cards.length) + cards.length) % cards.length;

  return `
    <section class="ai-plan-region carousel-section" data-testid="ai-plan-region" aria-label="Interactive Daily Action Flow">
      <div class="carousel-header">
        <div>
          <p class="eyebrow">AI-Personalized Daily Flow (Separate From Raw Station Numbers)</p>
          <h2 class="section-title">Glide through your plan, indoor hacks &amp; commute options</h2>
        </div>
        <div class="carousel-controls">
          <button
            type="button"
            class="btn btn-secondary"
            style="min-height:38px;"
            id="toggle-view-mode-btn"
          >
            ${state.planViewMode === "flow" ? "Show all cards" : "3D Card Flow"}
          </button>
          ${
            state.planViewMode === "flow"
              ? `
            <button type="button" class="btn btn-secondary" style="min-height:38px;" id="plan-prev-btn" aria-label="Previous plan card">←</button>
            <button type="button" class="btn btn-secondary" style="min-height:38px;" id="plan-next-btn" aria-label="Next plan card">→</button>
          `
              : ""
          }
        </div>
      </div>

      ${
        state.planViewMode === "flow"
          ? `
        <div class="carousel-stage" role="region" aria-label="Daily guidance spatial carousel">
          ${cards
            .map((c, idx) => {
              const isCenter = idx === activeIdx;
              return `
                <article
                  class="carousel-card"
                  ${carouselOffsetAttr(idx, activeIdx, cards.length)}
                  data-plan-card-index="${idx}"
                  tabindex="${isCenter ? "0" : "-1"}"
                  aria-hidden="${isCenter ? "false" : "true"}"
                >
                  <div>
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:var(--space-2);">
                      <span class="eyebrow" style="margin:0;">${escapeHtml(c.tag)}</span>
                      <span class="badge ${escapeHtml(c.badgeClass)}">${escapeHtml(c.badgeText)}</span>
                    </div>
                    <h3 class="section-title" style="margin-top:var(--space-2);">${escapeHtml(c.title)}</h3>
                    <p class="muted-copy" style="margin:0 0 var(--space-2); font-size:var(--text-xs);">${escapeHtml(c.subtitle)}</p>
                    <p style="margin:0; font-size:var(--text-sm);">${escapeHtml(c.body)}</p>
                    ${
                      c.extra
                        ? `
                      <details class="rationale-disclosure">
                        <summary>Why this helps &amp; trade-offs</summary>
                        <dl class="rationale-dl">
                          <div><dt>Trigger</dt><dd>${escapeHtml(c.extra.condition)}</dd></div>
                          <div><dt>Direct benefit</dt><dd>${escapeHtml(c.extra.benefit)}</dd></div>
                          <div><dt>Trade-off</dt><dd>${escapeHtml(c.extra.tradeoff)}</dd></div>
                        </dl>
                      </details>
                    `
                        : ""
                    }
                  </div>
                  <div style="border-top:1px solid var(--color-border-subtle); padding-top:var(--space-2); font-size:var(--text-xs); color:var(--color-ink-secondary);">
                    <strong>${escapeHtml(c.detailLabel)}:</strong> ${escapeHtml(c.detailText)}
                  </div>
                </article>
              `;
            })
            .join("")}
        </div>

        <div class="carousel-dots" role="tablist" aria-label="Daily guidance cards">
          ${cards
            .map(
              (c, idx) => `
            <button
              type="button"
              class="carousel-dot"
              role="tab"
              aria-selected="${idx === activeIdx ? "true" : "false"}"
              aria-label="Show ${escapeHtml(c.title)}"
              data-plan-dot="${idx}"
            ></button>
          `
            )
            .join("")}
        </div>
      `
          : renderGridFallback(analysis.plan)
      }

      <details class="rationale-disclosure">
        <summary>Why this plan? Household factors, confidence &amp; limits</summary>
        <div class="two-col-grid" style="margin-top: var(--space-3);">
          <div>
            <strong>What shaped this advice:</strong>
            <ul style="margin: var(--space-2) 0 0; padding-left: var(--space-5); font-size: var(--text-sm);">
              ${(analysis.plan.profileDrivers || []).map((d) => `<li>${escapeHtml(d)}</li>`).join("")}
            </ul>
          </div>
          <div>
            <strong>Confidence &amp; limits:</strong>
            <p class="muted-copy" style="margin: var(--space-2) 0 0;">${escapeHtml(analysis.plan.confidence?.reason)}</p>
            <ul style="margin: var(--space-2) 0 0; padding-left: var(--space-5); font-size: var(--text-sm);">
              ${(analysis.limitations || analysis.plan.limitations || []).map((l) => `<li>${escapeHtml(l)}</li>`).join("")}
            </ul>
          </div>
        </div>
      </details>
    </section>
  `;
}

function renderGridFallback(plan) {
  return `
    <div data-testid="timeline-grid">
      <div class="priority-callout" data-testid="priority-action">
        <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:var(--space-2); align-items:center;">
          <span class="eyebrow" style="margin:0;">Most Important Action Today</span>
          <span class="badge badge-${escapeHtml(plan.priority?.level || "moderate")}">
            ${escapeHtml((plan.priority?.level || "moderate").replace("_", " "))}
          </span>
        </div>
        <h3 style="margin: var(--space-2) 0 var(--space-1);">${escapeHtml(plan.priority?.title)}</h3>
        <p style="margin:0 0 var(--space-2);">${escapeHtml(plan.priority?.action)}</p>
        <p class="muted-copy" style="margin:0;"><strong>Why:</strong> ${escapeHtml(plan.priority?.reason)}</p>
      </div>

      <div class="timeline-grid">
        ${(plan.timeline || [])
          .map(
            (slot) => `
          <article class="timeline-card">
            <div style="display:flex; justify-content:space-between; gap:var(--space-2); align-items:center;">
              <div>
                <strong style="text-transform:capitalize;">${PERIOD_ICONS[slot.period] || ""} ${escapeHtml(slot.period)}</strong>
                <div class="muted-copy tabular-num">${escapeHtml(slot.window)}</div>
              </div>
              <span class="badge badge-${escapeHtml(slot.risk)}">${escapeHtml(slot.risk.replace("_", " "))}</span>
            </div>
            <p style="margin:0; font-size:var(--text-sm);">${escapeHtml(slot.recommendation)}</p>
            <p class="muted-copy" style="margin:0;"><strong>Indoor backup:</strong> ${escapeHtml(slot.indoorAlternative)}</p>
          </article>
        `
          )
          .join("")}
      </div>

      <div class="two-col-grid" style="margin-top: var(--space-4);">
        <section class="decision-card">
          <p class="eyebrow">Indoor Air Hacks</p>
          ${(plan.indoorAirPlan || [])
            .map(
              (item) => `
            <div style="margin-top:var(--space-2);">
              <strong>${escapeHtml(item.title)}</strong>
              <p style="margin:2px 0; font-size:var(--text-sm);">${escapeHtml(item.action)}</p>
            </div>
          `
            )
            .join("")}
        </section>
        <section class="decision-card">
          <p class="eyebrow">Sustainable Commute</p>
          ${(plan.mobilityOptions || [])
            .map(
              (mob) => `
            <div style="margin-top:var(--space-2);">
              <strong>${escapeHtml(mob.option)}</strong>
              <p style="margin:2px 0; font-size:var(--text-sm);">${escapeHtml(mob.whyItHelps)}</p>
            </div>
          `
            )
            .join("")}
        </section>
      </div>
    </div>
  `;
}

function renderFollowupAssistant(state) {
  return `
    <section class="surface-card" id="followup-assistant-section" aria-labelledby="followup-title">
      <p class="eyebrow">Interactive AI Assistant • Grounded in Live Air Data</p>
      <h2 id="followup-title" class="section-title">Ask a question about today’s air or your family’s plans</h2>
      <p class="muted-copy" style="margin-bottom: var(--space-4);">
        Answers stay grounded in your city’s live reading, household profile, and safety rules.
      </p>

      <div class="city-quick-list" style="margin-bottom: var(--space-4);" role="group" aria-label="Suggested questions">
        ${QUICK_QUESTIONS.map(
          (q) => `
          <button type="button" class="chip-btn" data-quick-question="${escapeHtml(q)}" ${
            state.isFollowupLoading ? "disabled" : ""
          }>
            ${escapeHtml(q)}
          </button>
        `
        ).join("")}
      </div>

      <form id="followup-form" class="search-row">
        <div class="field-group">
          <label for="followup-question-input" class="field-label">Your question</label>
          <input
            id="followup-question-input"
            type="text"
            class="text-input"
            maxlength="300"
            placeholder="e.g., Can I jog at 6 PM or should I work out indoors?"
            ${state.isFollowupLoading ? "disabled" : ""}
            required
          />
        </div>
        <button type="submit" class="btn btn-primary" ${state.isFollowupLoading ? "disabled" : ""}>
          ${state.isFollowupLoading ? "Asking AI…" : "Ask Assistant"}
        </button>
      </form>

      ${
        state.followupError
          ? `<p class="muted-copy" role="alert" style="color:var(--color-severity-severe-fg); margin-top:var(--space-3);">${escapeHtml(
              state.followupError
            )}</p>`
          : ""
      }

      ${
        state.followupHistory.length > 0
          ? `
        <div class="split-stack" style="gap:var(--space-3); margin-top:var(--space-4);" aria-live="polite">
          ${state.followupHistory
            .map(
              (item) => `
            <div class="decision-card">
              <p style="margin:0 0 var(--space-2);"><strong>You asked:</strong> ${escapeHtml(item.question)}</p>
              <p style="margin:0 0 var(--space-2);">${escapeHtml(item.answer)}</p>
              <p class="muted-copy" style="margin:0;">
                <strong>Practical next step:</strong> ${escapeHtml(item.nextStep)}
                ${item.degradedMode ? " (Safety rule fallback)" : ""}
              </p>
            </div>
          `
            )
            .join("")}
        </div>
      `
          : ""
      }
    </section>
  `;
}

export function renderAppRouteView(root, state, actions) {
  if (state.route === "profile") {
    renderProfileView(root, state, actions);
    return;
  }

  const activeAnalysis = state.analysis || state.previousAnalysis;
  const city = state.cities.find((c) => c.id === state.selectedCityId);
  const cityName = city?.name || activeAnalysis?.telemetry?.location?.city || "Selected city";

  if (state.route === "today") {
    const blocks = [];

    if (state.isLoading) {
      blocks.push(
        renderMultiStepLoader(state.loadingStepIndex, {
          hasPreviousResult: Boolean(state.previousAnalysis),
        })
      );
    }

    if (state.requestError) {
      blocks.push(
        renderErrorState({
          detail: state.requestError,
          hasPreviousResult: Boolean(activeAnalysis),
        })
      );
    }

    if (!activeAnalysis && !state.isLoading && !state.requestError) {
      blocks.push(renderEmptyState());
    } else if (activeAnalysis) {
      if (activeAnalysis.telemetry?.freshness?.status === "stale") {
        blocks.push(
          renderStaleBanner({
            ageMinutes: activeAnalysis.telemetry.freshness.ageMinutes,
            observedAt: activeAnalysis.telemetry.source.observedAt,
          })
        );
      }

      if (activeAnalysis.status === "unavailable") {
        blocks.push(
          renderUnavailableState({
            cityName,
            reason: activeAnalysis.limitations?.[0],
          })
        );
      } else if (activeAnalysis.degradedMode) {
        blocks.push(renderDegradedBanner(activeAnalysis.degradedReason));
      }

      blocks.push(renderWeatherHero(activeAnalysis, state, actions));
      blocks.push(renderSpatialActionFlow(activeAnalysis, state));
      blocks.push(renderFollowupAssistant(state));
    }

    blocks.push(renderEvaluatorBar(state.simulateMode, state.isLoading));
    root.innerHTML = `<div class="split-stack">${blocks.join("")}</div>`;
  } else if (state.route === "plan") {
    if (!activeAnalysis) {
      root.innerHTML = renderEmptyState();
    } else {
      root.innerHTML = `
        <div class="split-stack">
          ${renderSpatialActionFlow(activeAnalysis, state)}
          ${renderFollowupAssistant(state)}
        </div>
      `;
    }
  } else if (state.route === "why") {
    if (!activeAnalysis) {
      root.innerHTML = renderEmptyState();
    } else {
      const { policy, plan, provenance } = activeAnalysis;
      root.innerHTML = `
        <section class="surface-card split-stack">
          <div>
            <p class="eyebrow">Reasoning, Safety Rules &amp; Trust</p>
            <h1 class="section-title">Why this advice was generated</h1>
            <p class="muted-copy">
              Built-in safety rules inspect your city’s official station data and your household profile
              before the AI writes any personalized advice.
            </p>
          </div>
          <div class="two-col-grid">
            <div class="decision-card">
              <strong>Safety Rule Checks (v${escapeHtml(policy.policyVersion)})</strong>
              <ul style="margin:var(--space-2) 0 0; padding-left:var(--space-5); font-size:var(--text-sm);">
                <li>Risk level: <strong>${escapeHtml(policy.riskCategory.replaceAll("_", " "))}</strong></li>
                <li>Opening windows recommended: <strong>${policy.ventilationPermitted ? "Yes" : "No"}</strong></li>
                <li>Heavy outdoor exercise discouraged: <strong>${policy.strenuousOutdoorDiscouraged ? "Yes" : "No"}</strong></li>
                ${(policy.profileModifiersApplied || []).map((m) => `<li>${escapeHtml(m)}</li>`).join("")}
              </ul>
            </div>
            <div class="decision-card">
              <strong>How Your Household Shaped the Plan (${escapeHtml(plan.confidence.level)} confidence)</strong>
              <p class="muted-copy" style="margin:var(--space-2) 0 0;">${escapeHtml(plan.confidence.reason)}</p>
              <ul style="margin:var(--space-2) 0 0; padding-left:var(--space-5); font-size:var(--text-sm);">
                ${(plan.profileDrivers || []).map((d) => `<li>${escapeHtml(d)}</li>`).join("")}
              </ul>
            </div>
          </div>
          <div class="surface-subtle">
            <strong>System versions:</strong>
            Safety Rules v${escapeHtml(provenance.policyVersion)} • Prompt v${escapeHtml(provenance.promptVersion)}
          </div>
        </section>
      `;
    }
  } else {
    const prov = activeAnalysis?.provenance;
    const telem = activeAnalysis?.telemetry;
    root.innerHTML = `
      <section class="surface-card split-stack">
        <div>
          <p class="eyebrow">Data Sources &amp; Plain-English Guide</p>
          <h1 class="section-title">About Air Quality Terms &amp; Data Sources</h1>
          <p class="muted-copy">
            Readings come directly from official monitoring stations and are never invented by AI.
          </p>
        </div>
        <div class="decision-card">
          <strong>What the numbers mean</strong>
          <ul style="margin:var(--space-2) 0 0; padding-left:var(--space-5); font-size:var(--text-sm);">
            <li><strong>AQI (Air Quality Index):</strong> Overall pollution score. Lower is cleaner (0–50 Clean, 101–150 Poor for sensitive groups, 151+ Unhealthy, 301+ Severe Smog).</li>
            <li><strong>PM2.5 (Fine Dust):</strong> Microscopic soot and smoke particles that reach deep into lungs.</li>
            <li><strong>PM10 (Coarse Dust):</strong> Larger dust, pollen, and road particles that irritate eyes, nose, and throat.</li>
          </ul>
        </div>
        ${
          prov && telem
            ? `
          <div class="decision-card">
            <strong>Current Station Details</strong>
            <ul style="margin:var(--space-2) 0 0; padding-left:var(--space-5); font-size:var(--text-sm);">
              <li><strong>Provider:</strong> ${escapeHtml(prov.provider)}</li>
              <li><strong>Station:</strong> ${escapeHtml(telem.station.name)} (ID: ${escapeHtml(telem.station.id)})</li>
              <li class="tabular-num"><strong>Measured at:</strong> ${escapeHtml(prov.observedAt)}</li>
              <li class="tabular-num"><strong>Checked at:</strong> ${escapeHtml(prov.retrievedAt)}</li>
              <li><strong>Freshness:</strong> ${escapeHtml(telem.freshness.status)}</li>
            </ul>
          </div>
        `
            : ""
        }
      </section>
    `;
  }

  root.querySelector("#simulate-mode-select")?.addEventListener("change", (e) => {
    actions.onChangeSimulateMode(e.target.value);
  });
  root.querySelector("#refresh-telemetry-btn")?.addEventListener("click", actions.onRefreshAnalysis);
  root.querySelectorAll("[data-switch-city]").forEach((btn) => {
    btn.addEventListener("click", () => actions.onSwitchCityAndRun(btn.dataset.switchCity));
  });
  root.querySelectorAll("[data-jump-flow]").forEach((btn) => {
    btn.addEventListener("click", () => actions.onSetPlanCarousel(Number(btn.dataset.jumpFlow)));
  });
  root.querySelector("#toggle-view-mode-btn")?.addEventListener("click", actions.onTogglePlanViewMode);
  root.querySelector("#plan-prev-btn")?.addEventListener("click", () => actions.onShiftPlanCarousel(-1));
  root.querySelector("#plan-next-btn")?.addEventListener("click", () => actions.onShiftPlanCarousel(1));
  root.querySelectorAll("[data-plan-dot]").forEach((btn) => {
    btn.addEventListener("click", () => actions.onSetPlanCarousel(Number(btn.dataset.planDot)));
  });
  root.querySelectorAll("[data-plan-card-index]").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.closest("summary, details")) return;
      const idx = Number(card.dataset.planCardIndex);
      if (idx !== (activeAnalysis ? ((state.planCarouselIndex % 7) + 7) % 7 : 0)) {
        actions.onSetPlanCarousel(idx);
      }
    });
  });
  root.querySelectorAll("[data-nav-target]").forEach((btn) => {
    btn.addEventListener("click", () => actions.onNavigate(btn.dataset.navTarget));
  });
  root.querySelectorAll('[data-action="go-landing"]').forEach((btn) => {
    btn.addEventListener("click", actions.onGoLanding);
  });
  root.querySelectorAll('[data-action="retry-analysis"]').forEach((btn) => {
    btn.addEventListener("click", actions.onRefreshAnalysis);
  });
  root.querySelectorAll("[data-quick-question]").forEach((btn) => {
    btn.addEventListener("click", () => actions.onAskFollowup(btn.dataset.quickQuestion));
  });
  root.querySelector("#followup-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = root.querySelector("#followup-question-input");
    const q = input?.value?.trim();
    if (q) {
      actions.onAskFollowup(q);
    }
  });
}
