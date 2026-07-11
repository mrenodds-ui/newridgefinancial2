# Moonshot AI — Better HAL Chat Box (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_hal_chatbox_better_consult.py`  
**Apply:** DO NOT APPLY / WAIT FOR OPERATOR APPROVAL.

## Operator request (verbatim)

> ask moonshot ai if there ia a better chat box to use with hal page and report with code dont code until approved

---

# Verdict — Is there a better chat box? 
**Yes** — a redesigned **custom composer (Option B)** beats the current textarea-and-plain-bubbles UX while preserving all HAL command-surface semantics, zero external dependencies, and full offline operation.

## 0. Operator Intent (quote; confirm consult-only)
> "ask moonshot ai if there ia a better chat box to use with hal page and report with code dont code until approved"

**Confirmed CONSULT ONLY** — The following is a specification and paste-ready reference implementation. No files have been modified. Await explicit `approve/proceed` before applying to the working tree.

## 1. Current Chat Box Audit (what works / what hurts)

| Works | Hurts |
|-------|-------|
| Plain-text bubbles keep HAL honest (no markdown hallucinations) | No auto-resize composer → manual drag feels dated |
| Transcript restore + 80-entry cap prevents mem-bloat | No visual receipt when board-actions execute (silent success) |
| Enter↵ send / Shift+Enter newline | Sticky `bottom:0` input can obscure last message on mobile keyboards |
| Suggestion chips give command discoverability | Chip wrap overflow hard-limited to 72px; no scroll affordance |
| `softRenderHalMain` preserves rail across silent refreshes | No copy-to-clipboard for HAL replies (pain for long command outputs) |
| `aria-live="polite"` on message stream | No empty-state welcome when transcript is blank |
| `apex-hal-highlight` overlay integration | Z-index risk: sticky input (z-2) vs highlight overlay (needs z-10+) |

## 2. Options Compared (A keep+polish / B redesigned custom / C library)

| Criteria | A) Keep + Polish | B) Redesigned Custom ⭐ | C) Third-Party Library |
|----------|------------------|------------------------|------------------------|
| **Zero SaaS deps** | ✅ | ✅ | ⚠️ (Most SDKs phone home) |
| **Offline/local** | ✅ | ✅ | ❌ (Often requires WS/HTTP streams) |
| **Board-actions integration** | ✅ Native | ✅ Native | 🔧 Fragile adapter layer |
| **Mobile keyboard handling** | 🔧 Patchy | ✅ Composer pushes content | 🔧 Variable |
| **Bundle size** | ~0 KB | ~0 KB | +30–300 KB |
| **A11y (focus traps)** | Known | Fixed | Unknown |
| **Transcript persistence** | Works | Preserved exactly | Risk of remount wipe |

**Winner: B** — Evolving the existing DOM structure adds auto-resize, command receipts, copy actions, and mobile-safe layout without breaking the `halTranscript[]` lifecycle or introducing supply-chain risk.

## 3. Primary Recommendation (pick one)
**Adopt Option B: The “Apex HAL Console” composer**

Key upgrades:
1. **Auto-resizing textarea** (CSS `field-sizing` + JS fallback) — replaces manual resize handle.
2. **Command receipts** — When `runHalBoardActions` executes, a system bubble appears (“HAL navigated → Claims”).
3. **Copy affordance** — Hover/focus reveals copy button on HAL messages only (user messages are transient input).
4. **Empty state** — Welcome card with hint commands when `halTranscript` is empty.
5. **Mobile-safe footer** — Flex layout removes sticky positioning hazard; uses `overscroll-behavior` containment.
6. **Keyboard chords** — `Ctrl/Cmd + Enter` to send (mirrors Slack/VS Code muscle memory) in addition to existing Enter↵.

## 4. Proposed UI Spec (layout, composer, messages, chips, status)

