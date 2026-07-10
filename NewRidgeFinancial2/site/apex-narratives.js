/**
 * NR2-Apex Interactive Narratives — starship document bridge
 * Build: hal-10360 — voice-to-narrative + payer-specific appeal templates
 */
(function () {
  "use strict";

  const PAGE_TITLES = {
    narratives: "Narratives",
  };

  const DEFAULT_SECTIONS = [
    { id: "intro", title: "Introduction", content: "" },
    { id: "findings", title: "Findings", content: "" },
    { id: "treatment", title: "Treatment Plan", content: "" },
    { id: "notes", title: "Clinical Notes", content: "" },
    { id: "followup", title: "Follow-up", content: "" },
    { id: "insurance", title: "Insurance Narrative", content: "" },
  ];

  const TEMPLATES = {
    "new-patient":
      "New patient examination.\n\nChief complaint:\n\nClinical findings:\n\nAssessment:\n\nPlan:",
    restorative:
      "Restorative procedure note.\n\nTooth/area:\n\nMaterials:\n\nOcclusion checked:\n\nPost-op instructions:",
    perio:
      "Periodontal maintenance.\n\nProbing summary:\n\nBleeding points:\n\nHome care reviewed:\n\nNext visit:",
  };

  let sections = DEFAULT_SECTIONS.map((s) => ({ ...s }));
  let activeId = "intro";
  let lastSuggestion = "";
  let sources = { clinicalNotes: [], claims: [], insurance: [], lastImport: "" };
  let selectedNotes = new Set();
  let selectedClaimId = "";
  let selectedPayerId = "";
  let lockedContextId = "";
  let contextHint = "";
  let payerTemplates = [];
  let selectedTemplateId = "";
  let voiceListening = false;
  let voiceRecognition = null;

  function escape(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fetchFn(url, opts) {
    if (window.Apex && window.Apex.apexFetch) {
      return window.Apex.apexFetch(url, opts);
    }
    return fetch(url, Object.assign({ credentials: "same-origin" }, opts || {}));
  }

  function activeSection() {
    return sections.find((s) => s.id === activeId) || sections[0];
  }

  function progressPct() {
    const idx = Math.max(0, sections.findIndex((s) => s.id === activeId));
    return Math.round(((idx + 1) / Math.max(sections.length, 1)) * 100);
  }

  function contextChipsHtml() {
    const chips = [];
    if (selectedClaimId) chips.push(`<span class="narr-chip">Claim ${escape(selectedClaimId)}</span>`);
    if (selectedPayerId) chips.push(`<span class="narr-chip">Payer ${escape(selectedPayerId)}</span>`);
    selectedNotes.forEach((id) => chips.push(`<span class="narr-chip">Note ${escape(id)}</span>`));
    if (!chips.length) return `<p class="narr-suggestion__text">Select clinical notes, a claim, and a payer below.</p>`;
    return `<div class="narr-context-chips">${chips.join("")}</div>`;
  }

  function sourceListHtml(kind) {
    if (kind === "clinical") {
      const rows = sources.clinicalNotes || [];
      if (!rows.length) {
        return `<div class="narr-data-placeholder">Import SoftDent clinical notes to enable selection</div>`;
      }
      return `<div class="narr-source-list" id="narr-src-clinical">${rows
        .map((n) => {
          const id = String(n.noteId || "");
          const on = selectedNotes.has(id) ? " is-selected" : "";
          return `<label class="narr-source-item${on}" data-note-id="${escape(id)}">
            <input type="checkbox" data-sel-note value="${escape(id)}" ${selectedNotes.has(id) ? "checked" : ""} />
            <span><strong>${escape(n.patientName || "—")}</strong>
            <span>${escape(id)} · ${escape(n.date || "")}</span>
            <span>${escape(n.snippet || "")}</span></span></label>`;
        })
        .join("")}</div>`;
    }
    if (kind === "claims") {
      const rows = sources.claims || [];
      if (!rows.length) {
        return `<div class="narr-data-placeholder">Import SoftDent claims to enable selection</div>`;
      }
      return `<div class="narr-source-list" id="narr-src-claims">${rows
        .map((c) => {
          const id = String(c.claimId || "");
          const on = selectedClaimId === id ? " is-selected" : "";
          return `<label class="narr-source-item${on}" data-claim-pick="${escape(id)}">
            <input type="radio" name="narr-claim" data-sel-claim value="${escape(id)}" ${
            selectedClaimId === id ? "checked" : ""
          } />
            <span><strong>${escape(id)}</strong>
            <span>${escape(c.patientName || "—")} · ${escape(c.date || "")}${
            c.bucket ? " · " + escape(String(c.bucket)) + "d" : ""
          }</span></span></label>`;
        })
        .join("")}</div>`;
    }
    const rows = sources.insurance || [];
    if (!rows.length) {
      return `<div class="narr-data-placeholder">Payer list appears after SoftDent claims import includes Payer</div>`;
    }
    return `<div class="narr-source-list" id="narr-src-insurance">${rows
      .map((p) => {
        const id = String(p.payerId || p.payerName || "");
        const on = selectedPayerId === id ? " is-selected" : "";
        return `<label class="narr-source-item${on}">
          <input type="radio" name="narr-payer" data-sel-payer value="${escape(id)}" ${
          selectedPayerId === id ? "checked" : ""
        } />
          <span><strong>${escape(p.payerName || id)}</strong>
          <span>${escape(String(p.claimCount || 0))} claim(s)</span></span></label>`;
      })
      .join("")}</div>`;
  }

  function shellHtml() {
    const nodes = sections
      .map(
        (s) =>
          `<button type="button" class="narr-scrubber__node${s.id === activeId ? " active" : ""}" data-section="${escape(
            s.id
          )}">${escape(s.title)}</button>`
      )
      .join("");
    const outline = sections
      .map(
        (s) =>
          `<li data-section="${escape(s.id)}" class="${s.id === activeId ? "active" : ""}">${escape(s.title)}</li>`
      )
      .join("");
    const sec = activeSection();
    const importStamp = sources.lastImport
      ? `Last updated: ${escape(sources.lastImport)}`
      : "Last updated: — (import SoftDent)";
    return `
<div class="narratives-bridge" id="narratives-bridge">
  <div class="narr-scrubber">
    <div class="narr-scrubber__track" id="narr-timeline">${nodes}</div>
    <div class="narr-scrubber__progress" id="narr-progress"><span style="width:${progressPct()}%"></span></div>
  </div>
  <div class="narr-workspace">
    <aside class="narr-outline">
      <h3 class="narr-panel-title">Sections</h3>
      <ul class="narr-outline__list" id="narr-outline-list">${outline}</ul>
      <button type="button" class="apex-btn apex-btn--secondary" id="btn-add-section">+ Add Section</button>
    </aside>
    <main class="narr-composer">
      <div class="narr-composer__toolbar">
        <button type="button" class="apex-btn" id="btn-rewrite-hal">HAL Rewrite</button>
        <button type="button" class="apex-btn" id="btn-insert-template">Insert Template</button>
        <button type="button" class="apex-btn${voiceListening ? " is-live" : ""}" id="btn-voice-narr" title="Voice to narrative (browser mic)">
          ${voiceListening ? "● Listening…" : "🎙 Voice"}
        </button>
        <div class="narr-composer__status" id="composer-status">Draft · ${escape(sec.title)}</div>
      </div>
      <div id="narr-locked-chips">${contextChipsHtml()}</div>
      <textarea class="narr-composer__editor" id="narr-editor" placeholder="Compose clinical narrative for ${escape(
        sec.title
      )}. Lock context, then use insurance narrative types for payer letters. Dollar amounts are never invented.">${escape(
      sec.content || ""
    )}</textarea>
    </main>
    <aside class="narr-context" id="narr-context-panel">
      <h3 class="narr-panel-title">Context</h3>
      <p class="narr-suggestion__text" id="patient-data-placeholder">${escape(
        contextHint || "Loading import-backed context…"
      )}</p>
      <p class="narr-suggestion__text">${importStamp}</p>
      <div class="narr-context__section">
        <h4>Clinical Notes</h4>
        ${sourceListHtml("clinical")}
      </div>
      <div class="narr-context__section">
        <h4>Claims</h4>
        ${sourceListHtml("claims")}
      </div>
      <div class="narr-context__section">
        <h4>Insurance</h4>
        ${sourceListHtml("insurance")}
      </div>
      <button type="button" class="apex-btn apex-btn--secondary" id="btn-lock-context">Lock Context</button>
      <div class="narr-context__section">
        <h4>Insurance Narrative (HAL)</h4>
        <select class="narr-ins-type" id="ins-narr-type">
          <option value="appeal">Appeal Letter</option>
          <option value="medical-necessity">Medical Necessity</option>
          <option value="attachment-cover">Attachment Cover Letter</option>
          <option value="prior-auth">Prior Authorization</option>
        </select>
        <select class="narr-ins-type" id="ins-payer-template" title="Payer-specific appeal template">
          <option value="">Payer template (auto from selected payer)…</option>
          ${payerTemplates
            .map(
              (t) =>
                `<option value="${escape(t.id || "")}" ${
                  selectedTemplateId === t.id ? "selected" : ""
                }>${escape(t.displayName || t.id)}${t.operatorMaintained ? " ★" : ""}</option>`
            )
            .join("")}
        </select>
        <input class="narr-ins-type" id="ins-denial-reason" type="text" placeholder="Denial reason (appeals)" />
        <label class="narr-consent">
          <input type="checkbox" id="ins-consent" />
          <span>I confirm this narrative is based solely on imported clinical data and accurate to the best of my knowledge.</span>
        </label>
        <button type="button" class="apex-btn apex-btn--primary" id="btn-ins-generate">Generate Payer Draft</button>
        <p class="narr-suggestion__text">Voice: say “dictate findings: …” to HAL, or use 🎙 Voice. ★ = operator-maintained template.</p>
      </div>
      <div class="narr-context__section">
        <h4>HAL Suggestions</h4>
        <div class="narr-suggestion" id="narr-hal-suggestion">
          <p class="narr-suggestion__text" id="narr-suggestion-text">Select text or generate an insurance draft.</p>
          <button type="button" class="apex-btn apex-btn--small" id="btn-apply-suggestion" disabled>Apply</button>
        </div>
      </div>
      <div class="narr-context__section">
        <h4>Templates</h4>
        <select class="narr-select" id="template-select">
          <option value="">Select template…</option>
          <option value="new-patient">New Patient Exam</option>
          <option value="restorative">Restorative Procedure</option>
          <option value="perio">Periodontal Maintenance</option>
        </select>
      </div>
      <div class="narr-actions">
        <button type="button" class="apex-btn apex-btn--primary" id="btn-generate-packet">Generate Print Packet</button>
        <button type="button" class="apex-btn" id="btn-save-draft">Save Draft (session)</button>
      </div>
    </aside>
  </div>
</div>`;
  }

  function persistEditor() {
    const editor = document.getElementById("narr-editor");
    const sec = activeSection();
    if (editor && sec) sec.content = editor.value;
  }

  function setActive(id) {
    persistEditor();
    if (!sections.some((s) => s.id === id)) return;
    activeId = id;
    remount();
  }

  function remount() {
    const stage = document.getElementById("apex-stage");
    if (!stage) return;
    stage.className = "apex-stage apex-mosaic";
    stage.innerHTML = shellHtml();
    wire(stage);
  }

  function applySeed() {
    try {
      const raw = sessionStorage.getItem("nr2-apex-narrative-seed");
      if (!raw) return;
      sessionStorage.removeItem("nr2-apex-narrative-seed");
      const seed = JSON.parse(raw);
      if (seed.claimId) selectedClaimId = String(seed.claimId);
      if (seed.payer) selectedPayerId = String(seed.payer).trim().toLowerCase();
      if (Array.isArray(seed.claimIds) && seed.claimIds.length) {
        selectedClaimId = String(seed.claimIds[0]);
        activeId = "insurance";
        const sec = sections.find((s) => s.id === "insurance");
        if (sec) {
          sec.content =
            (sec.content || "") +
            `\n\nBulk appeal seed (import-backed claim IDs):\n` +
            seed.claimIds.map((id) => `- ${id}`).join("\n") +
            "\n\nGenerate one appeal per claim with consent, or compose a combined packet manually.\n";
        }
      }
      if (seed.claimId) activeId = "insurance";
    } catch (_err) {
      /* ignore */
    }
  }

  async function loadStructure() {
    try {
      const res = await fetchFn("/api/apex/narratives/structure");
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data.sections) && data.sections.length) {
        sections = data.sections.map((s, i) => ({
          id: String(s.id || `sec-${i}`),
          title: String(s.title || `Section ${i + 1}`),
          content: s.content === "[PLACEHOLDER]" ? "" : String(s.content || ""),
        }));
        if (!sections.some((s) => s.id === activeId)) activeId = sections[0].id;
      }
      if (data.sources && typeof data.sources === "object") {
        sources = {
          clinicalNotes: Array.isArray(data.sources.clinicalNotes) ? data.sources.clinicalNotes : [],
          claims: Array.isArray(data.sources.claims) ? data.sources.claims : [],
          insurance: Array.isArray(data.sources.insurance) ? data.sources.insurance : [],
          lastImport: String(data.sources.lastImport || ""),
        };
        payerTemplates = Array.isArray(data.sources.payerTemplates) ? data.sources.payerTemplates : [];
      }
      contextHint = String(data.contextHint || data.sourceNote || "");
    } catch (_err) {
      /* keep defaults */
    }
  }

  async function lockContext() {
    try {
      const res = await fetchFn("/api/apex/narratives/context", {
        method: "POST",
        body: JSON.stringify({
          clinicalNoteIds: Array.from(selectedNotes),
          claimId: selectedClaimId || null,
          payerId: selectedPayerId || null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      lockedContextId = String((data && data.contextId) || "");
      const status = document.getElementById("composer-status");
      if (status) {
        status.textContent = lockedContextId
          ? `Context locked · ${lockedContextId}`
          : `Context lock failed`;
      }
      const chips = document.getElementById("narr-locked-chips");
      if (chips) chips.innerHTML = contextChipsHtml();
    } catch (err) {
      window.alert(String((err && err.message) || err));
    }
  }

  async function generateInsurance() {
    const consent = document.getElementById("ins-consent");
    const typeEl = document.getElementById("ins-narr-type");
    const denialEl = document.getElementById("ins-denial-reason");
    const out = document.getElementById("narr-suggestion-text");
    const applyBtn = document.getElementById("btn-apply-suggestion");
    if (!consent || !consent.checked) {
      if (out) out.textContent = "Consent checkbox required before generating an insurance narrative.";
      return;
    }
    if (out) out.textContent = "HAL composing payer draft from locked import context…";
    if (applyBtn) applyBtn.disabled = true;
    try {
      const res = await fetchFn("/api/apex/hal/narrative-generate", {
        method: "POST",
        body: JSON.stringify({
          contextId: lockedContextId || undefined,
          clinicalNoteIds: Array.from(selectedNotes),
          claimId: selectedClaimId || null,
          payerId: selectedPayerId || null,
          type: (typeEl && typeEl.value) || "appeal",
          denialReason: (denialEl && denialEl.value) || "",
          templateId: selectedTemplateId || (document.getElementById("ins-payer-template") || {}).value || null,
          operatorConsent: true,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) {
        lastSuggestion = "";
        if (out) out.textContent = data.error || "Insurance narrative generation failed.";
        return;
      }
      lastSuggestion = String(data.draftText || "");
      if (out) out.textContent = lastSuggestion.slice(0, 400) + (lastSuggestion.length > 400 ? "…" : "");
      if (applyBtn) applyBtn.disabled = !lastSuggestion;
      // Prefer insurance section
      if (sections.some((s) => s.id === "insurance")) {
        activeId = "insurance";
      }
    } catch (err) {
      if (out) out.textContent = `HAL generate failed: ${String((err && err.message) || err)}`;
    }
  }

  async function rewriteHal() {
    const editor = document.getElementById("narr-editor");
    const out = document.getElementById("narr-suggestion-text");
    const applyBtn = document.getElementById("btn-apply-suggestion");
    if (!editor) return;
    persistEditor();
    const selected = editor.value.substring(editor.selectionStart, editor.selectionEnd);
    const text = (selected || editor.value || "").trim();
    if (!text) {
      if (out) out.textContent = "Enter or select text to rewrite.";
      return;
    }
    if (out) out.textContent = "HAL rewriting…";
    if (applyBtn) applyBtn.disabled = true;
    try {
      const res = await fetchFn("/api/apex/narratives/generate", {
        method: "POST",
        body: JSON.stringify({
          text,
          section: activeId,
          style: "clinical",
        }),
      });
      const data = await res.json().catch(() => ({}));
      lastSuggestion = String((data && (data.suggestion || data.text || data.reply || data.draftText)) || "");
      if (!lastSuggestion) lastSuggestion = "HAL returned no rewrite for that selection.";
      if (out) out.textContent = lastSuggestion;
      if (applyBtn) applyBtn.disabled = !lastSuggestion;
    } catch (err) {
      if (out) out.textContent = `HAL rewrite failed: ${String((err && err.message) || err)}`;
    }
  }

  function applySuggestion() {
    const editor = document.getElementById("narr-editor");
    if (!editor || !lastSuggestion) return;
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    if (start !== end) {
      editor.setRangeText(lastSuggestion, start, end, "end");
    } else {
      editor.value = lastSuggestion;
    }
    persistEditor();
    const status = document.getElementById("composer-status");
    if (status) status.textContent = `Draft · ${activeSection().title} · HAL applied · human review required`;
  }

  function insertTemplate() {
    const sel = document.getElementById("template-select");
    const editor = document.getElementById("narr-editor");
    if (!sel || !editor) return;
    const key = sel.value;
    if (!key || !TEMPLATES[key]) return;
    const tpl = TEMPLATES[key];
    if (editor.value.trim()) {
      editor.value = `${editor.value.trim()}\n\n${tpl}`;
    } else {
      editor.value = tpl;
    }
    persistEditor();
  }

  async function generatePacket() {
    persistEditor();
    try {
      const res = await fetchFn("/api/apex/narratives/print-packet", {
        method: "POST",
        body: JSON.stringify({
          sections: sections,
          activeSection: activeId,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (data && data.url) {
        window.open(data.url, "_blank", "noopener,width=720,height=640");
        return;
      }
      if (window.Apex && typeof window.Apex.printPage === "function") {
        window.Apex.printPage();
      } else {
        window.print();
      }
    } catch (_err) {
      window.print();
    }
  }

  function applyVoiceText(sectionId, text, mode) {
    const sid = String(sectionId || activeId || "notes");
    const body = String(text || "").trim();
    if (!body) return false;
    if (!sections.some((s) => s.id === sid)) {
      sections.push({ id: sid, title: sid, content: "" });
    }
    persistEditor();
    const sec = sections.find((s) => s.id === sid);
    if (!sec) return false;
    if (mode === "replace") sec.content = body;
    else sec.content = sec.content ? `${sec.content.trim()}\n\n${body}` : body;
    activeId = sid;
    remount();
    const status = document.getElementById("composer-status");
    if (status) status.textContent = `Voice · ${sec.title} · ${mode || "append"}`;
    return true;
  }

  function toggleVoiceDictation() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const status = document.getElementById("composer-status");
    const btn = document.getElementById("btn-voice-narr");
    if (!SR) {
      if (status) status.textContent = "Voice unavailable in this browser — use HAL: dictate findings: …";
      return;
    }
    if (voiceListening && voiceRecognition) {
      try {
        voiceRecognition.stop();
      } catch (_err) {
        /* ignore */
      }
      voiceListening = false;
      if (btn) btn.textContent = "🎙 Voice";
      if (status) status.textContent = `Draft · ${activeSection().title}`;
      return;
    }
    const rec = new SR();
    voiceRecognition = rec;
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (ev) => {
      const said = String((ev.results && ev.results[0] && ev.results[0][0] && ev.results[0][0].transcript) || "").trim();
      if (!said) return;
      if (window.Apex && typeof window.Apex.askHalFromBridge === "function") {
        window.Apex.askHalFromBridge(`dictate ${activeId}: ${said}`);
      } else {
        applyVoiceText(activeId, said, "append");
      }
    };
    rec.onerror = () => {
      voiceListening = false;
      if (btn) btn.textContent = "🎙 Voice";
    };
    rec.onend = () => {
      voiceListening = false;
      if (btn) btn.textContent = "🎙 Voice";
    };
    voiceListening = true;
    if (btn) btn.textContent = "● Listening…";
    if (status) status.textContent = `Listening · ${activeSection().title}`;
    try {
      rec.start();
    } catch (_err) {
      voiceListening = false;
      if (btn) btn.textContent = "🎙 Voice";
    }
  }

  function wire(root) {
    root.querySelectorAll("[data-section]").forEach((el) => {
      el.addEventListener("click", () => setActive(el.getAttribute("data-section")));
    });
    document.getElementById("btn-add-section")?.addEventListener("click", () => {
      persistEditor();
      const id = `sec-${Date.now()}`;
      sections.push({ id, title: `Section ${sections.length + 1}`, content: "" });
      activeId = id;
      remount();
    });
    root.querySelectorAll("[data-sel-note]").forEach((el) => {
      el.addEventListener("change", () => {
        const id = el.value;
        if (el.checked) selectedNotes.add(id);
        else selectedNotes.delete(id);
        remount();
      });
    });
    root.querySelectorAll("[data-sel-claim]").forEach((el) => {
      el.addEventListener("change", () => {
        if (el.checked) {
          selectedClaimId = el.value;
          const claim = (sources.claims || []).find((c) => c.claimId === selectedClaimId);
          if (claim && claim.payer && !selectedPayerId) {
            selectedPayerId = String(claim.payer).trim().toLowerCase();
          }
          remount();
        }
      });
    });
    root.querySelectorAll("[data-sel-payer]").forEach((el) => {
      el.addEventListener("change", () => {
        if (el.checked) {
          selectedPayerId = el.value;
          remount();
        }
      });
    });
    document.getElementById("btn-lock-context")?.addEventListener("click", lockContext);
    document.getElementById("btn-ins-generate")?.addEventListener("click", generateInsurance);
    document.getElementById("btn-rewrite-hal")?.addEventListener("click", rewriteHal);
    document.getElementById("btn-apply-suggestion")?.addEventListener("click", applySuggestion);
    document.getElementById("btn-insert-template")?.addEventListener("click", insertTemplate);
    document.getElementById("btn-voice-narr")?.addEventListener("click", toggleVoiceDictation);
    document.getElementById("ins-payer-template")?.addEventListener("change", (ev) => {
      selectedTemplateId = String(ev.target.value || "");
    });
    document.getElementById("btn-generate-packet")?.addEventListener("click", generatePacket);
    document.getElementById("btn-save-draft")?.addEventListener("click", () => {
      persistEditor();
      try {
        sessionStorage.setItem(
          "nr2-apex-narrative-draft",
          JSON.stringify({
            sections,
            activeId,
            selectedNotes: Array.from(selectedNotes),
            selectedClaimId,
            selectedPayerId,
            lockedContextId,
          })
        );
      } catch (_err) {
        /* ignore */
      }
      const status = document.getElementById("composer-status");
      if (status) status.textContent = `Saved · ${activeSection().title}`;
    });
    document.getElementById("narr-editor")?.addEventListener("input", persistEditor);
  }

  function restoreDraft() {
    try {
      const raw = sessionStorage.getItem("nr2-apex-narrative-draft");
      if (!raw) return;
      const data = JSON.parse(raw);
      if (Array.isArray(data.sections) && data.sections.length) {
        sections = data.sections;
        activeId = data.activeId || sections[0].id;
      }
      if (Array.isArray(data.selectedNotes)) selectedNotes = new Set(data.selectedNotes.map(String));
      if (data.selectedClaimId) selectedClaimId = String(data.selectedClaimId);
      if (data.selectedPayerId) selectedPayerId = String(data.selectedPayerId);
      if (data.lockedContextId) lockedContextId = String(data.lockedContextId);
    } catch (_err) {
      /* ignore */
    }
  }

  async function mount(stageEl) {
    if (!stageEl) return;
    restoreDraft();
    applySeed();
    await loadStructure();
    stageEl.className = "apex-stage apex-mosaic";
    stageEl.innerHTML = shellHtml();
    wire(stageEl);
    const title = document.getElementById("apex-page-title");
    if (title) title.textContent = PAGE_TITLES.narratives || "Narratives";
  }

  function isActive() {
    return !!document.getElementById("narratives-bridge");
  }

  window.ApexNarratives = {
    mount,
    isActive,
    persistEditor,
    applyVoiceText,
  };
})();
