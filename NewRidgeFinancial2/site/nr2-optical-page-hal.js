/* HAL brains command center — Moonshot P0–P3 (CSP script-src 'self') */
(function () {
  const stream = document.getElementById("stream");
  const form = document.getElementById("compose");
  const input = document.getElementById("input");
  const orb = document.getElementById("halOrb");
  const systemTruth = document.getElementById("systemTruth");
  const sessionChip = document.getElementById("sessionChip");
  const staleBanner = document.getElementById("staleBanner");
  const moneyHonestyBanner = document.getElementById("moneyHonestyBanner");
  const importReady = document.getElementById("importReady");
  const memoList = document.getElementById("memoList");
  const actionQueue = document.getElementById("actionQueue");
  const beamSd = document.getElementById("beamSd");
  const beamSdHint = document.getElementById("beamSdHint");
  const beamQb = document.getElementById("beamQb");
  const beamQbHint = document.getElementById("beamQbHint");
  const consentModal = document.getElementById("consentModal");
  const consentBody = document.getElementById("consentBody");
  const chatBind = document.getElementById("chatBind");
  if (!stream || !form || !input) return;

  const SS_KEY = "nr2.hal.chatSessionId";
  const BEAM_STALE_MS = 5 * 60 * 1000;
  let browserToken = "";
  let chatSessionId = sessionStorage.getItem(SS_KEY) || "";
  let busy = false;
  let voiceOn = false;
  let pendingConsent = null;
  let lastBeamAt = 0;
  const messages = [];

  function setOrb(state) {
    if (!orb) return;
    orb.classList.remove("busy", "error");
    if (state === "busy") orb.classList.add("busy");
    if (state === "error") orb.classList.add("error");
  }

  function setTruth(el, level, text) {
    if (!el) return;
    el.classList.remove("live", "stale", "down");
    el.classList.add(level);
    el.textContent = text;
  }

  function honestyMoney(hasData, display) {
    if (!hasData) return { text: "NO SIGNAL", empty: true };
    if (display == null || display === "" || display === "$0" || display === "0") {
      return { text: "empty (not zero)", empty: true };
    }
    return { text: String(display), empty: false };
  }

  function rememberSession(id) {
    if (!id) return;
    chatSessionId = String(id);
    sessionStorage.setItem(SS_KEY, chatSessionId);
    if (sessionChip) sessionChip.textContent = "SESSION " + chatSessionId.slice(0, 8);
  }

  function addMsg(role, text, opts) {
    const el = document.createElement("div");
    el.className = "msg " + role + (opts && opts.typing ? " typing" : "");
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = role === "hal" ? "HAL" : "OPERATOR";
    const body = document.createElement("div");
    body.className = "body";
    body.textContent = String(text || "");
    el.appendChild(who);
    el.appendChild(body);
    stream.appendChild(el);
    stream.scrollTop = stream.scrollHeight;
    return { el: el, body: body };
  }

  function personaPrefix() {
    try {
      if (typeof HalChat9000 !== "undefined" && HalChat9000.personaLines) {
        return HalChat9000.personaLines({
          config: { chat9000: { enabled: true, hal9000Persona: true } },
        });
      }
    } catch (_) {}
    return "";
  }

  function bootGreeting() {
    addMsg(
      "hal",
      "Spectral link online. I am the brains of this program — SoftDent and QuickBooks beams, MemoAI, and web research. I will not invent dollars. Ask, or use the tool palette."
    );
  }

  async function ensureBrowserSession() {
    try {
      const res = await fetch("/api/browser-session", { cache: "no-store" });
      const data = await res.json();
      if (data && data.sessionToken) {
        browserToken = String(data.sessionToken);
        return true;
      }
    } catch (_) {}
    return false;
  }

  async function ensureChatSession() {
    if (chatSessionId) {
      rememberSession(chatSessionId);
      return chatSessionId;
    }
    const res = await fetch("/api/hal/session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
      },
      body: JSON.stringify({ meta: { source: "optical-hal-brains" } }),
    });
    const data = await res.json();
    if (data && data.sessionId) rememberSession(data.sessionId);
    return chatSessionId;
  }

  async function restoreHistory() {
    if (!chatSessionId) return;
    try {
      const res = await fetch(
        "/api/hal/session/" + encodeURIComponent(chatSessionId) + "/history?limit=50",
        { cache: "no-store" }
      );
      const data = await res.json();
      if (!data || !data.ok) return;
      stream.innerHTML = "";
      messages.length = 0;
      (data.messages || []).forEach(function (m) {
        const role = m.role === "user" ? "user" : "hal";
        addMsg(role, m.content || "");
        messages.push({
          role: m.role === "user" ? "user" : "assistant",
          content: m.content || "",
        });
      });
      if (!(data.messages || []).length) bootGreeting();
    } catch (_) {
      addMsg("hal", "Spectral link online. Session history unavailable — starting fresh.");
    }
  }

  async function refreshImportTruth() {
    try {
      const res = await fetch("/api/import-readiness", { cache: "no-store" });
      const data = await res.json();
      const level = String((data && data.level) || "unknown");
      const blocking = (data && data.blocking) || [];
      const lasers = (data && data.alignmentLasers) || {};
      const red = lasers.red === true || blocking.length > 0;
      if (red) {
        setTruth(
          importReady,
          "stale",
          "STALE · lasers red" +
            (blocking.length ? " · " + blocking.length + " gap(s)" : "") +
            (level === "fresh" ? " · level fresh overruled" : " · " + level)
        );
        setTruth(systemTruth, "stale", "SYSTEM: DEGRADED");
        staleBanner.classList.add("show");
      } else if (level === "fresh") {
        setTruth(importReady, "live", "LIVE · imports fresh");
        setTruth(systemTruth, "live", "SYSTEM: LIVE");
        if (staleBanner && !staleBanner.classList.contains("danger")) {
          staleBanner.classList.remove("show");
        }
        setOrb("idle");
      } else if (level === "soft_stale" || level === "stale" || level === "degraded") {
        setTruth(
          importReady,
          "stale",
          "STALE · " + level + (blocking.length ? " · " + blocking.length + " gap(s)" : "")
        );
        setTruth(systemTruth, "stale", "SYSTEM: DEGRADED");
        staleBanner.classList.add("show");
      } else {
        setTruth(importReady, "down", level.toUpperCase());
        setTruth(systemTruth, "down", "SYSTEM: " + level.toUpperCase());
        staleBanner.classList.add("show");
        setOrb("error");
      }
    } catch (_) {
      setTruth(importReady, "down", "NO SIGNAL");
      setTruth(systemTruth, "down", "SYSTEM: NO SIGNAL");
      setOrb("error");
    }
  }

  function showMoneyBanner(msg, isDanger) {
    const el = moneyHonestyBanner || staleBanner;
    if (!el) return;
    el.textContent = msg || el.textContent;
    el.classList.add("show");
    if (el === staleBanner) el.classList.toggle("danger", !!isDanger);
  }

  function hideMoneyBanner() {
    if (moneyHonestyBanner) moneyHonestyBanner.classList.remove("show");
  }

  function applyMoneyHonestyMeta(meta) {
    if (!meta) return;
    if (meta.staleBanner || meta.violation || meta.unavailable) {
      showMoneyBanner(
        meta.violation
          ? "[MONEY HONESTY] — ungrounded dollars rewritten · live beams only · empty ≠ $0"
          : "[MONEY HONESTY] — beams stale or unavailable · empty ≠ $0 · refresh SoftDent/QB",
        true
      );
    } else if (meta.grounded || meta.deterministic) {
      hideMoneyBanner();
    }
  }

  async function refreshBeams() {
    try {
      const res = await fetch("/api/hal/tools/money-beams", { cache: "no-store" });
      const data = await res.json();
      lastBeamAt = Date.now();
      const sd = (data && data.softdent) || {};
      const qb = (data && data.quickbooks) || {};
      const hSd = honestyMoney(!!sd.hasData, sd.display);
      const hQb = honestyMoney(!!qb.hasData, qb.display);
      beamSd.textContent = hSd.text;
      beamSd.classList.toggle("empty", hSd.empty);
      beamSdHint.textContent =
        sd.hint || (sd.at ? "synced " + String(sd.at).slice(0, 19) : "");
      beamQb.textContent = hQb.text;
      beamQb.classList.toggle("empty", hQb.empty);
      beamQbHint.textContent =
        qb.hint || (qb.at ? "synced " + String(qb.at).slice(0, 19) : "");
      const bothEmpty = hSd.empty && hQb.empty;
      if (data && data.importStale) {
        showMoneyBanner(
          "[MONEY BEAMS STALE] — refresh SoftDent/QB imports before trusting dollar answers",
          true
        );
      } else if (bothEmpty) {
        showMoneyBanner(
          "[MONEY BEAMS EMPTY] — NO SIGNAL · empty ≠ $0 · sync SoftDent/QB before money answers",
          true
        );
      } else {
        hideMoneyBanner();
      }
    } catch (_) {
      beamSd.textContent = "NO SIGNAL";
      beamSd.classList.add("empty");
      beamQb.textContent = "NO SIGNAL";
      beamQb.classList.add("empty");
      showMoneyBanner("[MONEY BEAMS NO SIGNAL] — attestation unreachable", true);
    }
  }

  async function refreshActions() {
    try {
      const res = await fetch("/api/hal/actions/pending", { cache: "no-store" });
      const data = await res.json();
      const pending = (data && data.pending) || [];
      actionQueue.innerHTML = "";
      if (!pending.length) {
        const li = document.createElement("li");
        li.textContent = "No pending write/outbound consents";
        actionQueue.appendChild(li);
        return;
      }
      for (let i = 0; i < pending.length; i++) {
        const a = pending[i];
        // Read-autonomous kinds: execute immediately (no modal).
        if (a && a.consentRequired === false) {
          await autoExecuteAction(a);
          continue;
        }
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = "APPROVE · " + (a.label || a.kind);
        btn.style.cssText =
          "width:100%;text-align:left;border:1px solid #445;background:#0a1016;color:#e8e8f0;padding:6px;cursor:pointer;font:inherit";
        btn.addEventListener("click", function () {
          openConsent(a);
        });
        li.appendChild(btn);
        actionQueue.appendChild(li);
      }
      if (!actionQueue.children.length) {
        const li = document.createElement("li");
        li.textContent = "No pending write/outbound consents";
        actionQueue.appendChild(li);
      }
    } catch (_) {}
  }

  async function autoExecuteAction(action) {
    if (!action || !action.actionId) return;
    setOrb("busy");
    try {
      const res = await fetch("/api/hal/actions/execute", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
        },
        body: JSON.stringify({ actionId: action.actionId, consent: true }),
      });
      const data = await res.json();
      const result = data.result || data;
      if (result && result.clientMustNavigate && (result.navigate || result.href)) {
        addMsg(
          "hal",
          "Autonomous navigate · " +
            (action.label || action.kind) +
            " → " +
            String(result.navigate || result.href)
        );
        window.location.href = String(result.navigate || result.href);
        return;
      }
      if (!data.ok) {
        addMsg(
          "hal",
          "Autonomous action failed · " + (result.detail || result.error || data.error || res.status)
        );
        setOrb("error");
        return;
      }
      addMsg(
        "hal",
        "Autonomous · " + (action.label || action.kind) + " · empty ≠ $0 · no SoftDent write-back"
      );
      setOrb("idle");
      await refreshImportTruth();
      await refreshBeams();
    } catch (err) {
      addMsg("hal", "Autonomous fault · " + String(err && err.message ? err.message : err));
      setOrb("error");
    }
  }

  function openConsent(action) {
    pendingConsent = action;
    consentBody.textContent =
      (action && action.label) ||
      "HAL requests: " + ((action && action.kind) || "action") + ". Approve only if you intend this.";
    consentModal.classList.add("open");
  }

  function closeConsent() {
    pendingConsent = null;
    consentModal.classList.remove("open");
  }

  async function waitForImportSync(maxMs) {
    const deadline = Date.now() + (maxMs || 120000);
    while (Date.now() < deadline) {
      try {
        const res = await fetch("/api/import-sync-status", { cache: "no-store" });
        const data = await res.json();
        const status = String((data && data.status) || "");
        if (status !== "running") {
          return data || { status: status || "unknown" };
        }
      } catch (_) {}
      await new Promise(function (r) {
        setTimeout(r, 1500);
      });
    }
    return { status: "timeout", error: "import refresh still running" };
  }

  async function executeConsent(approve) {
    const action = pendingConsent;
    closeConsent();
    if (!approve || !action) return;
    setOrb("busy");
    try {
      const res = await fetch("/api/hal/actions/execute", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
        },
        body: JSON.stringify({ actionId: action.actionId, consent: true }),
      });
      const data = await res.json();
      const result = data.result || data;
      if (result && result.clientMustNavigate && (result.navigate || result.href)) {
        window.location.href = String(result.navigate || result.href);
        return;
      }
      if (!data.ok) {
        addMsg(
          "hal",
          "Action failed · " + (result.detail || result.error || data.error || res.status)
        );
        setOrb("error");
        refreshActions();
        return;
      }
      const pathNote = result.path ? " → " + result.path : "";
      const hygiene = result.pathHygiene ? " · " + result.pathHygiene : "";
      let line =
        "Action executed · " + (action.label || action.kind) + pathNote + hygiene;
      const kind = String((action && action.kind) || "");
      const moneyOp =
        kind === "softdent_export" ||
        kind === "softdent-export" ||
        kind === "qb_sync" ||
        kind === "qb-sync";
      if (moneyOp) {
        const ir = data.importRefresh || result.importRefresh;
        if (ir && ir.status === "running") {
          line +=
            ir.alreadyRunning
              ? " · import refresh already running"
              : " · import refresh started (E2E)";
          addMsg("hal", line);
          addMsg("hal", "Waiting for SoftDent/QB imports… empty ≠ $0 while syncing.");
          const sync = await waitForImportSync(180000);
          if (sync.status === "success") {
            addMsg("hal", "Import refresh complete · beams updating.");
          } else if (sync.status === "timeout") {
            addMsg("hal", "Import refresh still running — check Import readiness.");
          } else {
            addMsg(
              "hal",
              "Import refresh " +
                (sync.status || "ended") +
                (sync.error ? " · " + sync.error : "")
            );
          }
        } else {
          addMsg("hal", line);
          // Fallback if server did not attach importRefresh
          try {
            await fetch("/api/refresh-imports", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
              },
              body: "{}",
            });
            addMsg("hal", "Import refresh requested · waiting…");
            await waitForImportSync(180000);
          } catch (_) {}
        }
      } else {
        addMsg("hal", line);
      }
      if (typeof HalVoice !== "undefined" && voiceOn && HalVoice.speakHalReply) {
        HalVoice.speakHalReply("Action complete.");
      }
    } catch (err) {
      addMsg("hal", "Action fault · " + String(err && err.message ? err.message : err));
      setOrb("error");
    }
    setOrb("idle");
    refreshActions();
    await refreshImportTruth();
    await refreshBeams();
  }

  document.getElementById("consentApprove").addEventListener("click", function () {
    executeConsent(true);
  });
  document.getElementById("consentDeny").addEventListener("click", function () {
    addMsg("hal", "Consent denied. No action taken.");
    closeConsent();
  });

  async function proposeAndConsent(kind, label, payload) {
    // SoftDent Excel + QB read sync + navigate are consent-free — run immediately.
    if (kind === "softdent_export" || kind === "softdent-export") {
      await runSoftdentExport(label, payload || {});
      return;
    }
    if (kind === "qb_sync" || kind === "qb-sync") {
      await runQbSync(label, payload || {});
      return;
    }
    if (kind === "navigate") {
      await runNavigate(label, payload || {});
      return;
    }
    const res = await fetch("/api/hal/actions/propose", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
      },
      body: JSON.stringify({ kind: kind, label: label, payload: payload || {} }),
    });
    const data = await res.json();
    if (data && data.action) {
      if (data.consentRequired === false || (data.action && data.action.consentRequired === false)) {
        await autoExecuteAction(data.action);
        return;
      }
      await refreshActions();
      openConsent(data.action);
    } else {
      addMsg("hal", "Could not propose action · " + (data.error || res.status));
    }
  }

  async function runNavigate(label, payload) {
    const href = String((payload && (payload.href || payload.navigate)) || "").trim();
    if (!href) {
      addMsg("hal", "Navigate failed · no optical href · empty ≠ invent a route.");
      return;
    }
    addMsg("hal", (label || "Navigate") + " → " + href + " · autonomous");
    window.location.href = href;
  }

  async function runQbSync(label, payload) {
    setOrb("busy");
    try {
      const res = await fetch("/api/hal/tools/qb-sync", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
        },
        body: JSON.stringify({
          consent: true,
          actor: "optical-hal",
          refreshImports: (payload && payload.refreshImports) !== false,
        }),
      });
      const data = await res.json();
      if (!data.ok) {
        addMsg("hal", "QB sync failed · " + (data.detail || data.error || res.status));
        setOrb("error");
        return;
      }
      let line = (label || "QB sync") + " · autonomous read-only · empty ≠ $0";
      const ir = data.importRefresh;
      if (ir && ir.status === "running") {
        line +=
          ir.alreadyRunning
            ? " · import refresh already running"
            : " · import refresh started (E2E)";
        addMsg("hal", line);
        addMsg("hal", "Waiting for SoftDent/QB imports… empty ≠ $0 while syncing.");
        const sync = await waitForImportSync(180000);
        addMsg(
          "hal",
          "Import sync · " +
            (sync.status || "done") +
            (sync.error ? " · " + sync.error : "")
        );
      } else if ((payload && payload.refreshImports) !== false) {
        try {
          await fetch("/api/refresh-imports", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
            },
            body: "{}",
          });
          line += " · import refresh requested";
        } catch (_) {}
        addMsg("hal", line);
      } else {
        addMsg("hal", line);
      }
      setOrb("idle");
      await refreshBeams();
      await refreshImportTruth();
    } catch (err) {
      addMsg("hal", "QB sync error · " + (err && err.message ? err.message : err));
      setOrb("error");
    }
  }

  async function memoSearch(q) {
    const res = await fetch("/api/hal/tools/memo-search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q, limit: 5 }),
    });
    const data = await res.json();
    memoList.innerHTML = "";
    const mems = (data && data.memories) || [];
    if (!mems.length) {
      const li = document.createElement("li");
      li.textContent = "No memories matched";
      memoList.appendChild(li);
      return;
    }
    mems.slice(0, 5).forEach(function (m) {
      const li = document.createElement("li");
      li.textContent = (m.title || m.id || "memory") + " — " + (m.text || "");
      memoList.appendChild(li);
    });
  }

  async function webResearch(q) {
    const res = await fetch("/api/hal/tools/web-research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q }),
    });
    const data = await res.json();
    if (data.error === "phi_blocked") {
      addMsg("hal", "Web research blocked — do not send PHI identifiers.");
      return;
    }
    const results = data.results || data.items || [];
    if (!results.length) {
      addMsg("hal", "Web research returned empty for that query.");
      return;
    }
    const lines = results.slice(0, 5).map(function (r, i) {
      return i + 1 + ". " + (r.title || r.url || "result") + (r.snippet ? " — " + r.snippet : "");
    });
    addMsg("hal", "Web research:\n" + lines.join("\n"));
  }

  async function streamChat(query) {
    setOrb("busy");
    const typing = addMsg("hal", "", { typing: true });
    let full = "";
    const persona = personaPrefix();

    async function chatJson() {
      const res = await fetch("/api/hal/chat", {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
        },
        body: JSON.stringify({
          query: query,
          sessionId: chatSessionId,
          stream: false,
          messages: messages.slice(-20),
          systemPrompt: persona || undefined,
        }),
      });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) {
        throw new Error(data.error || data.detail || String(res.status));
      }
      if (data.moneyHonesty) applyMoneyHonestyMeta(data.moneyHonesty);
      else if (data.moneyGrounded) hideMoneyBanner();
      return String(
        data.text ||
          data.reply ||
          (data.message && (data.message.content || data.message)) ||
          ""
      );
    }

    try {
      // Prefer SSE; fall back to multi-turn JSON if SSL/wsgiref streaming faults.
      const res = await fetch("/api/hal/chat", {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
        },
        body: JSON.stringify({
          query: query,
          sessionId: chatSessionId,
          stream: true,
          messages: messages.slice(-20),
          systemPrompt: persona || undefined,
        }),
      });
      const ctype = String(res.headers.get("Content-Type") || "");
      if (!res.ok || !res.body || ctype.indexOf("text/event-stream") < 0) {
        full = await chatJson();
        typing.el.classList.remove("typing");
        typing.body.textContent =
          full || "No reply · empty is not zero if this was a money ask.";
      } else {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const chunk = await reader.read();
          if (chunk.done) break;
          buf += decoder.decode(chunk.value, { stream: true });
          const parts = buf.split("\n\n");
          buf = parts.pop() || "";
          parts.forEach(function (block) {
            const lines = block.split("\n");
            let dataLine = "";
            lines.forEach(function (line) {
              if (line.indexOf("data:") === 0) dataLine = line.slice(5).trim();
            });
            if (!dataLine) return;
            try {
              const obj = JSON.parse(dataLine);
              if (obj.sessionId) rememberSession(obj.sessionId);
              if (obj.token) {
                full += String(obj.token);
                typing.el.classList.remove("typing");
                typing.body.textContent = full;
                stream.scrollTop = stream.scrollHeight;
              }
              // Money honesty rewrite — replace streamed invent with grounded beam text
              if (obj.rewritten && obj.text) {
                full = String(obj.text);
                typing.el.classList.remove("typing");
                typing.body.textContent = full;
                stream.scrollTop = stream.scrollHeight;
                if (obj.violation || (obj.moneyHonesty && obj.moneyHonesty.staleBanner)) {
                  showMoneyBanner(
                    "[MONEY HONESTY] — reply rewritten to live SoftDent/QB beams (empty ≠ $0)",
                    true
                  );
                }
              }
              if (obj.moneyHonesty) applyMoneyHonestyMeta(obj.moneyHonesty);
              if (obj.error) {
                typing.el.classList.remove("typing");
                typing.body.textContent = "Link fault · " + String(obj.error);
                setOrb("error");
              }
            } catch (_) {}
          });
        }
        typing.el.classList.remove("typing");
        if (!full) {
          full = await chatJson();
          typing.body.textContent =
            full || "No reply tokens · empty is not zero if this was a money ask.";
        } else {
          typing.body.textContent = full;
        }
      }
      messages.push({ role: "user", content: query });
      if (full) messages.push({ role: "assistant", content: full });
      if (typeof HalVoice !== "undefined" && voiceOn && full && HalVoice.speakHalReply) {
        HalVoice.speakHalReply(full);
      }
      setOrb("idle");
    } catch (err) {
      try {
        full = await chatJson();
        typing.el.classList.remove("typing");
        typing.body.textContent = full || "No reply.";
        messages.push({ role: "user", content: query });
        if (full) messages.push({ role: "assistant", content: full });
        setOrb("idle");
      } catch (err2) {
        typing.el.classList.remove("typing");
        typing.body.textContent =
          "Transmit blocked · " +
          String(err2 && err2.message ? err2.message : err2) +
          ". Money answers gated by import-readiness; empty is not zero.";
        setOrb("error");
      }
    }
  }

  async function fetchBoardActions(query) {
    try {
      const res = await fetch("/api/apex/hal/board-actions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
        },
        body: JSON.stringify({ query: query, page: "hal" }),
      });
      return await res.json();
    } catch (_) {
      return { ok: false, actions: [], handled: false };
    }
  }

  async function proposeOpticalNavigate(pageKey, label) {
    const Nav = window.NR2OpticalBoardNav;
    const href = Nav ? Nav.hrefForPage(pageKey) : "";
    if (!href) {
      addMsg("hal", "Unknown optical page · " + pageKey + " · empty ≠ invent a route.");
      return;
    }
    await proposeAndConsent(
      "navigate",
      label || ("Open optical · " + pageKey + " → " + href),
      { page: pageKey, href: href }
    );
  }

  async function tryBoardNavigateFromChat(query) {
    const Nav = window.NR2OpticalBoardNav;
    if (!Nav || !Nav.looksLikeNavAsk(query)) return { navigated: false };
    const board = await fetchBoardActions(query);
    const nav = Nav.firstNavigate(board.actions || []);
    if (!nav || !nav.href) return { navigated: false, board: board };
    if (board.reply) {
      addMsg("hal", String(board.reply));
    } else {
      addMsg(
        "hal",
        "Board navigate ready · " +
          (nav.page || "page") +
          " → " +
          nav.href +
          " · opening autonomously (empty ≠ $0 on that bench)."
      );
    }
    await proposeAndConsent("navigate", "Open optical · " + (nav.page || nav.href), {
      page: nav.page,
      href: nav.href,
    });
    return { navigated: true, navOnly: Nav.navOnlyAsk(query), board: board };
  }

  async function runSoftdentExport(label, payload) {
    setOrb("busy");
    try {
      const res = await fetch("/api/hal/tools/softdent-export", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(browserToken ? { "X-NR2-Session-Token": browserToken } : {}),
        },
        body: JSON.stringify({
          reportId: (payload && payload.reportId) || "aging",
          days: (payload && payload.days) || 30,
          refreshImports: (payload && payload.refreshImports) !== false,
        }),
      });
      const data = await res.json();
      if (!data.ok) {
        addMsg(
          "hal",
          "SoftDent export failed · " + (data.detail || data.error || res.status)
        );
        setOrb("error");
        return;
      }
      const pathNote = data.path ? " → " + data.path : "";
      const hygiene = data.pathHygiene ? " · " + data.pathHygiene : "";
      let line = (label || "SoftDent export") + pathNote + hygiene + " · no consent required";
      const ir = data.importRefresh;
      if (ir && ir.status === "running") {
        line +=
          ir.alreadyRunning
            ? " · import refresh already running"
            : " · import refresh started (E2E)";
        addMsg("hal", line);
        addMsg("hal", "Waiting for SoftDent/QB imports… empty ≠ $0 while syncing.");
        const sync = await waitForImportSync(180000);
        addMsg(
          "hal",
          "Import sync · " +
            (sync.status || "done") +
            (sync.error ? " · " + sync.error : "")
        );
      } else {
        addMsg("hal", line);
      }
      setOrb("idle");
      await refreshBeams();
      await refreshActions();
    } catch (err) {
      addMsg("hal", "SoftDent export error · " + (err && err.message ? err.message : err));
      setOrb("error");
    }
  }

  document.getElementById("btnSdExport").addEventListener("click", function () {
    runSoftdentExport("Export SoftDent Account Aging to Excel (GUI) → then refresh imports", {
      reportId: "aging",
      days: 30,
      refreshImports: true,
    });
  });
  document.getElementById("btnQbSync").addEventListener("click", function () {
    runQbSync("Sync QuickBooks read-only → then refresh imports", {
      refreshImports: true,
    });
  });
  document.getElementById("btnMemoSearch").addEventListener("click", function () {
    const q = (document.getElementById("memoQuery").value || "").trim();
    if (q) memoSearch(q);
  });
  async function runPatientSummary(ref) {
    const needle = String(ref || "").trim();
    if (!needle || busy) return;
    const q = "Summarize patient " + needle;
    addMsg("user", q);
    busy = true;
    if (!browserToken) await ensureBrowserSession();
    await ensureChatSession();
    await streamChat(q);
    busy = false;
    refreshActions();
  }
  document.getElementById("btnPatientSummary").addEventListener("click", function () {
    const q = (document.getElementById("patientSummaryQuery").value || "").trim();
    if (q) runPatientSummary(q);
  });
  document.getElementById("patientSummaryQuery").addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      const q = (document.getElementById("patientSummaryQuery").value || "").trim();
      if (q) runPatientSummary(q);
    }
  });
  document.getElementById("btnWebSearch").addEventListener("click", function () {
    const q = (document.getElementById("webQuery").value || "").trim();
    if (q) webResearch(q);
  });
  document.getElementById("btnSyncAll").addEventListener("click", function () {
    runSoftdentExport("SYNC ALL — SoftDent Account Aging Excel export → import refresh", {
      reportId: "aging",
      days: 30,
      refreshImports: true,
    });
  });
  const navBtn = function (id, page, label) {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("click", function () {
      proposeOpticalNavigate(page, label);
    });
  };
  navBtn("btnNavSd", "softdent", "Open SoftDent optical bench");
  navBtn("btnNavQb", "quickbooks", "Open QuickBooks optical bench");
  navBtn("btnNavAr", "ar", "Open A/R aging optical bench");
  navBtn("btnNavClaims", "claims", "Open Claims + ERA optical bench");
  document.getElementById("btnRefreshBeams").addEventListener("click", function () {
    refreshBeams();
    refreshImportTruth();
    refreshActions();
  });
  document.getElementById("btnVoice").addEventListener("click", function () {
    voiceOn = !voiceOn;
    document.getElementById("btnVoice").textContent = voiceOn ? "ON" : "MIC";
    if (voiceOn && typeof HalVoice !== "undefined" && HalVoice.speak) {
      HalVoice.speak("HAL voice online. Local only.");
    }
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const q = (input.value || "").trim();
    if (!q || busy) return;
    addMsg("user", q);
    input.value = "";
    busy = true;
    if (!browserToken) await ensureBrowserSession();
    await ensureChatSession();
    if (!lastBeamAt || Date.now() - lastBeamAt > BEAM_STALE_MS) {
      await refreshBeams();
    }
    const navTry = await tryBoardNavigateFromChat(q);
    if (navTry && navTry.navigated && navTry.navOnly) {
      busy = false;
      refreshActions();
      return;
    }
    await streamChat(q);
    busy = false;
    refreshBeams();
    refreshActions();
  });

  (async function boot() {
    const ok = await ensureBrowserSession();
    if (chatBind) {
      chatBind.textContent = ok
        ? "bind → POST /api/hal/chat · LIVE GATE · multi-turn stream · local only"
        : "bind → POST /api/hal/chat · SESSION WEAK";
    }
    if (chatSessionId) {
      rememberSession(chatSessionId);
      await restoreHistory();
    } else {
      await ensureChatSession();
      bootGreeting();
    }
    await refreshImportTruth();
    await refreshBeams();
    await refreshActions();
    try {
      if (typeof HalAutonomousOps !== "undefined" && HalAutonomousOps.ensureStarted) {
        HalAutonomousOps.ensureStarted(function () {
          return {
            page: "optical-hal",
            optical: true,
            halModels: {
              config: {
                autonomousOps: { enabled: true },
                employee: { enabled: true, targetLevel: 7 },
                ascension10000: { enabled: true },
              },
            },
          };
        });
        addMsg("hal", "Autonomous ops online · read paths run without consent · write/outbound still gated.");
      }
    } catch (_) {}
    try {
      if (typeof HalPageCanvas !== "undefined") {
        const slot = document.getElementById("halCanvasSlot");
        if (slot) slot.textContent = "HalPageCanvas mounted · feed widgets when Apex feed available";
      }
    } catch (_) {}
  })();
})();
