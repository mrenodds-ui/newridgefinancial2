/**
 * Shared UI component library for NewRidgeFinancial 2.0.
 *
 * One design system, used by every page. Components return HTML strings that
 * map onto the existing mockup-faithful CSS classes, so the visual look is
 * identical across pages and never duplicated per page.
 *
 * Components: AppShell, Sidebar, TopBar, PageTitle, Card, Button, Table,
 * FormField, Modal, StatusBadge, EmptyState, LoadingState, ErrorState.
 */
const UI = (function () {
  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function attrs(map) {
    if (!map) return "";
    return Object.entries(map)
      .filter(([, v]) => v != null && v !== false)
      .map(([k, v]) => (v === true ? ` ${k}` : ` ${esc(k)}="${esc(v)}"`))
      .join("");
  }

  /* ---- AppShell ---- */
  function AppShell(opts) {
    const o = opts || {};
    return `
      <div class="app">
        <aside class="sidebar" id="${esc(o.sidebarId || "sidebar")}" aria-label="Primary navigation">${o.sidebar || ""}</aside>
        <main class="main">${o.main || ""}</main>
      </div>`;
  }

  /* ---- StatusBadge ---- */
  const TONE_ALIASES = { green: "ok", success: "ok", blue: "info", gold: "warn", yellow: "warn", danger: "red", error: "red" };
  function StatusBadge(text, tone) {
    const t = TONE_ALIASES[tone] || tone || "muted";
    return `<span class="pv-pill pv-pill--${esc(t)}">${esc(text)}</span>`;
  }

  /* ---- Button ---- */
  function Button(opts) {
    const o = opts || {};
    const variant = o.variant || "secondary";
    const cls =
      variant === "link"
        ? "pv-gold-link"
        : variant === "toolbar"
          ? "pv-toolbar__btn"
          : `pv-button${variant === "primary" ? " pv-button--primary" : ""}${variant === "ghost" ? " pv-button--ghost" : ""}`;
    const icon = o.icon ? `<span class="pv-btn-ico">${esc(o.icon)}</span>` : "";
    const tag = variant === "link" ? "button" : "button";
    return `<${tag} class="${cls}${o.className ? " " + esc(o.className) : ""}" type="${esc(o.type || "button")}"${o.disabled ? " disabled" : ""}${attrs(o.attrs)}>${icon}${esc(o.label)}</${tag}>`;
  }

  /* ---- PageTitle ---- */
  function PageTitle(opts) {
    const o = opts || {};
    return `
      <div class="pv__header-main">
        ${o.eyebrow ? `<p class="pv__eyebrow">${esc(o.eyebrow)}</p>` : ""}
        <h2 class="pv__title">${esc(o.title)}</h2>
        ${o.subtitle ? `<p class="pv__subtitle">${esc(o.subtitle)}</p>` : ""}
      </div>`;
  }

  /* ---- TopBar (per-page header bar: title + actions + safety) ---- */
  function TopBar(opts) {
    const o = opts || {};
    const actions = (o.actions && o.actions.length) ? `<div class="pv-toolbar">${o.actions.join("")}</div>` : "";
    const badge = o.dataBadge ? `<span class="pv-badge pv-badge--import">${esc(o.dataBadge)}</span>` : "";
    const safety = o.safety
      ? `<div class="pv__safety">${badge}<span class="pv-safety-note">🛡 ${esc(o.safety)}</span></div>`
      : "";
    return `
      <header class="pv__header">
        ${PageTitle(o)}
        <div class="pv__header-right">
          ${actions}
          ${safety}
        </div>
      </header>`;
  }

  /* ---- Sidebar (single shared sidebar for whole app) ---- */
  function Sidebar(opts) {
    const o = opts || {};
    const items = (o.nav || [])
      .map(
        (item) =>
          `<button type="button" class="nav-item${item.id === o.activeId ? " active" : ""}" data-nav="${esc(item.id)}">
            ${item.icon ? `<span class="nav-item__ico">${esc(item.icon)}</span>` : ""}
            <span class="nav-item__label">${esc(item.label)}</span>
            ${item.badge ? `<span class="nav-item__badge">${esc(item.badge)}</span>` : ""}
          </button>`,
      )
      .join("");
    const user = o.user || {};
    return `
      <div class="brand">
        <svg class="tooth" viewBox="0 0 64 64" aria-hidden="true">
          <path d="M20.9 7.8c4.4 0 7.1 2.4 11.1 2.4s6.7-2.4 11.1-2.4c7.8 0 13.2 6.3 13.2 15.1 0 5.4-2.4 10.4-4.7 15.2-2.2 4.6-3.4 9.7-4.4 14.7-.6 3.1-2.5 5.2-5.1 5.2-3.1 0-4.5-2.9-5.6-6.4l-2.1-6.7c-.7-2.3-1.4-3.8-2.4-3.8s-1.7 1.5-2.4 3.8l-2.1 6.7c-1.1 3.5-2.5 6.4-5.6 6.4-2.6 0-4.5-2.1-5.1-5.2-1-5-2.2-10.1-4.4-14.7-2.3-4.8-4.7-9.8-4.7-15.2C7.7 14.1 13.1 7.8 20.9 7.8Z"
            fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div class="brand-copy">
          <strong>${esc(o.brand || "New Ridge Family Financial")}</strong>
          <span class="brand-kicker">${esc(o.kicker || "Financial OS")}</span>
        </div>
      </div>
      <nav class="nav" id="nav">${items}</nav>
      <div class="foot">
        <div class="foot-user">
          <span class="foot-avatar">${esc(user.initials || "NR")}</span>
          <span class="foot-user__copy">
            <strong>${esc(user.name || "New Ridge Owner")}</strong>
            <span>${esc(user.role || "Administrator")}</span>
          </span>
          <span class="foot-chev">⌄</span>
        </div>
        <div class="foot-status">
          <span class="foot-status__dot"></span>
          <span>${esc(o.status || "All systems operational")}</span>
        </div>
      </div>`;
  }

  /* ---- Card ---- */
  function Card(opts) {
    const o = opts || {};
    const head =
      o.title || o.headRight
        ? `<div class="pv-card__head"><h3>${esc(o.title || "")}</h3>${o.headRight ? `<span>${o.headRight}</span>` : ""}</div>`
        : "";
    return `<section class="pv-card${o.className ? " " + esc(o.className) : ""}"${attrs(o.attrs)}>${head}${o.body || ""}</section>`;
  }

  /* ---- Table ---- */
  function Table(opts) {
    const o = opts || {};
    const cols = o.columns || [];
    if (o.loading) return LoadingState({ label: o.loadingLabel || "Loading…" });
    if (o.error) return ErrorState({ message: o.error });
    if (!o.rows || !o.rows.length) {
      return EmptyState({ title: o.emptyTitle || "Nothing here yet", message: o.emptyMessage || "No records to show." });
    }
    const body = o.rows
      .map((row, i) => {
        const cells = (Array.isArray(row) ? row : row.cells) || [];
        const rowKey = Array.isArray(row) ? null : row.key;
        const rc = o.rowClass ? o.rowClass(row, i) : Array.isArray(row) ? "" : row.className || "";
        return `<tr${rowKey != null ? ` data-row="${esc(rowKey)}"` : ""}${rc ? ` class="${esc(rc)}"` : ""}>${cells
          .map((c) => `<td>${c}</td>`)
          .join("")}</tr>`;
      })
      .join("");
    return `
      <div class="pv-table-wrap">
        <table class="pv-table">
          <thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>`;
  }

  /* ---- FormField ---- */
  function FormField(opts) {
    const o = opts || {};
    const id = o.id || o.name;
    const req = o.required ? ' <span class="pv-req">*</span>' : "";
    const errId = `${id}-error`;
    const common = `id="${esc(id)}" name="${esc(o.name || id)}"${o.disabled ? " disabled" : ""}${o.required ? " required" : ""}${o.error ? ` aria-invalid="true" aria-describedby="${esc(errId)}"` : ""}${attrs(o.attrs)}`;
    let control = "";
    if (o.type === "textarea") {
      control = `<textarea class="pv-input" rows="${o.rows || 3}" placeholder="${esc(o.placeholder || "")}" ${common}>${esc(o.value || "")}</textarea>`;
    } else if (o.type === "select") {
      const options = (o.options || [])
        .map((opt) => {
          const val = typeof opt === "string" ? opt : opt.value;
          const label = typeof opt === "string" ? opt : opt.label;
          return `<option value="${esc(val)}"${String(val) === String(o.value) ? " selected" : ""}>${esc(label)}</option>`;
        })
        .join("");
      control = `<select class="pv-input" ${common}>${options}</select>`;
    } else if (o.type === "checkbox") {
      return `<label class="pv-check"><input type="checkbox" ${o.value ? "checked" : ""} ${common}/><span>${esc(o.label)}</span></label>`;
    } else {
      control = `<input class="pv-input" type="${esc(o.type || "text")}" value="${esc(o.value || "")}" placeholder="${esc(o.placeholder || "")}" ${common}/>`;
    }
    return `
      <label class="pv-field" for="${esc(id)}">
        ${o.label ? `<span class="pv-field__label">${esc(o.label)}${req}</span>` : ""}
        ${control}
        <span class="pv-field__error" id="${esc(errId)}">${o.error ? esc(o.error) : ""}</span>
      </label>`;
  }

  /* ---- Modal ---- */
  function Modal(opts) {
    const o = opts || {};
    return `
      <div class="pv-modal${o.open ? " pv-modal--open" : ""}" id="${esc(o.id)}" role="dialog" aria-modal="true" aria-hidden="${o.open ? "false" : "true"}">
        <div class="pv-modal__backdrop" data-modal-close="${esc(o.id)}"></div>
        <div class="pv-modal__panel">
          <div class="pv-modal__head">
            <h3>${esc(o.title || "")}</h3>
            <button class="pv-modal__close" type="button" data-modal-close="${esc(o.id)}" aria-label="Close">×</button>
          </div>
          <div class="pv-modal__body">${o.body || ""}</div>
          ${o.footer ? `<div class="pv-modal__foot">${o.footer}</div>` : ""}
        </div>
      </div>`;
  }

  /* ---- EmptyState ---- */
  function EmptyState(opts) {
    const o = opts || {};
    return `
      <div class="pv-state pv-state--empty" role="status">
        <div class="pv-state__icon">${o.icon || "🗂"}</div>
        <strong class="pv-state__title">${esc(o.title || "Nothing here yet")}</strong>
        <p class="pv-state__msg">${esc(o.message || "")}</p>
        ${o.action || ""}
      </div>`;
  }

  /* ---- LoadingState ---- */
  function LoadingState(opts) {
    const o = opts || {};
    return `
      <div class="pv-state pv-state--loading" role="status" aria-live="polite">
        <div class="pv-spinner" aria-hidden="true"></div>
        <span class="pv-state__msg">${esc(o.label || "Loading…")}</span>
      </div>`;
  }

  /* ---- ErrorState ---- */
  function ErrorState(opts) {
    const o = opts || {};
    const retry = o.retryLabel !== null ? Button({ label: o.retryLabel || "Retry", variant: "secondary", attrs: { "data-retry": "1" } }) : "";
    return `
      <div class="pv-state pv-state--error" role="alert">
        <div class="pv-state__icon">⚠️</div>
        <strong class="pv-state__title">${esc(o.title || "Something went wrong")}</strong>
        <p class="pv-state__msg">${esc(o.message || "Please try again.")}</p>
        ${o.onRetry === false ? "" : retry}
      </div>`;
  }

  return {
    esc,
    attrs,
    AppShell,
    StatusBadge,
    Button,
    PageTitle,
    TopBar,
    Sidebar,
    Card,
    Table,
    FormField,
    Modal,
    EmptyState,
    LoadingState,
    ErrorState,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = UI;
}
if (typeof window !== "undefined") {
  window.UI = UI;
}
