import { NAV_ITEMS, escapeHtml } from "../state.js";

const NAV_ICONS = {
  today:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
  plan:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  why:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 .8c0 1.7-2.5 2-2.5 3.7"/><circle cx="12" cy="17" r=".8" fill="currentColor"/></svg>',
  profile:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-4 14.5-4 16 0"/></svg>',
  "about-data":
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 7c0-2 3.6-3.5 8-3.5s8 1.5 8 3.5v10c0 2-3.6 3.5-8 3.5s-8-1.5-8-3.5Z"/><path d="M4 12c0 2 3.6 3.5 8 3.5s8-1.5 8-3.5"/></svg>',
};

const SHORT_LABELS = {
  today: "Today",
  plan: "Routine",
  why: "Why?",
  profile: "Profile",
  "about-data": "Data",
};

const LOCATION_PIN_SVG =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>';

export function renderHeaderContext(container, state, { onChangeLocation }) {
  const city = state.cities.find((c) => c.id === state.selectedCityId);
  const preset = state.presets.find((p) => p.id === state.selectedPresetId);

  if (!city && !preset) {
    container.innerHTML = `<span class="muted-copy">Select a city to begin</span>`;
    return;
  }

  container.innerHTML = `
    ${city ? `<span class="location-pill">${LOCATION_PIN_SVG} <strong>${escapeHtml(city.name)}</strong></span>` : ""}
    ${preset ? `<span class="badge badge-sample">${escapeHtml(preset.title)}</span>` : ""}
    <button type="button" class="btn btn-secondary" style="min-height:36px;" id="header-change-city-btn">Change city</button>
  `;

  container.querySelector("#header-change-city-btn")?.addEventListener("click", onChangeLocation);
}

export function renderPrimaryNav(navListEl, activeRoute, onNavigate) {
  navListEl.innerHTML = NAV_ITEMS.map((item) => {
    const isCurrent = activeRoute === item.id;
    return `
      <li>
        <button
          type="button"
          class="nav-tab"
          data-route="${escapeHtml(item.id)}"
          ${isCurrent ? 'aria-current="page"' : ""}
          title="${escapeHtml(item.label + " — " + item.description)}"
        >
          ${NAV_ICONS[item.id] || ""}
          <span>${escapeHtml(SHORT_LABELS[item.id] || item.label)}</span>
        </button>
      </li>
    `;
  }).join("");

  navListEl.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      onNavigate(btn.dataset.route);
    });
  });
}