```
┌─────────────────────────────────────┐
│  Apex Widget Header                 │
├─────────────────────────────────────┤
│  [Empty State] OR                   │
│  ┌─────────────────────────────┐   │
│  │ User: "sync imports"        │   │
│  └─────────────────────────────┘   │
│  ┌─────────────────────────────┐   │
│  │ HAL: "Synced 4 datasets"    │   │
│  │ [Copy]                09:42 │   │
│  └─────────────────────────────┘   │
│  ┌─────────────────────────────┐   │
│  │ HAL ran: refresh_widget     │   │  ← new "receipt" style
│  └─────────────────────────────┘   │
├─────────────────────────────────────┤
│ [Chip] [Chip] [Chip] …   (scroll)   │
├─────────────────────────────────────┤
│ ┌──────────────────┐ ┌──┐          │
│ │ Ask HAL…         │ │▶ │          │  ← auto-grow textarea
│ │                  │ └──┘          │
│ └──────────────────┘               │
│ Local HAL command surface ● Ready  │
└─────────────────────────────────────┘
```

- **Message bubbles**: Max-width 85%, timestamps on hover (`opacity:0 → 1`), role badges (`You` / `HAL`).
- **Chips**: Horizontal scroll (`overflow-x:auto`) with fade mask instead of vertical wrap; preserves muscle memory for quick commands.
- **Status**: Dot indicator (●) pulses amber during `Thinking…` and green when idle.

## 5. Paste-Ready Code (CONSULT ONLY)

### 5.1 HTML Template — Replace `hal-chat` widget block in `apex-core.js`

```html
<!-- CONSULT ONLY: New HAL Chat Structure -->
<header class="apex-widget-header">
  <span class="apex-widget-label">${label}</span>
  <span class="apex-hal-chat__live-indicator" data-hal-live aria-hidden="true"></span>
</header>
<div class="apex-hal-chat" data-hal-chat>
  <!-- Message Log -->
  <div class="apex-hal-chat__messages" 
       data-hal-messages 
       role="log" 
       aria-live="polite" 
       aria-label="HAL conversation history">
    <!-- Empty state injected here when length 0 -->
  </div>

  <!-- Suggestion Chips (horizontal scroll) -->
  <div class="apex-hal-chat__chips-wrap">
    <div class="apex-hal-chat__chips" data-hal-chips role="list" aria-label="Suggested commands"></div>
  </div>

  <!-- Composer -->
  <form class="apex-hal-chat__composer" data-hal-form>
    <div class="apex-hal-chat__input-sizer" data-input-sizer>
      <textarea 
        class="apex-hal-chat__input" 
        data-hal-input 
        rows="1" 
        enterkeyhint="send" 
        placeholder="Ask HAL… (Enter to send · Shift+Enter for new line)" 
        aria-label="Ask HAL"
        maxlength="2000"
      ></textarea>
    </div>
    <button type="submit" class="apex-hal-chat__send" data-hal-send aria-label="Send command">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <line x1="22" y1="2" x2="11" y2="13"></line>
        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
      </svg>
    </button>
  </form>

  <!-- Meta / Status -->
  <div class="apex-hal-chat__meta">
    <span class="apex-hal-chat__hint">${this.escape(this.spec.hint || "Local HAL command surface")}</span>
    <span class="apex-hal-chat__indicator" data-hal-indicator hidden>
      <span class="apex-hal-chat__dot"></span> Thinking…
    </span>
  </div>
</div>
```

### 5.2 CSS — Append/Replace in `apex-tokens.css`

