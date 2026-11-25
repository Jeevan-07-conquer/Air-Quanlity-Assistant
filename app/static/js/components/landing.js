import { escapeHtml } from "../state.js";

function findCityMatches(cities, query) {
  const q = query.trim().toLowerCase();
  if (!q) return cities;
  return cities.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      c.region.toLowerCase().includes(q) ||
      c.aliases.some((alias) => alias.toLowerCase().includes(q))
  );
}

function carouselOffsetAttr(index, activeIndex, total) {
  let diff = index - activeIndex;
  if (total > 2) {
    if (diff > total / 2) diff -= total;
    if (diff < -total / 2) diff += total;
  }
  if (Math.abs(diff) > 2) return 'data-hidden="true"';
  return `data-offset="${diff}"`;
}

export function renderLandingView(root, state, actions) {
  const matches = findCityMatches(state.cities, state.searchQuery);
  const selectedCity = state.cities.find((c) => c.id === state.selectedCityId);
  const hasUnsupportedQuery = state.searchQuery.trim().length > 0 && matches.length === 0;
  const presets = state.presets || [];
  const activeIdx = presets.length ? ((state.landingCarouselIndex % presets.length) + presets.length) % presets.length : 0;

  root.innerHTML = `
    <div class="landing-layout">
      <section class="surface-card" aria-labelledby="landing-headline">
        <span class="condition-pill">Atmospheric Air &amp; Daily Routine Assistant</span>
        <h1 id="landing-headline" class="hero-headline" style="margin-top:var(--space-3);">
          Turn today’s air quality into a safer daily plan.
        </h1>
        <p class="lead-copy">
          Check live station air quality for your city, then glide through personalized morning-to-night
          routines, indoor air hacks, and lower-emission commute choices.
        </p>

        <form id="landing-location-form" novalidate>
          <div class="search-row">
            <div class="field-group">
              <label for="city-search-input" class="field-label">
                Choose your city
              </label>
              <input
                id="city-search-input"
                type="search"
                class="text-input"
                placeholder="Search Delhi, Noida, Mumbai, or Kolkata"
                value="${escapeHtml(state.searchQuery)}"
                autocomplete="off"
                aria-describedby="city-search-hint"
              />
              <span id="city-search-hint" class="field-hint">
                Supports Delhi NCR, Noida, Mumbai, and Kolkata.
              </span>
            </div>

            <button type="button" class="btn btn-secondary" id="use-location-btn">
              Use my location
            </button>
          </div>

          ${
            state.searchQuery.trim().length > 0 && matches.length > 0
              ? `
            <ul class="city-suggestions" role="listbox" aria-label="Matching supported cities">
              ${matches
                .map(
                  (city) => `
                <li>
                  <button
                    type="button"
                    class="city-option"
                    role="option"
                    aria-selected="${city.id === state.selectedCityId ? "true" : "false"}"
                    data-city-id="${escapeHtml(city.id)}"
                  >
                    <span><strong>${escapeHtml(city.name)}</strong> — ${escapeHtml(city.region)}</span>
                    <span class="muted-copy">Select</span>
                  </button>
                </li>
              `
                )
                .join("")}
            </ul>
          `
              : ""
          }

          ${
            hasUnsupportedQuery
              ? `
            <div class="state-panel state-panel-neutral" role="status" style="margin-top: var(--space-3);">
              <strong>Location not yet supported:</strong> "${escapeHtml(state.searchQuery.trim())}"
              is outside the supported cities (Delhi, Noida, Mumbai, Kolkata). Pick a city below.
            </div>
          `
              : ""
          }

          ${
            state.locationNotice
              ? `
            <div class="state-panel state-panel-neutral" role="status" style="margin-top: var(--space-3);">
              ${escapeHtml(state.locationNotice)}
            </div>
          `
              : ""
          }

          <div class="city-quick-list" role="group" aria-label="Supported cities">
            ${state.cities
              .map(
                (city) => `
              <button
                type="button"
                class="chip-btn"
                data-quick-city="${escapeHtml(city.id)}"
                aria-pressed="${city.id === state.selectedCityId ? "true" : "false"}"
              >
                ${escapeHtml(city.name)}
              </button>
            `
              )
              .join("")}
          </div>

          <div class="cta-bar">
            <p class="trust-line">
              Live station readings are displayed separately from AI guidance.
            </p>
            <div style="display:flex; gap:var(--space-2); flex-wrap:wrap;">
              <button
                type="button"
                class="btn btn-secondary"
                id="landing-customize-profile-btn"
                ${selectedCity ? "" : "disabled"}
              >
                Customize profile
              </button>
              <button
                type="submit"
                class="btn btn-primary"
                id="landing-continue-btn"
                ${selectedCity ? "" : "disabled"}
              >
                ${selectedCity ? `Check ${escapeHtml(selectedCity.name)} air &amp; plan` : "Select a city to continue"}
              </button>
            </div>
          </div>
        </form>
      </section>

      ${
        presets.length > 0
          ? `
        <section class="carousel-section" aria-labelledby="sample-presets-title">
          <div class="carousel-header">
            <div>
              <p class="eyebrow">Explore Household Scenarios</p>
              <h2 id="sample-presets-title" class="section-title">
                Glide through labeled sample profiles
              </h2>
            </div>
            <div class="carousel-controls">
              <button type="button" class="btn btn-secondary" id="landing-prev-btn" aria-label="Previous sample profile">← Prev</button>
              <button type="button" class="btn btn-secondary" id="landing-next-btn" aria-label="Next sample profile">Next →</button>
            </div>
          </div>

          <div class="carousel-stage" role="region" aria-label="Sample profile spatial carousel">
            ${presets
              .map((preset, idx) => {
                const isCenter = idx === activeIdx;
                return `
                  <article
                    class="carousel-card"
                    ${carouselOffsetAttr(idx, activeIdx, presets.length)}
                    data-landing-card-index="${idx}"
                    tabindex="${isCenter ? "0" : "-1"}"
                    aria-hidden="${isCenter ? "false" : "true"}"
                  >
                    <div>
                      <div style="display:flex; justify-content:space-between; align-items:center; gap:var(--space-2);">
                        <span class="badge badge-sample">${escapeHtml(preset.badge)}</span>
                        <span class="muted-copy tabular-num">${idx + 1} / ${presets.length}</span>
                      </div>
                      <h3 class="section-title" style="margin-top:var(--space-3);">${escapeHtml(preset.title)}</h3>
                      <p class="muted-copy" style="margin:0 0 var(--space-2);">${escapeHtml(preset.subtitle)}</p>
                      <p style="margin:0; font-size:var(--text-sm);">${escapeHtml(preset.profile_summary)}</p>
                    </div>
                    <div style="display:flex; justify-content:flex-end;">
                      <button
                        type="button"
                        class="btn btn-primary"
                        data-preset-id="${escapeHtml(preset.id)}"
                        ${isCenter ? "" : 'tabindex="-1"'}
                      >
                        Open daily plan →
                      </button>
                    </div>
                  </article>
                `;
              })
              .join("")}
          </div>

          <div class="carousel-dots" role="tablist" aria-label="Sample profile cards">
            ${presets
              .map(
                (preset, idx) => `
              <button
                type="button"
                class="carousel-dot"
                role="tab"
                aria-selected="${idx === activeIdx ? "true" : "false"}"
                aria-label="Show ${escapeHtml(preset.title)}"
                data-landing-dot="${idx}"
              ></button>
            `
              )
              .join("")}
          </div>
        </section>
      `
          : ""
      }
    </div>
  `;

  root.querySelector("#city-search-input")?.addEventListener("input", (e) => {
    actions.onSearchChange(e.target.value);
  });
  root.querySelectorAll("[data-city-id]").forEach((btn) => {
    btn.addEventListener("click", () => actions.onSelectCity(btn.dataset.cityId));
  });
  root.querySelectorAll("[data-quick-city]").forEach((btn) => {
    btn.addEventListener("click", () => actions.onSelectCity(btn.dataset.quickCity));
  });
  root.querySelector("#use-location-btn")?.addEventListener("click", actions.onRequestGeolocation);
  root.querySelector("#landing-customize-profile-btn")?.addEventListener("click", actions.onCustomizeProfile);
  root.querySelector("#landing-location-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    if (state.selectedCityId) {
      actions.onQuickPlan();
    }
  });
  root.querySelector("#landing-prev-btn")?.addEventListener("click", () => actions.onShiftLandingCarousel(-1));
  root.querySelector("#landing-next-btn")?.addEventListener("click", () => actions.onShiftLandingCarousel(1));
  root.querySelectorAll("[data-landing-dot]").forEach((btn) => {
    btn.addEventListener("click", () => actions.onSetLandingCarousel(Number(btn.dataset.landingDot)));
  });
  root.querySelectorAll("[data-landing-card-index]").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.closest("[data-preset-id]")) return;
      const idx = Number(card.dataset.landingCardIndex);
      if (idx !== activeIdx) actions.onSetLandingCarousel(idx);
    });
  });
  root.querySelectorAll("[data-preset-id]").forEach((btn) => {
    btn.addEventListener("click", () => actions.onSelectPreset(btn.dataset.presetId));
  });
}
