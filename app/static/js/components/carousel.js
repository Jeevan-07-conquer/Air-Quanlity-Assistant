import { escapeHtml } from "../state.js";

/**
 * Compute spatial coverflow offset attribute for 3D carousel cards.
 */
export function carouselOffsetAttr(index, activeIndex, total) {
  let diff = index - activeIndex;
  if (total > 2) {
    if (diff > total / 2) diff -= total;
    if (diff < -total / 2) diff += total;
  }
  if (Math.abs(diff) > 2) return 'data-hidden="true"';
  return `data-offset="${diff}"`;
}

/**
 * Accessible pagination dots using semantic <nav> and aria-current.
 */
export function renderCarouselDots(items, activeIdx, dataAttrName, labelPrefix) {
  return `
    <nav class="carousel-dots" aria-label="${escapeHtml(labelPrefix)} pagination">
      ${items
        .map(
          (item, idx) => `
        <button
          type="button"
          class="carousel-dot"
          aria-current="${idx === activeIdx ? "true" : "false"}"
          aria-label="Show ${escapeHtml(item.title)}"
          ${dataAttrName}="${idx}"
        ></button>
      `
        )
        .join("")}
    </nav>
  `;
}
