# Moonshot AI — HAL Voice + Report Programming (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_hal_voice_report_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> ask moonshot ai how to program hal voice and report

---

# Verdict — HAL voice + report programming

## 0. Operator Intent (quote; consult-only)

> "ask moonshot ai how to program hal voice and report"

**Interpretation:** Provide a concrete programming plan for HAL **voice** (speak replies, listen/push-to-talk, voice commands that drive UI/actions, neural TTS vs browser speechSynthesis, calibration, interruption, when not to speak) and **report** (shift handoff reports, readiness/smoke reports, spoken briefings), including how voice + report should work together (e.g., "HAL, give me the handoff report" → tool → spoken summary + markdown).  
**Constraint:** Consult-only. Do not apply code. SoftDent READ-ONLY; empty ≠ $0; PHI local TTS / loopback only.

---

## 1. Current State Audit (HalVoice, PTT, TTS, voice commands, handoff/readiness reports)

| Component | Location | State | Notes |
|-----------|----------|-------|-------|
| **HalVoice engine** | `site/hal-voice.js` | **Active** | `HAL_CHAT` profile (rate 1.12, pitch 1.0), `speakHalReply()` (excerpts >480 chars), `speakHalBriefing()` (caps ~420 chars), interruptible speech, `checkNeuralTts()` probes loopback `/api/hal-tts/status`, falls back to `window.speechSynthesis`. |
| **PTT / Voice trigger** | `app.js` | **Basic** | `data-hal-voice-ptt` attribute triggers `HalVoice.speak()` with canned line or `lastBriefing`. Click-to-speak only; no hold-to-talk. |
| **Reply speech sync** | `app.js` | **Active** | After HAL reply, `speakHalReply(full, {interrupt:true})` runs; duration estimation syncs typing animation to speech cadence. Skippable via `window._halRandomQaSkipSpeech`. |
| **Natural voice config** | `app.js` | **Stub** | `naturalVoiceConfig()` reads `halModels` config; not yet wired to TTS selection. |
| **Voice→UI parsers** | `apex_backend.py` | **Active** | `parse_voice_slider_command()` (EBITDA scrubber), `parse_voice_narrative_command()` (claims narratives). Return actions: `navigate`, `focus_widget`, `set_inputs`, `narrative_append`. |
| **Handoff tools** | `hal-agent.js` | **Active** | `clock_out_shift` (POST `/api/employee/clock-out`), `get_last_handoff_report` (GET `/api/shift/handoff/{id}`). Return markdown; no spoken excerpt pipeline yet. |
| **Readiness diagnostics** | `hal-core.js` | **Partial** | Diagnostics exist; no voice trigger or spoken summary. |
| **PHI policy** | `site/data/hal-voice-scripts.json` | **Policy only** | Templates avoid PHI; no runtime enforcement in TTS layer. |
| **Interrupt/cancel** | `hal-voice.js` | **Active** | `cancelSpeech()`, `beginSpeechGeneration()` gen handles barge-in. |

---

## 2. Gap Map

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **Voice→Report commands** | Partial | No parser maps "handoff report", "readiness check", "daily briefing" to tools. Tools exist but lack voice bridge. | Small | `apex_backend.py` new parser |
| **Spoken report excerpts** | Partial | `speakHalBriefing` exists but tools don't generate 1–2 sentence excerpts for speech; full markdown is too long for TTS. | Small | `hal-agent.js` excerpt generator |
| **PHI-safe TTS guards** | Missing | No runtime check prevents speaking PHI (names, SSN, DOB) over browser speechSynthesis (potentially cloud). | Small | `hal-voice.js` regex + flag |
| **Hold-to-talk PTT** | Missing | Only click-to-speak; no `pointerdown`/`pointerup` hold mode for hands-free. | Medium | `app.js` event handlers |
| **Daily ops briefing** | Missing | No unified report combining SoftDent today + QB pending + claims aging + staff on-duty. | Medium | `hal-agent.js` new tool |
| **Voice calibration persistence** | Missing | `HAL_CHAT` rates are hardcoded; not saved to `LocalStore` per-user. | Tiny | `hal-voice.js` load/save |
| **Barge-in (STT during HAL speech)** | Partial | Cancel exists, but no "stop listening" trigger while HAL is speaking (hotword not required). | Small | `hal-voice.js` + Web Speech API |

---

## 3. Target Design — voice + report together

### 3A Speak path (reply → excerpt → TTS; interrupt; mute/skip rules)

1. **Excerpt logic** (existing): `speakHalReply` truncates to `maxReplyChars` (480); `speakHalBriefing` truncates to 420 chars with word-boundary ellipsis.
2. **TTS priority**: 
   - **Primary**: Local neural TTS via `checkNeuralTts()` → `/api/hal-tts` (loopback, PHI-safe).
   - **Fallback**: Browser `speechSynthesis` with `HAL_CHAT.voiceHints` (Microsoft Guy/David), but **only if** content passes PHI filter.