```css
/* CONSULT ONLY: Apex HAL Chat Console v2.0 */

.apex-hal-chat {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  background: var(--apex-elevated, var(--apex-surface));
  border-radius: var(--apex-radius);
}

/* Messages */
.apex-hal-chat__messages {
  flex: 1 1 auto;
  min-height: 120px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scroll-behavior: smooth;
}

/* Empty State */
.apex-hal-chat__empty {
  text-align: center;
  padding: 32px 16px;
  color: var(--apex-text-secondary);
  opacity: 0.8;
}
.apex-hal-chat__empty-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--apex-cyan);
  margin-bottom: 4px;
}
.apex-hal-chat__empty-hint {
  font-size: 11px;
}

/* Message Bubbles */
.apex-hal-chat__msg {
  position: relative;
  font-size: 12px;
  line-height: 1.5;
  padding: 10px 12px;
  border-radius: var(--apex-radius);
  max-width: 88%;
  white-space: pre-wrap;
  word-break: break-word;
  animation: apex-hal-fade-in 180ms ease-out;
}
@keyframes apex-hal-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.apex-hal-chat__msg--user {
  align-self: flex-end;
  background: var(--apex-cyan-dim);
  color: var(--apex-text-primary);
  border: 1px solid rgba(0, 240, 255, 0.25);
}

.apex-hal-chat__msg--hal {
  align-self: flex-start;
  background: var(--apex-surface);
  color: var(--apex-text-secondary);
  border: 1px solid var(--apex-border);
}

.apex-hal-chat__msg--system {
  align-self: center;
  font-size: 11px;
  color: var(--apex-text-secondary);
  background: transparent;
  border: 1px dashed var(--apex-border);
  opacity: 0.9;
}

/* Metadata (timestamp + copy) */
.apex-hal-chat__meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  opacity: 0;
  transition: opacity var(--apex-anim-fast);
  font-size: 10px;
  color: var(--apex-text-secondary);
}
.apex-hal-chat__msg:hover .apex-hal-chat__meta-row,
.apex-hal-chat__msg:focus-within .apex-hal-chat__meta-row {
  opacity: 1;
}

.apex-hal-chat__copy {
  background: transparent;
  border: none;
  color: var(--apex-cyan);
  cursor: pointer;
  padding: 2px 6px;
  font-size: 10px;
  border-radius: 4px;
}
.apex-hal-chat__copy:hover {
  background: var(--apex-cyan-dim);
}

/* Chips (horizontal scroll) */
.apex-hal-chat__chips-wrap {
  flex-shrink: 0;
  position: relative;
  padding: 0 12px;
  margin-bottom: 4px;
}
.apex-hal-chat__chips-wrap::after {
  content: "";
  position: absolute;
  right: 0; top: 0; bottom: 0;
  width: 24px;
  background: linear-gradient(to right, transparent, var(--apex-elevated));
  pointer-events: none;
}
.apex-hal-chat__chips {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  scrollbar-width: none; /* Firefox */
  padding-bottom: 4px;
}
.apex-hal-chat__chips::-webkit-scrollbar {
  display: none;
}

.apex-hal-chat__chip {
  flex: 0 0 auto;
  border: 1px solid var(--apex-border);
  background: var(--apex-surface);
  color: var(--apex-text-secondary);
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 11px;
  cursor: pointer;
  transition: all var(--apex-anim-fast);
  white-space: nowrap;
}
.apex-hal-chat__chip:hover,
.apex-hal-chat__chip:focus {
  color: var(--apex-cyan);
  border-color: var(--apex-cyan-dim);
  background: var(--apex-cyan-dim);
  outline: none;
}

/* Composer (no sticky positioning) */
.apex-hal-chat__composer {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 12px;
  background: var(--apex-elevated);
  border-top: 1px solid var(--apex-border);
}

.apex-hal-chat__input-sizer {
  flex: 1 1 auto;
  position: relative;
}

.apex-hal-chat__input {
  width: 100%;
  field-sizing: content; /* Chrome 123+, Firefox 133+ */
  min-height: 44px;
  max-height: 160px; /* ~6 lines */
  resize: none;
  background: var(--apex-surface);
  border: 1px solid var(--apex-border);
  border-radius: var(--apex-radius);
  color: var(--apex-text-primary);
  padding: 10px 12px;
  font: inherit;
  font-size: 13px;
  line-height: 1.4;
}
/* Fallback for browsers without field-sizing */
@supports not (field-sizing: content) {
  .apex-hal-chat__input {
    overflow-y: auto;
  }
}

.apex-hal-chat__input:focus {
  outline: none;
  border-color: var(--apex-cyan);
  box-shadow: 0 0 0 2px var(--apex-cyan-dim);
}

.apex-hal-chat__send {
  flex: 0 0 auto;
  height: 44px;
  width: 44px;
  display: grid;
  place-items: center;
  border: 1px solid var(--apex-cyan-dim);
  background: var(--apex-cyan-dim);
  color: var(--apex-cyan);
  border-radius: var(--apex-radius);
  cursor: pointer;
  transition: all var(--apex-anim-fast);
}
.apex-hal-chat__send:hover {
  background: rgba(0, 240, 255, 0.28);
}
.apex-hal-chat__send:active {
  transform: translateY(1px);
}

/* Meta / Status */
.apex-hal-chat__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px 12px;
  font-size: 11px;
  color: var(--apex-text-secondary);
}
.apex-hal-chat__hint {
  opacity: 0.8;
}
.apex-hal-chat__indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--apex-cyan);
  font-weight: 500;
}
.apex-hal-chat__indicator[hidden] {
  display: none;
}
.apex-hal-chat__dot {
  width: 6px;
  height: 6px;
  background: var(--apex-cyan);
  border-radius: 50%;
  animation: apex-pulse 1.5s infinite;
}
@keyframes apex-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Live indicator in header */
.apex-hal-chat__live-indicator {
  width: 8px;
  height: 8px;
  background: var(--apex-cyan);
  border-radius: 50%;
  box-shadow: 0 0 0 2px var(--apex-elevated);
}
.apex-hal-chat__live-indicator.is-busy {
  background: #f59e0b; /* amber */
}
```

