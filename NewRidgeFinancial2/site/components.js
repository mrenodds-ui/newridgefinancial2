/**
 * Shared UI component library for NewRidgeFinancial 2.0.
 *
 * One design system, used by every page. Components return HTML strings that
 * map onto the existing mockup-faithful CSS classes, so the visual look is
 * identical across pages and never duplicated per page.
 *
 * Components: AppShell, Sidebar, PageHero, PageToolbar, CanvasShell, Card, Button, Table,
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

  function renderIcon(icon, className) {
    if (!icon) return "";
    const cls = className || "app-ico";
    if (typeof AppIcons !== "undefined" && AppIcons.isSvg(icon)) {
      return `<span class="${esc(className || "pv-btn-ico")}">${icon}</span>`;
    }
    if (String(icon).includes("<svg")) {
      return `<span class="${esc(className || "pv-btn-ico")}">${icon}</span>`;
    }
    return `<span class="${esc(className || "pv-btn-ico")}">${esc(icon)}</span>`;
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
    const icon = o.icon ? renderIcon(o.icon, "pv-btn-ico") : "";
    const tag = variant === "link" ? "button" : "button";
    return `<${tag} class="${cls}${o.className ? " " + esc(o.className) : ""}" type="${esc(o.type || "button")}"${o.disabled ? " disabled" : ""}${attrs(o.attrs)}>${icon}${esc(o.label)}</${tag}>`;
  }

  /* ---- Button ---- */
  function Sidebar(opts) {
    const o = opts || {};
    const mockupEpoch =
      typeof PageSchema !== "undefined" &&
      PageSchema.LAYOUT_EPOCH === "moonshot-mockup" &&
      !(typeof window !== "undefined" && window.NR2_WORKSTATION_ONLY);
    const MC =
      (typeof MoonshotMockupChrome !== "undefined" && MoonshotMockupChrome) ||
      (typeof globalThis !== "undefined" && globalThis.MoonshotMockupChrome) ||
      null;
    if (mockupEpoch && MC && typeof MC.renderNavRail === "function") {
      return MC.renderNavRail(o.activeId);
    }
    if (mockupEpoch) {
      return '<div class="sidebar__boot-error">Moonshot mockup nav required (nr2-moonshot-mockup-chrome.js).</div>';
    }
    if (Array.isArray(o.navGroups) && o.navGroups.length) {
      const groups = o.navGroups
        .map((group) => {
          const items = (group.pages || [])
            .map((pageId) => {
              const page = (o.pages && o.pages[pageId]) || null;
              if (!page) return "";
              const active = pageId === o.activeId;
              const accent = page.accent || "gold";
              return `<button type="button" class="nav-item nav-item--accent-${esc(accent)}${active ? " active" : ""}" data-nav="${esc(pageId)}">
                ${typeof AppIcons !== "undefined" ? renderIcon(AppIcons.nav(pageId), "nav-item__ico") : ""}
                <span class="nav-item__label">${esc(page.label || pageId)}</span>
                ${page.badge ? `<span class="nav-item__badge">${esc(page.badge)}</span>` : ""}
              </button>`;
            })
            .join("");
          if (!items) return "";
          return `<div class="nav-group"><p class="nav-group__title">${esc(group.section)}</p>${items}</div>`;
        })
        .join("");
      const practice = o.practice || {};
      return `
        <div class="brand brand--canvas">
          <span class="brand-mark" aria-hidden="true">NR</span>
          <div class="brand-copy">
            <strong>${esc(practice.name || o.brand || "New Ridge Family Dental")}</strong>
            <span class="brand-kicker">${esc(practice.location || o.kicker || "Ridgefield, Connecticut")}</span>
          </div>
        </div>
        <nav class="nav nav--grouped" id="nav">${groups}</nav>
        ${sidebarFoot(o)}`;
    }
    const items = (o.nav || [])
      .map(
        (item) =>
          `<button type="button" class="nav-item${item.id === o.activeId ? " active" : ""}" data-nav="${esc(item.id)}">
            ${item.icon ? renderIcon(item.icon, "nav-item__ico") : ""}
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
      ${sidebarFoot(o)}`;
  }

  function sidebarFoot(o) {
    const user = o.user || {};
    return `
      <div class="foot">
        <div class="foot-user">
          <span class="foot-avatar">${esc(user.initials || "NR")}</span>
          <span class="foot-user__copy">
            <strong>${esc(user.name || "New Ridge Owner")}</strong>
            <span>${esc(user.role || "Administrator")}</span>
          </span>
          <span class="foot-chev">${typeof AppIcons !== "undefined" ? AppIcons.ui("chevronDown") : ""}</span>
        </div>
        <div class="foot-status">
          <span class="foot-status__dot"></span>
          <span>${esc(o.status || "All systems operational")}</span>
        </div>
      </div>`;
  }

  function PageHero(opts) {
    const o = opts || {};
    const accent = o.accent || "gold";
    const trailing = [o.dataBadge, o.periodLabel].filter(Boolean).join("");
    return `
      <header class="pv-canvas-hero pv-canvas-hero--${esc(accent)}">
        <span class="pv-canvas-hero__accent" aria-hidden="true"></span>
        <div class="pv-canvas-hero__main">
          <p class="pv-canvas-hero__label">${esc(o.label || "")}</p>
          <h1 class="pv-canvas-hero__title">${esc(o.title || "")}</h1>
          <p class="pv-canvas-hero__subtitle">${esc(o.subtitle || "")}</p>
        </div>
        ${trailing ? `<div class="pv-canvas-hero__meta">${trailing}</div>` : ""}
      </header>`;
  }

  function PageToolbar(opts) {
    const o = opts || {};
    const filters = (o.filters || [])
      .map((label, i) => `<span class="pv-filter-pill${i === 0 ? " is-active" : ""}">${esc(label)}</span>`)
      .join("");
    const actions = o.actions ? `<div class="pv-canvas-toolbar__actions">${o.actions}</div>` : "";
    return `
      <div class="pv-canvas-toolbar">
        <div class="pv-canvas-toolbar__filters">${filters}</div>
        ${actions}
      </div>`;
  }

  function PageInsight(opts) {
    const o = opts || {};
    const tone = o.tone || "info";
    return `
      <aside class="pv-canvas-insight ms-hal-insight pv-canvas-insight--${esc(tone)}" role="status" aria-label="HAL insight">
        <div class="ms-hal-insight__icon" aria-hidden="true">AI</div>
        <div class="ms-hal-insight__body">
          <strong>${esc(o.title || "")}</strong>
          <p>${esc(o.body || "")}</p>
        </div>
      </aside>`;
  }

  function CanvasShell(opts) {
    const o = opts || {};
    return `
      <div class="pv-canvas-shell">
        ${o.hero || ""}
        ${o.toolbar || ""}
        ${o.insight || ""}
        ${o.strip || ""}
        ${o.commands || ""}
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
            <button class="pv-modal__close" type="button" data-modal-close="${esc(o.id)}" aria-label="Close">${typeof AppIcons !== "undefined" ? AppIcons.ui("close") : ""}</button>
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
        <div class="pv-state__icon">${o.icon || (typeof AppIcons !== "undefined" ? AppIcons.ui("empty") : "")}</div>
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
        <div class="pv-state__icon">${typeof AppIcons !== "undefined" ? AppIcons.ui("error") : ""}</div>
        <strong class="pv-state__title">${esc(o.title || "Something went wrong")}</strong>
        <p class="pv-state__msg">${esc(o.message || "Please try again.")}</p>
        ${o.onRetry === false ? "" : retry}
      </div>`;
  }

  function CanvasCommandStrip(opts) {
    const o = opts || {};
    const cmds = (o.commands || [])
      .map(
        (cmd) =>
          `<button type="button" class="pv-canvas-command__pill" data-hal-page="${esc(o.pageId || "")}" data-hal-cmd="${esc(cmd)}">${esc(cmd)}</button>`,
      )
      .join("");
    return `<div class="pv-canvas-command">
      <input class="pv-canvas-command__input" type="text" placeholder="Ask HAL or choose an action…" disabled />
      <div class="pv-canvas-command__pills">${cmds}</div>
    </div>`;
  }

  return {
    esc,
    attrs,
    AppShell,
    StatusBadge,
    Button,
    Sidebar,
    PageHero,
    PageToolbar,
    PageInsight,
    CanvasShell,
    CanvasCommandStrip,
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
if (typeof globalThis !== "undefined") {
  globalThis.UI = UI;
}
if (typeof window !== "undefined") {
  window.UI = UI;
}