3. **Interrupt**: New speech calls `cancelSpeech()` then `beginSpeechGeneration()` (barge-in allowed).
4. **Skip rules** (evaluated in order):
   - `qaSkipSpeech()` → test mode
   - `options.skipSpeech` → caller override
   - `containsPhi(text) && !options.allowPhi` → PHI guard (new)
   - `independentThoughtActive(options)` → defer to independent thread

### 3B Listen path (PTT / STT → query → tools → spoken report)

```
[PTT Button press] → Web Speech API recognition (interim + final)
        ↓
[Transcript] → POST /api/apex/query (existing endpoint)
        ↓
[apex_backend.py] → parse_voice_report_command() (new)
        ↓
[Tool routed] → clock_out_shift / readiness / daily_ops_briefing
        ↓
[Tool result] → { markdown: "...", spokenExcerpt: "Handoff 47: 3 open claims..." }
        ↓
[Client] → Display markdown in HAL chat + HalVoice.speakHalBriefing(spokenExcerpt)
```

**PTT modes**:
- **Tap**: Existing click behavior (speaks canned line).
- **Hold** (new): `pointerdown` starts recognition, `pointerup` stops; transcript sent as query.

### 3C Report types (handoff, readiness, daily ops briefing) + spoken vs markdown

| Report | Markdown Content | Spoken Excerpt (2–3 sentences) |
|--------|------------------|-------------------------------|
| **Handoff** | Full shift summary, open items list, employee notes | "Shift handoff 47 ready. 3 open insurance claims, 2 pending appointments. Alice clocked out at 5:15 PM." |
| **Readiness** | System health, SoftDent connection, QB sync status, model load | "All systems ready. SoftDent connected. 24B model warm. 12 claims require narratives." |
| **Daily Ops** | Today's schedule, production estimate, aging AR, staff on-duty | "Good morning. 14 patients scheduled today. 3 claims over 30 days. Front desk staffed." |

**Storage**: Markdown saved to `LocalStore` (`nr2:reports:{type}:{date}`) for audit; spoken excerpt ephemeral.

### 3D Voice command grammar (extend parsers vs free-form HAL tools)

Extend `apex_backend.py` with `parse_voice_report_command` (similar pattern to `parse_voice_slider_command`):

**Intent patterns**:
- `r"\b(handoff|shift report|end of shift)\b"` → `{"tool": "clock_out_shift", "intent": "handoff"}`
- `r"\b(readiness|system check|health check|smoke test)\b"` → `{"tool": "readiness_diagnostics", "intent": "readiness"}`
- `r"\b(briefing|morning brief|daily ops|status update)\b"` → `{"tool": "daily_ops_briefing", "intent": "briefing"}`

**Action routing**: Returns `{"type": "run_tool", "tool": "...", "speakResult": true}` → `hal-agent.js` executes and calls `HalVoice.speakHalBriefing()` on result.

**Avoid**: Free-form LLM for command routing (keep deterministic for reliability); use existing parsers.

---

## 4. Coding Plan by Phase (files · paste-ready sketches · validation)

### Phase 1: Voice→Report Bridge (MUST)

**File:** `apex_backend.py`  
**Add after** existing `parse_voice_narrative_command` block:

```python
def parse_voice_report_command(query: str) -> dict[str, Any] | None:
    """
    Parse voice commands for reports.
    Returns: {"tool": "clock_out_shift"|"readiness_diagnostics"|"daily_ops_briefing", "speak": True}
    """
    q = str(query or "").strip().lower()
    if not q:
        return None
    # Avoid collision with existing parsers
    if re.search(r"\b(salary|ebitda|depreciat|scrubber|narrat|dictat)\b", q):
        return None
    
    if re.search(r"\b(handoff|shift report|end of shift|clock out)\b", q):
        return {"tool": "clock_out_shift", "speak": True, "intent": "handoff"}
    if re.search(r"\b(readiness|system check|health check|smoke test)\b", q):
        return {"tool": "readiness_diagnostics", "speak": True, "intent": "readiness"}
    if re.search(r"\b(briefing|morning brief|daily ops|status update)\b", q):
        return {"tool": "daily_ops_briefing", "speak": True, "intent": "briefing"}
    return None
```

**Integration point** in `apex_backend.py` main query handler (after narrative check):

```python
    if not handled:
        voice_report = parse_voice_report_command(query)
        if voice_report:
            actions.append({
                "type": "run_tool",
                "tool": voice_report["tool"],
                "speak": voice_report.get("speak", True)
            })
            notes.append(f"Voice report request: {voice_report['intent']}")
            handled = True
```

