/**
 * Client-side state store + session-only storage helpers (SRD FR-12, §10.3).
 */

export const NAV_ITEMS = [
  { id: "today", label: "Today", description: "Current reading and daily plan" },
  { id: "plan", label: "Plan", description: "Timeline, activities, commute, and indoor actions" },
  { id: "why", label: "Why this advice?", description: "Explanation, sources, thresholds, and confidence" },
  { id: "profile", label: "Profile", description: "Household and lifestyle settings" },
  { id: "about-data", label: "About data", description: "Provider, timestamp, limitations, and safety notes" },
];

const SESSION_KEY = "uaqa_session_v1";

export function defaultProfile() {
  return {
    household: ["adult"],
    vulnerabilities: [],
    primaryActivities: ["commute"],
    commuteMode: "public_transit",
    commuteTime: "morning",
    outdoorWorkerOrAthlete: false,
    indoorContext: {
      purifierAvailable: false,
      indoorSensorAvailable: false,
      cookingExposure: false,
      ventilationConstraints: false,
    },
    plannedOutdoorActivity: {
      activity: "Morning commute and daily errands",
      preferredPeriod: "morning",
    },
    priorities: ["Clear safe timing"],
    isSamplePreset: false,
    presetId: null,
    presetLabel: null,
  };
}

export const appState = {
  route: "landing", // "landing" | "today" | "plan" | "why" | "profile" | "about-data"
  cities: [],
  presets: [],
  selectedCityId: null,
  selectedPresetId: null,
  searchQuery: "",
  locationNotice: "",
  profile: defaultProfile(),
  analysis: null,
  previousAnalysis: null,
  isLoading: false,
  loadingStepIndex: 0,
  requestError: null,
  simulateMode: "normal",
  followupHistory: [],
  isFollowupLoading: false,
  followupError: null,
  landingCarouselIndex: 0,
  planCarouselIndex: 0,
  planViewMode: "flow", // "flow" | "grid"
};

export function saveSessionState() {
  try {
    const payload = {
      selectedCityId: appState.selectedCityId,
      selectedPresetId: appState.selectedPresetId,
      profile: appState.profile,
    };
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(payload));
  } catch {
    // Ignore storage quota/privacy restrictions cleanly
  }
}

export function loadSessionState() {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed.selectedCityId) appState.selectedCityId = parsed.selectedCityId;
    if (parsed.selectedPresetId) appState.selectedPresetId = parsed.selectedPresetId;
    if (parsed.profile) appState.profile = parsed.profile;
  } catch {
    // Ignore corrupt session payload
  }
}

export function clearSessionProfile() {
  appState.selectedPresetId = null;
  appState.profile = defaultProfile();
  appState.analysis = null;
  appState.previousAnalysis = null;
  try {
    window.sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // Ignore
  }
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function announce(message) {
  const el = document.getElementById("live-announcer");
  if (el) {
    el.textContent = message;
  }
}