### 5.3 JS Wiring Deltas — `apex-core.js` modifications

```javascript
// CONSULT ONLY: JS deltas for apex-core.js

// 1. Enhance appendHalMessage to support copy buttons and system role
function appendHalMessage(logEl, role, text, opts = {}) {
  if (!logEl) return;
  const persist = !opts.skipPersist;
  
  // Hide empty state if present
  const empty = logEl.querySelector('[data-hal-empty]');
  if (empty) empty.remove();

  const row = document.createElement("div");
  row.className = `apex-hal-chat__msg apex-hal-chat__msg--${role}`;
  
  // Content
  const content = document.createElement("div");
  content.textContent = text; // Preserve honesty: no HTML injection
  row.appendChild(content);

  // Meta row (timestamp + copy for HAL only)
  if (role === 'hal' || role === 'system') {
    const meta = document.createElement("div");
    meta.className = "apex-hal-chat__meta-row";
    
    const time = document.createElement("time");
    time.dateTime = new Date().toISOString();
    time.textContent = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
    meta.appendChild(time);
    
    if (role === 'hal') {
      const copyBtn = document.createElement("button");
      copyBtn.className = "apex-hal-chat__copy";
      copyBtn.textContent = "Copy";
      copyBtn.type = "button";
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(text);
          copyBtn.textContent = "Copied";
          setTimeout(() => copyBtn.textContent = "Copy", 2000);
        } catch (e) { /* ignore */ }
      };
      meta.appendChild(copyBtn);
    }
    row.appendChild(meta);
  }

  logEl.appendChild(row);
  logEl.scrollTop = logEl.scrollHeight;

  if (persist) {
    halTranscript.push({ role: String(role || "hal"), text: String(text == null ? "" : text) });
    if (halTranscript.length > HAL_TRANSCRIPT_MAX) {
      halTranscript.splice(0, halTranscript.length - HAL_TRANSCRIPT_MAX);
    }
  }
}

// 2. Restore empty state when transcript empty
function restoreHalTranscript(logEl) {
  if (!logEl) return;
  logEl.innerHTML = ''; // Clear (safer than checking childCount)
  
  if (!halTranscript.length) {
    logEl.innerHTML = `
      <div class="apex-hal-chat__empty" data-hal-empty>
        <div class="apex-hal-chat__empty-title">⌘ Command Surface Ready</div>
        <div class="apex-hal-chat__empty-hint">Try: "Sync imports", "Focus claims", or "Explain EBITDA"</div>
      </div>
    `;
    return;
  }
  
  halTranscript.forEach((entry) => {
    appendHalMessage(logEl, entry.role, entry.text, { skipPersist: true });
  });
}

// 3. Auto-resize textarea (fallback for non field-sizing browsers)
function wireHalChatAutoResize(input) {
  if (!input) return;
  const resize = () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  };
  input.addEventListener('input', resize);
  // Initial call
  resize();
}

// 4. Keyboard chords: Ctrl/Cmd+Enter to send
function wireHalChatChords(form, input) {
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
}

// 5. Inject system receipt after board actions (optional UX boost)
// Call this at end of runHalBoardActions
function appendHalReceipt(logEl, actions, results) {
  if (!logEl || !actions?.length) return;
  const summary = actions.map((a,i) => {
    const status = results[i]?.includes('fail') ? '⚠' : '✓';
    return `${status} ${a.type}`;
  }).join(' · ');
  
  appendHalMessage(logEl, 'system', `HAL executed: ${summary}`, { skipPersist: true });
}

// 6. Update wireHalChat initialization (pseudo-patch)
/*
In wireHalChat():
  - Call wireHalChatAutoResize(input) after DOM insertion
  - Call wireHalChatChords(form, input)
  - Use data-hal-indicator for "Thinking…" instead of text replacement:
    - Show: indicator.removeAttribute('hidden')
    - Hide: indicator.setAttribute('hidden','')
*/
```

