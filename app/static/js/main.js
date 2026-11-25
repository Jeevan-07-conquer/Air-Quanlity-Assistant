import {
  announce,
  appState,
  clearSessionProfile,
  loadSessionState,
  saveSessionState,
} from "./state.js";
import { renderHeaderContext, renderPrimaryNav } from "./components/nav.js";
import { renderLandingView } from "./components/landing.js";
import { renderAppRouteView } from "./components/dashboardViews.js";

const headerContextEl = document.getElementById("header-context");
const navListEl = document.getElementById("primary-nav-list");
const appRootEl = document.getElementById("app-root");
const brandHomeLink = document.getElementById("brand-home-link");

let loadingTimer = null;

function clearLoadingTimer() {
  if (loadingTimer) {
    window.clearInterval(loadingTimer);
    loadingTimer = null;
  }
}

async function runAnalysisRequest({ forceRefresh = false } = {}) {
  if (!appState.selectedCityId || appState.isLoading) {
    return;
  }

  clearLoadingTimer();
  appState.isLoading = true;
  appState.loadingStepIndex = 0;
  appState.requestError = null;
  if (appState.analysis) {
    appState.previousAnalysis = appState.analysis;
  }
  renderApp();
  announce("Checking the latest reading and building today's plan.");

  loadingTimer = window.setInterval(() => {
    if (appState.loadingStepIndex < 2) {
      appState.loadingStepIndex += 1;
      renderApp();
    }
  }, 550);

  try {
    const resp = await fetch("/api/analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        locationId: appState.selectedCityId,
        profile: appState.profile,
        options: {
          language: "en",
          includeHourlyPlan: true,
          forceRefresh,
          simulateMode: appState.simulateMode,
        },
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || `HTTP ${resp.status}`);
    }
    appState.analysis = data;
    appState.previousAnalysis = data;
    appState.followupHistory = [];
    appState.followupError = null;
    appState.planCarouselIndex = 0;
    document.body.dataset.atmosphere = data.policy?.riskCategory || "moderate";
    saveSessionState();
    announce(`Updated air quality plan for ${data.telemetry?.location?.city || appState.selectedCityId}.`);
  } catch (err) {
    appState.requestError = err?.message || "Failed to reach analysis API.";
    announce("Unable to refresh analysis. Showing last verified result if available.");
  } finally {
    clearLoadingTimer();
    appState.isLoading = false;
    renderApp();
  }
}

async function runFollowupRequest(question) {
  const activeAnalysis = appState.analysis || appState.previousAnalysis;
  if (!activeAnalysis || appState.isFollowupLoading) return;

  appState.isFollowupLoading = true;
  appState.followupError = null;
  renderApp();

  try {
    const resp = await fetch("/api/followup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        telemetry: activeAnalysis.telemetry,
        policy: activeAnalysis.policy,
        profile: appState.profile,
        plan: activeAnalysis.plan,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || `HTTP ${resp.status}`);
    }
    appState.followupHistory = [
      {
        question,
        answer: data.answer,
        nextStep: data.nextStep,
        degradedMode: Boolean(data.degradedMode),
      },
      ...appState.followupHistory,
    ];
    announce("Follow-up answer ready.");
  } catch (err) {
    appState.followupError = err?.message || "Could not answer your question right now.";
  } finally {
    appState.isFollowupLoading = false;
    renderApp();
  }
}

