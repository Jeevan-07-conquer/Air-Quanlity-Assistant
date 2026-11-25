import { escapeHtml } from "../state.js";

const HOUSEHOLD_OPTIONS = [
  { id: "adult", label: "Adults" },
  { id: "child", label: "Child / Toddler" },
  { id: "senior", label: "Senior citizen" },
  { id: "pregnant", label: "Pregnant person" },
];

const VULNERABILITY_OPTIONS = [
  { id: "respiratory_condition", label: "Respiratory condition (e.g., asthma)" },
  { id: "cardiovascular_condition", label: "Cardiovascular sensitivity" },
];

const ACTIVITY_OPTIONS = [
  { id: "commute", label: "Office / daily commute" },
  { id: "school", label: "School run" },
  { id: "sports", label: "Sports / running" },
  { id: "errands", label: "Errands / shopping" },
  { id: "outdoor_work", label: "Outdoor work" },
];

const COMMUTE_MODES = [
  { id: "public_transit", label: "Public transit (metro / bus)" },
  { id: "walking", label: "Walking" },
  { id: "two_wheeler", label: "Two-wheeler" },
  { id: "car", label: "Car" },
  { id: "carpool", label: "Carpool" },
  { id: "mixed", label: "Mixed transport" },
];

export function renderProfileView(root, state, actions) {
  const p = state.profile;
  const selectedCity = state.cities.find((c) => c.id === state.selectedCityId);

  root.innerHTML = `
    <div class="landing-layout">
      <section class="surface-card" aria-labelledby="profile-heading">
        <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:var(--space-3); align-items:flex-start;">
          <div>
            <p class="eyebrow">Profile Setup • Progressive Disclosure</p>
            <h1 id="profile-heading" class="section-title">Tailor guidance to your household &amp; routine</h1>
          </div>
          ${
            p.isSamplePreset
              ? `<span class="badge badge-sample">${escapeHtml(p.presetLabel || "Sample profile")}</span>`
              : ""
          }
        </div>

        <p class="muted-copy">
          Only household group, primary activity, and commute mode are required. Optional health sensitivity
          fields are used solely to apply safer thresholds for this session and are never stored on our servers.
        </p>

        <form id="profile-setup-form" class="form-stack">
          <fieldset class="fieldset-card">
            <legend class="fieldset-legend">1. Household members (Required — select at least one)</legend>
            <p class="field-hint">Helps apply stricter exposure safeguards when children, seniors, or pregnant members are present.</p>
            <div class="option-grid">
              ${HOUSEHOLD_OPTIONS.map(
                (opt) => `
                <label class="check-tile">
                  <input type="checkbox" name="household" value="${opt.id}" ${
                  p.household.includes(opt.id) ? "checked" : ""
                } />
                  <span>${escapeHtml(opt.label)}</span>
                </label>
              `
              ).join("")}
            </div>
          </fieldset>

          <fieldset class="fieldset-card">
            <legend class="fieldset-legend">2. Routine &amp; primary commute (Required)</legend>
            <p class="field-hint">Shapes peak-hour shifting and practical lower-emission travel alternatives.</p>
            <div class="option-grid">
              ${ACTIVITY_OPTIONS.map(
                (opt) => `
                <label class="check-tile">
                  <input type="checkbox" name="primaryActivities" value="${opt.id}" ${
                  p.primaryActivities.includes(opt.id) ? "checked" : ""
                } />
                  <span>${escapeHtml(opt.label)}</span>
                </label>
              `
              ).join("")}
            </div>

            <div class="search-row" style="margin-top: var(--space-4);">
              <div class="field-group">
                <label for="commute-mode-select" class="field-label">Primary transport mode</label>
                <select id="commute-mode-select" name="commuteMode" class="select-input">
                  ${COMMUTE_MODES.map(
                    (m) => `
                    <option value="${m.id}" ${p.commuteMode === m.id ? "selected" : ""}>
                      ${escapeHtml(m.label)}
                    </option>
                  `
                  ).join("")}
                </select>
              </div>
              <div class="field-group">
                <label for="commute-time-select" class="field-label">Typical travel window</label>
                <select id="commute-time-select" name="commuteTime" class="select-input">
                  <option value="morning" ${p.commuteTime === "morning" ? "selected" : ""}>Morning</option>
                  <option value="afternoon" ${p.commuteTime === "afternoon" ? "selected" : ""}>Afternoon</option>
                  <option value="evening" ${p.commuteTime === "evening" ? "selected" : ""}>Evening</option>
                  <option value="flexible" ${p.commuteTime === "flexible" ? "selected" : ""}>Flexible</option>
                </select>
              </div>
            </div>
          </fieldset>

          <fieldset class="fieldset-card">
            <legend class="fieldset-legend">3. Planned outdoor activity &amp; exertion (Optional)</legend>
            <div class="search-row" style="margin-top: var(--space-2);">
              <div class="field-group">
                <label for="planned-activity-input" class="field-label">Planned outdoor activity</label>
                <input
                  id="planned-activity-input"
                  name="plannedActivity"
                  type="text"
                  class="text-input"
                  maxlength="80"
                  placeholder="e.g., Morning 5k run or school drop-off"
                  value="${escapeHtml(p.plannedOutdoorActivity?.activity || "")}"
                />
              </div>
              <div class="field-group">
                <label for="planned-period-select" class="field-label">Preferred period</label>
                <select id="planned-period-select" name="preferredPeriod" class="select-input">
                  <option value="morning" ${p.plannedOutdoorActivity?.preferredPeriod === "morning" ? "selected" : ""}>Morning</option>
                  <option value="afternoon" ${p.plannedOutdoorActivity?.preferredPeriod === "afternoon" ? "selected" : ""}>Afternoon</option>
                  <option value="evening" ${p.plannedOutdoorActivity?.preferredPeriod === "evening" ? "selected" : ""}>Evening</option>
                  <option value="night" ${p.plannedOutdoorActivity?.preferredPeriod === "night" ? "selected" : ""}>Night</option>
                </select>
              </div>
            </div>
            <label class="check-tile" style="margin-top: var(--space-3);">
              <input type="checkbox" name="outdoorWorkerOrAthlete" ${p.outdoorWorkerOrAthlete ? "checked" : ""} />
              <span>High-exertion outdoor athlete or outdoor worker</span>
            </label>
          </fieldset>

          <fieldset class="fieldset-card">
            <legend class="fieldset-legend">4. Indoor air context &amp; optional health sensitivity</legend>
            <p class="field-hint">
              Why we ask: determines whether purifier filtration, kitchen exhaust, or stricter respiratory cautions apply.
              Health selections stay in your browser session only.
            </p>
            <div class="option-grid">
              <label class="check-tile">
                <input type="checkbox" name="purifierAvailable" ${p.indoorContext.purifierAvailable ? "checked" : ""} />
                <span>Air purifier available</span>
              </label>
              <label class="check-tile">
                <input type="checkbox" name="indoorSensorAvailable" ${p.indoorContext.indoorSensorAvailable ? "checked" : ""} />
                <span>Indoor air sensor available</span>
              </label>
              <label class="check-tile">
                <input type="checkbox" name="cookingExposure" ${p.indoorContext.cookingExposure ? "checked" : ""} />
                <span>Indoor cooking smoke/fumes</span>
              </label>
              <label class="check-tile">
                <input type="checkbox" name="ventilationConstraints" ${p.indoorContext.ventilationConstraints ? "checked" : ""} />
                <span>Limited window ventilation</span>
              </label>
              ${VULNERABILITY_OPTIONS.map(
                (v) => `
                <label class="check-tile">
                  <input type="checkbox" name="vulnerabilities" value="${v.id}" ${
                  p.vulnerabilities.includes(v.id) ? "checked" : ""
                } />
                  <span>${escapeHtml(v.label)} (Optional)</span>
                </label>
              `
              ).join("")}
            </div>
          </fieldset>

          <div id="profile-validation-error" class="state-panel state-panel-error" role="alert" style="display:none;"></div>

          <div class="cta-bar">
            <button type="button" class="btn btn-secondary" id="clear-profile-btn">
              Clear profile (session reset)
            </button>
            <button type="submit" class="btn btn-primary" id="generate-plan-btn">
              ${selectedCity ? `Generate plan for ${escapeHtml(selectedCity.name)}` : "Generate today’s plan"}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;

  root.querySelector("#clear-profile-btn")?.addEventListener("click", actions.onClearProfile);

  root.querySelector("#profile-setup-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const household = [...form.querySelectorAll('input[name="household"]:checked')].map((el) => el.value);
    const primaryActivities = [...form.querySelectorAll('input[name="primaryActivities"]:checked')].map(
      (el) => el.value
    );
    const vulnerabilities = [...form.querySelectorAll('input[name="vulnerabilities"]:checked')].map(
      (el) => el.value
    );

    const errBox = root.querySelector("#profile-validation-error");
    if (household.length === 0 || primaryActivities.length === 0) {
      errBox.style.display = "block";
      errBox.textContent = "Please select at least one household member and one primary activity.";
      return;
    }
    errBox.style.display = "none";

    const activityText = form.querySelector("#planned-activity-input").value.trim();
    const preferredPeriod = form.querySelector("#planned-period-select").value;

    actions.onSaveAndGenerate({
      household,
      vulnerabilities,
      primaryActivities,
      commuteMode: form.querySelector("#commute-mode-select").value,
      commuteTime: form.querySelector("#commute-time-select").value,
      outdoorWorkerOrAthlete: form.querySelector('input[name="outdoorWorkerOrAthlete"]').checked,
      indoorContext: {
        purifierAvailable: form.querySelector('input[name="purifierAvailable"]').checked,
        indoorSensorAvailable: form.querySelector('input[name="indoorSensorAvailable"]').checked,
        cookingExposure: form.querySelector('input[name="cookingExposure"]').checked,
        ventilationConstraints: form.querySelector('input[name="ventilationConstraints"]').checked,
      },
      plannedOutdoorActivity: activityText
        ? { activity: activityText, preferredPeriod }
        : null,
      priorities: p.priorities || [],
      isSamplePreset: false,
      presetId: null,
      presetLabel: null,
    });
  });
}