## 6. Files to Touch + Migration Notes (preserve askHal / board-actions)

| File | Change | Migration Note |
|------|--------|----------------|
| `apex-core.js` | Replace `hal-chat` template string; update `appendHalMessage`, `restoreHalTranscript`, add `wireHalChatAutoResize`, `wireHalChatChords` | **Preserve**: `askHal` global entry point must still target `[data-hal-input]`. `runHalBoardActions` logic untouched except optional receipt injection. |
| `apex-tokens.css` | Replace `.apex-hal-chat*` blocks with v2 styles above | **Preserve**: `.apex-hal-highlight` overlay z-index must remain > chat composer (add `z-index: 20` to highlight if not present). |
| `apex_backend.py` | No change required | Widget spec remains `type: "hal-chat"`; new UI is pure presentation layer. |

**Data integrity**: `halTranscript[]` schema unchanged (`{role,text}`). Existing user sessions will restore correctly into new bubble markup.

## 7. Phased Plan + Validation Gates (DO NOT APPLY)

**Phase 1 — Structure (Template + CSS)**
- Paste new HTML template into widget factory.
- Append CSS to `apex-tokens.css`.
- **Gate**: Visual regression check — empty state appears; bubbles align; chips scroll horizontally.

**Phase 2 — Interaction (JS Wiring)**
- Implement `wireHalChatAutoResize` and `wireHalChatChords`.
- Update `appendHalMessage` with copy-button branch.
- **Gate**: Enter sends; Shift+Enter newline; Ctrl+Enter sends; Copy button writes to clipboard.

**Phase 3 — Integration**
- Optional: Inject `appendHalReceipt` into `runHalBoardActions` completion.
- **Gate**: Execute “sync imports” → observe system receipt bubble; transcript survives soft remount (`loadPage` silent refresh).

**Phase 4 — Mobile & A11y Hardening**
- iOS Safari: Confirm virtual keyboard does not trap scroll (input pushes content up naturally due to flex, not sticky).
- NVDA/VoiceOver: Confirm `role="log"` announces new HAL messages.
- **Gate**: HAL highlight overlay (`apex-hal-highlight`) does not obscure composer (z-index audit).

## 8. Approval Checklist

STOP. Do not proceed to implementation until operator confirms:

- [ ] **Scope**: Option B (custom redesign) approved; Option C (library) explicitly rejected.
- [ ] **Risk Acknowledgment**: Operator accepts that any remount logic (e.g., hard refresh) will wipe transcript (existing behavior preserved).
- [ ] **Mobile**: Operator tested or accepts mobile keyboard scroll behavior changes (sticky→flex).
- [ ] **A11y**: Operator accepts `aria-live="polite"` upgrade to `role="log"` + polite (dual).
- [ ] **Receipts**: Operator wants system receipts for board-actions (yes/no)?
- [ ] **Go/No-Go**: Operator replies with **`approve/proceed`** or requests revision.

**Awaiting operator signal.**