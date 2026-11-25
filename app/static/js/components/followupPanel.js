import { escapeHtml } from "../state.js";

const QUICK_QUESTIONS = [
  "Can my child or senior go outside today?",
  "When is it safe to open windows?",
  "How can I lower indoor smoke without a purifier?",
  "What is the safest commute option right now?",
];

/**
 * Secondary grounded conversational Q&A assistant (SRD §8.8).
 */
export function renderFollowupAssistant(state) {
  return `
    <section class="surface-card" id="followup-assistant-section" aria-labelledby="followup-title">
      <p class="eyebrow">Interactive AI Assistant • Grounded in Live Air Data</p>
      <h2 id="followup-title" class="section-title">Ask a question about today’s air or your family’s plans</h2>
      <p class="muted-copy mb-4">
        Answers stay grounded in your city’s live reading, household profile, and safety rules.
      </p>

      <div class="city-quick-list mb-4" role="group" aria-label="Suggested questions">
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
          ? `<p class="muted-copy error-inline" role="alert">${escapeHtml(state.followupError)}</p>`
          : ""
      }

      ${
        state.followupHistory.length > 0
          ? `
        <div class="split-stack stack-sm mt-4" aria-live="polite">
          ${state.followupHistory
            .map(
              (item) => `
            <div class="decision-card">
              <p class="m-0 mb-2"><strong>You asked:</strong> ${escapeHtml(item.question)}</p>
              <p class="m-0 mb-2">${escapeHtml(item.answer)}</p>
              <p class="muted-copy m-0">
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