const actions = {
  onNavigate(route) {
    appState.route = route;
    renderApp();
    announce(`Opened ${route} view.`);
  },
  onGoLanding() {
    appState.route = "landing";
    renderApp();
    announce("Returned to city selection.");
  },
  onSearchChange(value) {
    appState.searchQuery = value;
    appState.locationNotice = "";
    renderApp({ preserveSearchFocus: true });
  },
  onSelectCity(cityId) {
    const city = appState.cities.find((c) => c.id === cityId);
    if (!city) return;
    appState.selectedCityId = city.id;
    appState.searchQuery = city.name;
    appState.locationNotice = "";
    saveSessionState();
    renderApp();
    announce(`Selected ${city.name}.`);
  },
  onCustomizeProfile() {
    if (!appState.selectedCityId) return;
    appState.route = "profile";
    renderApp();
  },
  onQuickPlan() {
    if (!appState.selectedCityId) return;
    appState.route = "today";
    runAnalysisRequest();
  },
  onSelectPreset(presetId) {
    const preset = appState.presets.find((p) => p.id === presetId);
    if (!preset) return;
    appState.selectedPresetId = preset.id;
    appState.selectedCityId = preset.location_id;
    appState.searchQuery = appState.cities.find((c) => c.id === preset.location_id)?.name || "";
    appState.profile = structuredClone(preset.profile);
    appState.simulateMode = "normal";
    appState.route = "today";
    saveSessionState();
    runAnalysisRequest({ forceRefresh: true });
  },
  onSaveAndGenerate(updatedProfile) {
    appState.profile = updatedProfile;
    appState.selectedPresetId = null;
    if (!appState.selectedCityId) {
      appState.selectedCityId = "delhi";
    }
    appState.route = "today";
    saveSessionState();
    runAnalysisRequest({ forceRefresh: true });
  },
  onClearProfile() {
    clearSessionProfile();
    renderApp();
    announce("Session profile cleared.");
  },
  onRefreshAnalysis() {
    runAnalysisRequest({ forceRefresh: true });
  },
  onChangeSimulateMode(mode) {
    appState.simulateMode = mode;
    runAnalysisRequest({ forceRefresh: true });
  },
  onSwitchCityAndRun(cityId) {
    const city = appState.cities.find((c) => c.id === cityId);
    if (!city) return;
    appState.selectedCityId = city.id;
    appState.searchQuery = city.name;
    saveSessionState();
    runAnalysisRequest();
  },
  onShiftLandingCarousel(delta) {
    const n = appState.presets.length || 1;
    appState.landingCarouselIndex = ((appState.landingCarouselIndex + delta) % n + n) % n;
    renderApp();
  },
  onSetLandingCarousel(idx) {
    appState.landingCarouselIndex = idx;
    renderApp();
  },
  onShiftPlanCarousel(delta) {
    const n = 7;
    appState.planCarouselIndex = ((appState.planCarouselIndex + delta) % n + n) % n;
    renderApp();
  },
  onSetPlanCarousel(idx) {
    appState.planCarouselIndex = idx;
    appState.planViewMode = "flow";
    renderApp();
  },
  onTogglePlanViewMode() {
    appState.planViewMode = appState.planViewMode === "flow" ? "grid" : "flow";
    renderApp();
  },
  onAskFollowup(question) {
    runFollowupRequest(question);
  },
  onRequestGeolocation() {
    if (!("geolocation" in navigator)) {
      appState.locationNotice =
        "Browser geolocation is not available here. Please select a supported city manually.";
      renderApp();
      return;
    }
    appState.locationNotice = "Requesting browser location permission…";
    renderApp();

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const { latitude, longitude } = pos.coords;
          const resp = await fetch(`/api/locations?lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`);
          const data = await resp.json();
          if (data.resolutionStatus === "matched" && data.matches?.length) {
            appState.selectedCityId = data.matches[0].id;
            appState.searchQuery = data.matches[0].name;
          }
          appState.locationNotice = data.message || "Location checked.";
        } catch {
          appState.locationNotice = "Could not resolve coordinates. Manual selection remains ready.";
        }
        renderApp();
      },
      () => {
        appState.locationNotice = "Location permission declined. Manual city selection remains ready.";
        renderApp();
      },
      { timeout: 6000 }
    );
  },
};

function renderApp({ preserveSearchFocus = false } = {}) {
  let selectionStart = null;
  if (preserveSearchFocus) {
    const input = document.getElementById("city-search-input");
    if (input) selectionStart = input.selectionStart;
  }

  appRootEl?.setAttribute("aria-busy", appState.isLoading || appState.isFollowupLoading ? "true" : "false");

  renderHeaderContext(headerContextEl, appState, {
    onChangeLocation: actions.onGoLanding,
  });
  renderPrimaryNav(navListEl, appState.route, actions.onNavigate);

  if (appState.route === "landing") {
    renderLandingView(appRootEl, appState, actions);
    if (preserveSearchFocus) {
      const nextInput = document.getElementById("city-search-input");
      if (nextInput) {
        nextInput.focus();
        if (selectionStart !== null) {
          nextInput.setSelectionRange(selectionStart, selectionStart);
        }
      }
    }
  } else {
    renderAppRouteView(appRootEl, appState, actions);
  }
}

async function bootstrap() {
  loadSessionState();

  brandHomeLink?.addEventListener("click", (e) => {
    e.preventDefault();
    actions.onGoLanding();
  });

  document.addEventListener("keydown", (e) => {
    if (!e.target.closest(".carousel-stage")) return;
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      if (appState.route === "landing") actions.onShiftLandingCarousel(-1);
      else actions.onShiftPlanCarousel(-1);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      if (appState.route === "landing") actions.onShiftLandingCarousel(1);
      else actions.onShiftPlanCarousel(1);
    }
  });

  try {
    const resp = await fetch("/api/shell-bootstrap");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    appState.cities = data.cities || [];
    appState.presets = data.presets || [];
  } catch {
    appState.locationNotice = "Unable to load city configuration from server.";
  }

  renderApp();
}

bootstrap();