**File:** `hal-agent.js`  
**Modify** `clock_out_shift.run` to accept `options` and speak:

```javascript
clock_out_shift: {
  label: "Clock out and generate shift handoff report",
  run: async (ctx, args, options = {}) => {
    const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (!bridge || typeof bridge.loopbackJson !== "function") {
      return { ok: false, summary: "Clock-out requires loopback server." };
    }
    const data = await bridge.loopbackJson("/api/employee/clock-out", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    
    // Generate spoken excerpt (1-2 sentences)
    const openCount = data.openItemCount || 0;
    const spoken = `Handoff ${data.handoffId || 'ready'}: ${openCount} open item${openCount!==1?'s':''}. Shift closed.`;
    
    if (options.speak !== false && typeof HalVoice !== "undefined") {
      HalVoice.speakHalBriefing(spoken, { interrupt: true });
    }
    
    return {
      ok: true,
      summary: data.reportMarkdown || "",
      spokenExcerpt: spoken,
      handoff: data,
    };
  },
},
```

**Validation:** Say "HAL, handoff report" → should trigger tool → display markdown in chat + speak excerpt.

### Phase 2: PHI-Safe TTS Guards (MUST)

**File:** `site/hal-voice.js`  
**Add** PHI detector and guard:

```javascript
function containsPhi(text) {
  // SSN, phone, DOB patterns
  return /\b\d{3}-\d{2}-\d{4}\b|\b\d{3}-\d{3}-\d{4}\b|\b\d{1,2}\/\d{1,2}\/\d{2,4}\b/.test(String(text));
}

function speakHalReply(text, options) {
  options = options || {};
  // PHI guard: block speech unless explicitly allowed
  if (containsPhi(text) && !options.allowPhi) {
    console.warn("[HalVoice] PHI detected in speech; skipping TTS. Set allowPhi:true to override.");
    return { started: false, durationMs: 0, skipped: true, reason: "phi-content-blocked" };
  }
  // ... existing logic
}
```

**Validation:** Attempt to speak "Patient SSN 123-45-6789" → should skip and log warning.

### Phase 3: Hold-to-Talk PTT (SHOULD)

**File:** `app.js`  
**Extend** `data-hal-voice-ptt` handler:

```javascript
// Add to event delegation or button init
const voicePtt = event.target.closest("[data-hal-voice-ptt]");
if (voicePtt) {
  const mode = voicePtt.getAttribute("data-hal-voice-ptt") || "click"; // "click" | "hold"
  
  if (mode === "hold") {
    // Hold-to-talk implementation
    const startRecognition = () => {
      if (window.SpeechRecognition || window.webkitSpeechRecognition) {
        const rec = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        rec.lang = "en-US";
        rec.interimResults = true;
        rec.onresult = (e) => {
          const transcript = Array.from(e.results).map(r => r[0].transcript).join("");
          if (e.results[0].isFinal) {
            // Send to HAL query endpoint
            submitHalVoiceQuery(transcript);
          }
        };
        rec.start();
        window._currentRecognition = rec;
      }
    };
    const stopRecognition = () => {
      if (window._currentRecognition) {
        window._currentRecognition.stop();
        window._currentRecognition = null;
      }
    };
    voicePtt.addEventListener("pointerdown", startRecognition);
    voicePtt.addEventListener("pointerup", stopRecognition);
    voicePtt.addEventListener("pointerleave", stopRecognition);
  } else {
    // Existing click behavior
    const briefing = /* ... existing ... */;
    if (typeof HalVoice !== "undefined" && HalVoice.speak) {
      HalVoice.speak(briefing, { interrupt: true });
    }
  }
  return true;
}
```

**Validation:** Hold button, say "readiness check", release → should trigger readiness tool.

### Phase 4: Unified Daily Ops Briefing (SHOULD)

**File:** `hal-agent.js`  
**Add tool** (queries are READ-ONLY per constraints):

```javascript
daily_ops_briefing: {
  label: "Generate daily operations briefing",
  run: async (ctx, args, options = {}) => {
    const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (!bridge) return { ok: false, summary: "Bridge required." };
    
    // Parallel READ-ONLY queries (SoftDent + QB status)
    const [schedule, claims, staff] = await Promise.all([
      bridge.loopbackJson("/api/softdent/today-schedule"), // READ-ONLY
      bridge.loopbackJson("/api/claims/aging-summary"),     // READ-ONLY
      bridge.loopbackJson("/api/employee/on-duty"),         // READ-ONLY
    ]);
    
    const patientCount = schedule?.count || 0;
    const agingCount = claims?.over30 || 0;
    const staffList = (staff?.names || []).join(", ");
    
    const markdown = `## Daily Ops Briefing - ${new Date().toLocaleDateString()}
