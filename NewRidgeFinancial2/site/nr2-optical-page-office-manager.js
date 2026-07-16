/* Office Manager — readiness + SoftDent ops · Force Close · Mon–Thu list · no fake board actions */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  function countApptSlots(data) {
    if (!data || !Array.isArray(data.operatories)) return null;
    let n = 0;
    data.operatories.forEach(function (op) {
      if (op && Array.isArray(op.slots)) n += op.slots.length;
    });
    return n;
  }

  function todayIsoLocal() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return y + "-" + m + "-" + day;
  }

  function shortHash(h) {
    const s = String(h || "").replace(/^#/, "").trim();
    if (!s) return "—";
    return "#" + s.slice(0, 4);
  }

  let wkProviderOptions = [];
  let wkActivePatientId = "";

  function selectedProvider() {
    const sel = document.getElementById("wk-provider");
    return sel ? String(sel.value || "").trim() : "";
  }

  function collectProviders(data) {
    const set = {};
    (data && data.days ? data.days : []).forEach(function (day) {
      (day && day.slots ? day.slots : []).forEach(function (slot) {
        const p = String((slot && slot.provider) || "").trim();
        if (p && p !== "—") set[p] = true;
      });
    });
    return Object.keys(set).sort();
  }

  function fillProviderSelect(providers) {
    const sel = document.getElementById("wk-provider");
    if (!sel) return;
    const cur = String(sel.value || "");
    const merged = {};
    (wkProviderOptions || []).forEach(function (p) {
      merged[p] = true;
    });
    (providers || []).forEach(function (p) {
      merged[p] = true;
    });
    wkProviderOptions = Object.keys(merged).sort();
    sel.textContent = "";
    const all = document.createElement("option");
    all.value = "";
    all.textContent = "All";
    sel.appendChild(all);
    wkProviderOptions.forEach(function (p) {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      sel.appendChild(opt);
    });
    if (cur && merged[cur]) sel.value = cur;
  }

  function setDossierMessage(text, isFault) {
    const panel = document.getElementById("wk-dossier");
    const body = document.getElementById("wk-dossier-body");
    const wrap = document.querySelector(".om-weekly-body");
    if (!panel || !body) return;
    panel.hidden = false;
    if (wrap) wrap.classList.add("has-dossier");
    body.textContent = "";
    const p = document.createElement("p");
    p.className = isFault ? "d-fault" : "";
    p.style.margin = "0";
    p.textContent = text;
    body.appendChild(p);
  }

  function renderDossierMini(data, fallback) {
    const panel = document.getElementById("wk-dossier");
    const body = document.getElementById("wk-dossier-body");
    const wrap = document.querySelector(".om-weekly-body");
    if (!panel || !body) return;
    panel.hidden = false;
    if (wrap) wrap.classList.add("has-dossier");
    body.textContent = "";
    if (!data || data.ok === false) {
      const p = document.createElement("p");
      p.className = "d-fault";
      p.style.margin = "0";
      p.textContent =
        (data && data.error) ||
        "Mini dossier unavailable · capability or SoftDent gap · empty ≠ $0";
      body.appendChild(p);
      return;
    }
    const rows = [
      ["Initials", String(data.initials || (fallback && fallback.initials) || "P—")],
      ["Hash", shortHash(data.patientHash || (fallback && fallback.patientHash))],
      ["Carrier", data.primaryCarrier != null ? String(data.primaryCarrier) : "—"],
      ["Open claims", data.openClaims != null ? String(data.openClaims) : "—"],
      ["Last visit", data.lastVisit != null ? String(data.lastVisit) : "—"],
      ["Clinical notes", data.hasClinicalNotes ? "yes" : "none / unknown"],
      ["Account $", data.accountBalance != null ? String(data.accountBalance) : "unavailable"],
    ];
    rows.forEach(function (pair) {
      const row = document.createElement("div");
      row.className = "d-row";
      const k = document.createElement("span");
      k.textContent = pair[0];
      const v = document.createElement("span");
      v.textContent = pair[1];
      row.appendChild(k);
      row.appendChild(v);
      body.appendChild(row);
    });
    if (data.schemaGap) {
      const note = document.createElement("p");
      note.style.margin = "8px 0 0";
      note.style.color = "#5a6575";
      note.textContent = String(data.schemaGap);
      body.appendChild(note);
    }

    const claims = data.claims && typeof data.claims === "object" ? data.claims : null;
    const claimItems = claims && Array.isArray(claims.items) ? claims.items : [];
    const claimsHead = document.createElement("h4");
    claimsHead.className = "wk-dossier-sub";
    claimsHead.textContent = "Claims (SoftDent)";
    body.appendChild(claimsHead);
    if (!claimItems.length) {
      const empty = document.createElement("p");
      empty.className = "wk-dossier-muted";
      empty.textContent =
        (claims && (claims.emptyMessage || claims.error)) ||
        "No SoftDent claims for this patient.";
      body.appendChild(empty);
    } else {
      const ul = document.createElement("ul");
      ul.className = "wk-claim-list";
      claimItems.slice(0, 5).forEach(function (c) {
        if (!c || typeof c !== "object") return;
        const li = document.createElement("li");
        const amt =
          c.amount == null || c.amount === ""
            ? "—"
            : typeof c.amount === "number"
              ? "$" + c.amount.toLocaleString("en-US", { maximumFractionDigits: 2 })
              : String(c.amount);
        li.textContent =
          shortHash(c.claimHash || c.claimId) +
          " · " +
          String(c.payer || "unknown") +
          " · " +
          String(c.serviceDate || "—") +
          " · " +
          amt +
          " · " +
          String(c.status || "—");
        ul.appendChild(li);
      });
      body.appendChild(ul);
    }

    const ph = shortHash(data.patientHash || (fallback && fallback.patientHash)).replace(/^#/, "");
    const pid = String((fallback && fallback.patientId) || "").trim();
    const initials = String(data.initials || (fallback && fallback.initials) || "P—");
    const actions = document.createElement("div");
    actions.className = "wk-dossier-actions";
    const halBtn = document.createElement("button");
    halBtn.type = "button";
    halBtn.className = "btn-quiet";
    halBtn.textContent = "Ask HAL about this patient →";
    halBtn.addEventListener("click", function () {
      askHalAboutPatient(pid, ph, initials);
    });
    actions.appendChild(halBtn);
    body.appendChild(actions);
  }

  function askHalAboutPatient(patientId, patientHash, initials) {
    const pid = String(patientId || "").trim();
    const ph = String(patientHash || "").replace(/^#/, "").trim();
    if (!pid) {
      setDossierMessage("Cannot hand off to HAL — SoftDent patient id missing.", true);
      return;
    }
    const ctx = {
      patientId: pid,
      patientHash: ph,
      initials: String(initials || "P—"),
      at: Date.now(),
      ttlMs: 30 * 60 * 1000,
    };
    try {
      sessionStorage.setItem("nr2.hal.patientContext", JSON.stringify(ctx));
    } catch (_) {}
    if (W.postJson && ph) {
      W.postJson(
        "/api/audit/hal-patient-context",
        {
          patientHash: ph,
          action: "context_set",
          toolsUsed: '["om_ask_hal_link"]',
        },
        8000
      ).catch(function () {});
    }
    const url =
      "/nr2-optical-page-hal.html?patientId=" +
      encodeURIComponent(pid) +
      "&patientHash=" +
      encodeURIComponent(ph) +
      "&autoSummarize=1";
    window.location.href = url;
  }

  async function openPatientContext(slot) {
    const pid = String((slot && slot.patientId) || "").trim();
    const ph = String((slot && slot.patientHash) || "").trim();
    wkActivePatientId = pid;
    document.querySelectorAll(".wk-slot.is-active").forEach(function (el) {
      el.classList.remove("is-active");
    });
    if (!pid) {
      setDossierMessage("No SoftDent patient id on this slot.", true);
      return;
    }
    setDossierMessage("Loading mini dossier…");
    try {
      if (W.ensureSession) await W.ensureSession();
      if (ph && W.postJson) {
        W.postJson(
          "/api/audit/hal-patient-context",
          { patientHash: ph, action: "set_context", toolsUsed: '["om_weekly_click"]' },
          8000
        ).catch(function () {});
      }
      const res = await W.getJson(
        "/api/apex/patient-dossier-mini/" + encodeURIComponent(pid),
        12000
      );
      if (wkActivePatientId !== pid) return;
      if (!res.ok) {
        setDossierMessage(
          "Mini dossier " +
            (res.status === 403 ? "capability rejected" : "NO SIGNAL") +
            " · " +
            String((res.data && res.data.error) || res.status),
          true
        );
        return;
      }
      renderDossierMini(res.data, slot);
    } catch (err) {
      setDossierMessage(
        "Mini dossier fault · " + String(err && err.message ? err.message : err),
        true
      );
    }
  }

  function renderWeeklySchedule(data) {
    const grid = document.getElementById("wk-days-grid");
    const rangeEl = document.getElementById("wk-range-label");
    if (!grid) return;
    grid.textContent = "";
    const days = data && Array.isArray(data.days) ? data.days : [];
    if (rangeEl) {
      rangeEl.textContent = data && data.dateRange ? String(data.dateRange) : "—";
    }
    if (!selectedProvider()) {
      fillProviderSelect(collectProviders(data));
    } else {
      fillProviderSelect(wkProviderOptions);
    }
    if (!days.length) {
      const p = document.createElement("p");
      p.className = "wk-empty";
      p.textContent =
        (data && data.emptyMessage) ||
        "No Mon–Thu SoftDent appointments — sync SoftDent or empty week.";
      grid.appendChild(p);
      return;
    }
    const today = todayIsoLocal();
    days.forEach(function (day) {
      if (!day || typeof day !== "object") return;
      const col = document.createElement("article");
      const dateIso = String(day.date || "").slice(0, 10);
      col.className = "wk-day" + (dateIso === today ? " is-today" : "");

      const head = document.createElement("div");
      head.className = "wk-day-head";
      const title = document.createElement("span");
      title.textContent =
        String(day.dayName || "").slice(0, 3) +
        (dateIso ? " · " + dateIso.slice(5) : "");
      const count = document.createElement("span");
      count.className = "wk-count";
      const n = typeof day.count === "number" ? day.count : (day.slots || []).length;
      count.textContent = String(n) + " appt" + (n === 1 ? "" : "s");
      head.appendChild(title);
      head.appendChild(count);
      col.appendChild(head);

      const slots = Array.isArray(day.slots) ? day.slots : [];
      if (!slots.length) {
        const empty = document.createElement("p");
        empty.className = "wk-empty";
        empty.textContent =
          String(day.emptyMessage || "").trim() || "No SoftDent appointments.";
        col.appendChild(empty);
      } else {
        const ul = document.createElement("ul");
        ul.className = "wk-slots";
        slots.forEach(function (slot) {
          if (!slot || typeof slot !== "object") return;
          const li = document.createElement("li");
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "wk-slot";
          if (wkActivePatientId && String(slot.patientId || "") === wkActivePatientId) {
            btn.classList.add("is-active");
          }
          const phi = document.createElement("span");
          phi.className = "phi";
          const initials = String(slot.initials || "P—").trim() || "P—";
          phi.textContent = initials + " · " + shortHash(slot.patientHash);
          const prov = document.createElement("span");
          prov.className = "prov";
          prov.textContent = String(slot.provider || "—");
          prov.title = String(slot.provider || "");
          const st = document.createElement("span");
          st.className = "st";
          st.textContent = String(slot.status || "scheduled");
          const tm = document.createElement("span");
          tm.className = "tm";
          tm.textContent = "time " + (String(slot.time || "—").trim() || "—");
          btn.appendChild(phi);
          btn.appendChild(prov);
          btn.appendChild(st);
          btn.appendChild(tm);
          btn.addEventListener("click", function () {
            btn.classList.add("is-active");
            openPatientContext(slot);
          });
          li.appendChild(btn);
          ul.appendChild(li);
        });
        col.appendChild(ul);
      }
      grid.appendChild(col);
    });
  }

  async function loadWeeklySchedule() {
    const grid = document.getElementById("wk-days-grid");
    if (grid) {
      grid.textContent = "";
      const p = document.createElement("p");
      p.className = "wk-loading";
      p.id = "wk-loading";
      p.textContent = "Loading Mon–Thu schedule…";
      grid.appendChild(p);
    }
    const prov = selectedProvider();
    let path = "/api/softdent/appointments-range?days=4";
    if (prov) path += "&provider=" + encodeURIComponent(prov);
    const res = await W.getJson(path, 15000);
    if (!res.ok || !res.data) {
      if (grid) {
        grid.textContent = "";
        const p = document.createElement("p");
        p.className = "wk-fault";
        p.textContent =
          "Mon–Thu schedule NO SIGNAL · " +
          String((res.data && res.data.error) || res.status || "fetch failed");
        grid.appendChild(p);
      }
      const rangeEl = document.getElementById("wk-range-label");
      if (rangeEl) rangeEl.textContent = "NO SIGNAL";
      return false;
    }
    if (!prov) {
      fillProviderSelect(collectProviders(res.data));
    }
    renderWeeklySchedule(res.data);
    return !!(res.data.hasData || (res.data.days && res.data.days.length));
  }

  function wireWeeklyControls() {
    const btn = document.getElementById("btn-wk-refresh");
    if (btn && !btn._nr2WkBound) {
      btn._nr2WkBound = true;
      btn.addEventListener("click", function () {
        loadWeeklySchedule().catch(function (err) {
          const grid = document.getElementById("wk-days-grid");
          if (!grid) return;
          grid.textContent = "";
          const p = document.createElement("p");
          p.className = "wk-fault";
          p.textContent =
            "Mon–Thu refresh fault · " + String(err && err.message ? err.message : err);
          grid.appendChild(p);
        });
      });
    }
    const sel = document.getElementById("wk-provider");
    if (sel && !sel._nr2WkBound) {
      sel._nr2WkBound = true;
      sel.addEventListener("change", function () {
        loadWeeklySchedule().catch(function () {});
      });
    }
    const closeBtn = document.getElementById("btn-wk-dossier-close");
    if (closeBtn && !closeBtn._nr2WkBound) {
      closeBtn._nr2WkBound = true;
      closeBtn.addEventListener("click", function () {
        const panel = document.getElementById("wk-dossier");
        const wrap = document.querySelector(".om-weekly-body");
        if (panel) panel.hidden = true;
        if (wrap) wrap.classList.remove("has-dossier");
        wkActivePatientId = "";
        document.querySelectorAll(".wk-slot.is-active").forEach(function (el) {
          el.classList.remove("is-active");
        });
      });
    }
  }

  function gapKeys(ready) {
    const keys = [];
    const seen = {};
    function add(list) {
      (list || []).forEach(function (g) {
        if (!g || typeof g !== "object") return;
        const k = String(g.datasetKey || g.key || "").trim();
        if (!k || seen[k]) return;
        seen[k] = true;
        keys.push(k);
      });
    }
    add(ready.blocking);
    const gaps = (ready.datasetGaps || []).concat(
      (ready.completeness && ready.completeness.softGaps) || []
    );
    add(
      gaps.filter(function (g) {
        return g && /stale|missing|partial/i.test(String(g.status || ""));
      })
    );
    return keys;
  }

  function wireForceClose(readyData, readyOk) {
    const btn = document.getElementById("btn-force-close");
    if (!btn || btn._nr2ForceBound) return;
    btn._nr2ForceBound = true;
    btn.addEventListener("click", async function () {
      if (btn.disabled || btn.classList.contains("busy")) return;
      btn.classList.add("busy");
      btn.disabled = true;
      btn.textContent = "CLOSING…";
      W.setBanner("partial", "OM FORCE CLOSE · SoftDent pull if lasers red / stalled · empty ≠ $0");
      try {
        await W.ensureSession();
        const res = await W.forcePeriodClose({ actor: "optical-om" });
        const data = res && res.data ? res.data : {};
        const ok = !!(res && res.ok && data.ok);
        const status = String(data.status || (ok ? "completed" : "failed")).toUpperCase();
        const pull =
          data.pullSoftdentDecided === true
            ? " · SoftDent pull"
            : data.pullSoftdentDecided === false
              ? " · attest-only"
              : "";
        const hash = data.beamHash ? " · hash " + String(data.beamHash).slice(0, 8) : "";
        const fallback = data.fallback ? " · " + String(data.fallback) : "";
        W.setBanner(
          ok ? "live" : "partial",
          "OM FORCE CLOSE · " +
            status +
            pull +
            fallback +
            hash +
            (ok ? "" : " · " + String(data.error || "failed")) +
            " · empty ≠ $0"
        );
        if (ok) {
          W.setText("val-close", status);
          const el = document.getElementById("val-close");
          if (el) el.classList.remove("stale");
        } else if (String(data.status || "").toLowerCase() === "blocked") {
          W.setText("val-close", "BLOCKED");
          const el = document.getElementById("val-close");
          if (el) el.classList.add("stale");
        }
      } catch (err) {
        W.setBanner(
          "partial",
          "OM FORCE CLOSE fault · " + String(err && err.message ? err.message : err)
        );
      } finally {
        btn.classList.remove("busy");
        btn.textContent = "FORCE CLOSE";
        setTimeout(function () {
          boot();
        }, 400);
      }
    });
  }

  async function boot() {
    W.setBanner("partial", "OM wiring readiness + SoftDent day pulse · empty ≠ $0");
    W.setText("val-close", null, "—");
    W.setText("val-ready", null, "—");
    W.setText("val-ops", null, "—");
    W.setText("val-gaps", null, "—");
    W.setText("val-health", null, "—");

    wireWeeklyControls();
    const [ready, health, np, appt, weeklyOk] = await Promise.all([
      W.getJson("/api/import-readiness", 12000),
      W.getJson("/api/health", 12000),
      W.getJson("/api/softdent/new-patients-mtd", 12000),
      W.getJson("/api/softdent/appointments-today", 12000),
      loadWeeklySchedule().catch(function () {
        return false;
      }),
    ]);

    let live = !!weeklyOk;
    let blocked = false;
    let closeTrouble = false;
    let readyData = null;
    let pc = null;

    if (ready.ok && ready.data) {
      readyData = ready.data;
      const blocking = Array.isArray(readyData.blocking) ? readyData.blocking.length : 0;
      blocked = W.lasersRed ? W.lasersRed(readyData) : blocking > 0;
      closeTrouble = W.periodCloseIsTrouble ? W.periodCloseIsTrouble(readyData) : false;
      pc = W.periodCloseStatus ? W.periodCloseStatus(readyData) : null;
      const closeBit = W.periodCloseBannerBit
        ? W.periodCloseBannerBit(readyData)
        : "CLOSE · UNKNOWN";
      if (pc) {
        W.setText("val-close", String(pc.status || "unknown").toUpperCase());
        const ch = document.getElementById("hint-close");
        if (ch) {
          ch.textContent =
            closeBit + " · FORCE CLOSE pulls SoftDent when lasers red / stalled · empty ≠ $0";
        }
        if (closeTrouble) {
          const el = document.getElementById("val-close");
          if (el) el.classList.add("stale");
        }
      } else {
        W.setText("val-close", "NO SIGNAL");
      }
      const level = String(readyData.level || "unknown").toUpperCase();
      const sum = readyData.summary || {};
      const laserKeys = W.laserKeys ? W.laserKeys(readyData) : [];
      W.setText(
        "val-ready",
        level +
          (blocked ? " · lasers red" : " · lasers clear") +
          (blocking ? " · block " + blocking : "") +
          (sum.stale != null ? " · stale " + sum.stale : "")
      );
      const keys = laserKeys.length ? laserKeys : gapKeys(readyData);
      if (keys.length) {
        W.setText("val-gaps", keys.slice(0, 3).join(" · ") + (keys.length > 3 ? " +" + (keys.length - 3) : ""));
        const gh = document.getElementById("hint-gaps");
        if (gh) {
          gh.textContent =
            keys.length +
            " key(s)" +
            (blocked ? " · lasers RED" : " · soft gaps") +
            " · empty ≠ $0";
        }
      } else {
        W.setText("val-gaps", "NONE");
      }
      const hint = document.getElementById("hint-ready");
      if (hint) {
        hint.textContent = blocked
          ? "Blocking / lasers red · money reads STALE on main"
          : closeTrouble
            ? "Lasers clear but period-close " + String((pc && pc.status) || "trouble") + " — not LIVE OPS"
            : "No laser block · brief soft stale under TTL stays green";
      }
      live = true;
    } else {
      W.setText("val-close", "NO SIGNAL");
      W.setText("val-ready", "NO SIGNAL");
      W.setText("val-gaps", "NO SIGNAL");
    }

    wireForceClose(readyData, ready.ok);
    if (W.bindVerifyBeamButton) {
      W.bindVerifyBeamButton("btn-verify-beam", {
        hintId: "hint-beam-proof",
        valId: "val-beam-proof",
      });
    }
    if (W.bindDeskSmokeButton) {
      W.bindDeskSmokeButton("btn-desk-smoke", {
        hintId: "hint-desk-smoke",
        valId: "val-desk-smoke",
      });
    }
    W.getJson("/api/health/desk-smoke?run=0", 8000).then(function (res) {
      if (!res || !res.ok || !res.data) return;
      const st = String(res.data.status || "NO SIGNAL").toUpperCase();
      W.setText("val-desk-smoke", st);
      const el = document.getElementById("val-desk-smoke");
      if (el) {
        el.classList.remove("stale", "hal");
        el.classList.add(st === "GREEN" ? "hal" : "stale");
      }
    });
    const btn = document.getElementById("btn-force-close");
    if (btn && !btn.classList.contains("busy")) {
      const available = W.forceCloseAvailable
        ? W.forceCloseAvailable(readyData)
        : false;
      btn.disabled = !ready.ok || !available;
    }

    const opsBits = [];
    if (np.ok && np.data && np.data.hasData && np.data.count != null) {
      opsBits.push(String(np.data.count) + " NP");
      const oh = document.getElementById("hint-ops");
      if (oh) {
        oh.textContent =
          "new patients" + (np.data.period ? " · " + np.data.period : "") + " · appointments today";
      }
      live = true;
    }
    if (appt.ok && appt.data && appt.data.hasData) {
      const slots = countApptSlots(appt.data);
      if (slots != null) {
        opsBits.push(String(slots) + " appts");
        live = true;
      }
    }
    if (opsBits.length) {
      W.setText("val-ops", opsBits.join(" · "));
    } else {
      W.setText("val-ops", null, np.ok || appt.ok ? "∅" : "NO SIGNAL");
    }

    if (health.ok && health.data) {
      const bits = [];
      bits.push(health.data.db ? "DB" : "DB↓");
      bits.push(health.data.ollama ? "OLLAMA" : "OLLAMA↓");
      if (health.data.readinessLevel) bits.push(String(health.data.readinessLevel).toUpperCase());
      W.setText("val-health", bits.join(" · "));
      live = true;
    } else {
      W.setText("val-health", "NO SIGNAL");
    }

    const closeBit = readyData && W.periodCloseBannerBit ? W.periodCloseBannerBit(readyData) : "";
    W.setBanner(
      blocked || closeTrouble ? "partial" : live ? "live" : "partial",
      blocked
        ? "OM · lasers STALE · FORCE CLOSE pulls SoftDent aging · empty ≠ $0"
        : closeTrouble
          ? "OM · " + closeBit + " · FORCE CLOSE available · empty ≠ $0"
          : "OM · SoftDent Mon–Thu list + day pulse · " +
            (closeBit || "CLOSE · idle") +
            " · FORCE CLOSE · empty ≠ $0"
    );
  }

  boot().catch((err) => {
    W.setBanner("partial", "OM wire fault · " + String(err && err.message ? err.message : err));
  });
})();