- **Schedule**: ${patientCount} patients
- **Claims >30d**: ${agingCount}
- **Staff**: ${staffList || "None logged"}
`;
    const spoken = `Today: ${patientCount} patients scheduled. ${agingCount} claims over 30 days. ${staff?.names?.length || 0} staff on duty.`;
    
    if (options.speak !== false && typeof HalVoice !== "undefined") {
      HalVoice.speakHalBriefing(spoken, { interrupt: true });
    }
    
    return { ok: true, summary: markdown, spokenExcerpt: spoken };
  },
},
```

**Validation:** Voice command "morning briefing" → displays markdown + speaks summary.

### Phase 5: Voice Calibration Persistence (NICE)

**File:** `site/hal-voice.js`  
**Add** load/save:

```javascript
function loadVoiceCalibration() {
  try {
    const saved = localStorage.getItem("nr2:hal:voice:calibration");
    if (saved) {
      const cfg = JSON.parse(saved);
      Object.assign(HAL_CHAT, cfg);
    }
  } catch {}
}

function saveVoiceCalibration(cfg) {
  try {
    localStorage.setItem("nr2:hal:voice:calibration", JSON.stringify(cfg));
  } catch {}
}

// Expose for UI
HalVoice.setCalibration = (rate, pitch) => {
  HAL_CHAT.rate = rate;
  HAL_CHAT.pitch = pitch;
  saveVoiceCalibration({ rate, pitch });
};
```

---

## 5. MUST / SHOULD / NICE ranked table

| Priority | Item | Files | Validation |
|----------|------|-------|------------|
| **MUST** | Voice→Report parser (`parse_voice_report_command`) | `apex_backend.py` | "Handoff report" triggers tool |
| **MUST** | PHI-safe TTS guards | `hal-voice.js` | SSN in text → skip speech |
| **MUST** | Spoken excerpt generation in tools | `hal-agent.js` | Tool returns `spokenExcerpt` |
| **MUST** | Report display + speech integration | `app.js` | Markdown shown + brief spoken |
| **SHOULD** | Hold-to-talk PTT mode | `app.js` | Hold button, speak, release → query |
| **SHOULD** | Daily ops briefing tool | `hal-agent.js` | Aggregates SoftDent/QB/claims |
| **SHOULD** | Readiness diagnostics voice trigger | `hal-agent.js` + `apex_backend.py` | "Readiness check" speaks status |
| **NICE** | Voice calibration persistence | `hal-voice.js` | Rate/pitch saved to LocalStore |
| **NICE** | Report viewer with "Read Summary" button | new `hal-reports.js` | Click to re-speak excerpt |
| **NICE** | Barge-in hotword ("HAL, stop") | `hal-voice.js` | Interrupts current speech |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

### PHI Protection
- **Risk**: Browser `speechSynthesis` may use cloud voices (Google, Microsoft online).  
- **Mitigation**: 
  1. Prefer local neural TTS via `/api/hal-tts` (loopback).
  2. If neural unavailable, `containsPhi()` blocks speech unless `allowPhi:true`.
  3. Never include patient names, DOB, SSN in spoken excerpts; use counts/ids only.

### SoftDent READ-ONLY
- **Guarantee**: All report queries use `GET` or `POST` to read-only endpoints (`/api/softdent/*`, `/api/quickbooks/*` imports). 
- **Honesty**: Empty fields return `null` or omitted keys; UI displays "—" rather than `$0.00`.

### Rollback
- **Feature flags**: Wrap new behavior in `window.NR2_CONFIG.voiceReportsEnabled` (default `false` until validated).
- **TTS failure**: Falls back to text-only display (existing behavior).
- **Parser failure**: Unknown voice commands fall through to general HAL query (no crash).
- **Data safety**: No migrations; purely additive endpoints.

---

## 7. Approval Checklist

- [ ] **Confirm** voice command grammar: "handoff report", "readiness check", "morning briefing", "shift status" acceptable?
- [ ] **Confirm** PHI regex pattern for TTS blocking: `\b\d{3}-\d{2}-\d{4}\b` (SSN), `\b\d{3}-\d{3}-\d{4}\b` (phone), `\b\d{1,2}\/\d{1,2}\/\d{2,4}\b` (DOB) — sufficient or need expansion?
- [ ] **Confirm** local neural TTS endpoint `/api/hal-tts` is production-ready on R9700 loopback.
- [ ] **Approve** Phase 1 (MUST) implementation: voice→report bridge + PHI guards.
- [ ] **Approve** Phase 2 (SHOULD) implementation: hold-to-talk + daily ops briefing, OR defer to backlog.
- [ ] **Set target build ID** for implementation (e.g., `hal-10500`).
- [ ] **Confirm** SoftDent READ-ONLY compliance: all new report queries are read-only.

**DO NOT APPLY until operator says approve / proceed.**