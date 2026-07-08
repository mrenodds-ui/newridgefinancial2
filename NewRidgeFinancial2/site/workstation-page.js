/**
 * Office Workstation — Ask HAL tab + NR2 office channel messaging (SideNotes-like workflow, distinct UI).
 */
const WorkstationPage = (function () {
  const DEFAULT_MESSAGE_PROMPTS = [
    { label: "Patient arrived", template: "{station}: Patient has arrived" },
    { label: "Doctor ready", template: "{station}: Doctor is ready" },
    { label: "Need assistant", template: "{station}: Need assistant — " },
    { label: "Front desk", template: "{station}: Please send patient to front desk — " },
    { label: "Running behind", template: "{station}: Running behind — " },
    { label: "Blank message", template: "{station}: " },
    { label: "X-ray ready", template: "{station}: X-ray ready — " },
    { label: "Checkout", template: "{station}: Patient ready for checkout" },
    { label: "Sterilization", template: "{station}: Need instrument pick-up" },
    { label: "Break", template: "{station}: Stepping away — " },
    { label: "Confirm appt", template: "{station}: Please confirm appointment — " },
    { label: "Emergency", template: "{station}: URGENT — " },
  ];

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function iconsApi() {
    if (typeof AppIcons !== "undefined") return AppIcons;
    if (typeof globalThis !== "undefined" && globalThis.AppIcons) return globalThis.AppIcons;
    return null;
  }

  function uiIcon(key) {
    const api = iconsApi();
    if (!api) return "";
    const icon = api.ui(key);
    return icon ? api.wrap("hp-ico", icon) : "";
  }

  function navIcon(pageId) {
    const api = iconsApi();
    if (!api) return "";
    const icon = api.nav(pageId);
    return icon ? api.wrap("hp-ico", icon) : "";
  }

  function cardIconRaw(type, key) {
    const api = iconsApi();
    if (!api) return "";
    if (type === "nav") return api.nav(key) || "";
    if (type === "hal") return api.hal() || "";
    return api.ui(key) || "";
  }

  function cardIcon(type, key) {
    const icon = cardIconRaw(type, key);
    const api = iconsApi();
    return icon && api ? api.wrap("hp-card__ico", icon) : "";
  }

  function promptIcon(text) {
    const q = String(text || "").toLowerCase();
    if (q.includes("sidenote")) return navIcon("sidenotes");
    if (q.includes("import") || q.includes("softdent")) return navIcon("softdent");
    if (q.includes("briefing") || q.includes("attention")) return navIcon("office-manager");
    if (q.includes("monitor")) return uiIcon("monitor");
    return uiIcon("send");
  }

  function actionChip(label, attrs) {
    return `<button type="button" class="hp-action hp-action--icon" ${attrs}>${promptIcon(label)}<span class="hp-action__text">${esc(label)}</span></button>`;
  }

  function drawerInfoBtn(panelKey, label) {
    return `<button type="button" class="hp-info" data-hal-drawer="${esc(panelKey)}" title="${esc(label)}" aria-label="${esc(label)}">${uiIcon("info")}<span class="hp-info__label">i</span></button>`;
  }

  function cardHead(titleHtml, drawerKey, drawerLabel, iconSvg) {
    const iconPart = iconSvg
      ? `<button type="button" class="hp-card__ico hp-card__ico--btn" data-hal-drawer="${esc(drawerKey)}" title="${esc(drawerLabel)}" aria-label="${esc(drawerLabel)}">${iconSvg}</button>`
      : "";
    return `<div class="hp-card__head"><h3>${iconPart}${titleHtml}</h3>${drawerInfoBtn(drawerKey, drawerLabel)}</div>`;
  }

  function fillStationTemplate(template, stationLabel) {
    return String(template || "").replace(/\{station\}/gi, String(stationLabel || "Workstation"));
  }

  const DEFAULT_ASK_HAL_SUGGESTIONS = [
    "What is the ADA code for dental office accessibility?",
    "How do I verify a patient's insurance eligibility?",
    "What is our cancellation and no-show policy?",
    "How do I handle a patient allergy or medical alert?",
    "Where is the emergency kit and AED?",
    "How do I take a periapical x-ray?",
    "What are today's office hours?",
    "How do I schedule a hygiene recall?",
  ];

  function workstationConfig() {
    if (typeof WorkstationSchema !== "undefined" && WorkstationSchema.page) return WorkstationSchema.page;
    if (typeof PageSchema !== "undefined" && PageSchema.byId) return PageSchema.byId("workstation");
    return null;
  }

  function askHalSuggestionsFor(ctx) {
    const page = workstationConfig();
    if (page && Array.isArray(page.askHalSuggestions) && page.askHalSuggestions.length) {
      return page.askHalSuggestions;
    }
    return DEFAULT_ASK_HAL_SUGGESTIONS;
  }

  function defaultMessagePrompts() {
    const page = workstationConfig();
    if (page && Array.isArray(page.messagePrompts) && page.messagePrompts.length) {
      return page.messagePrompts.map((p) => ({ label: p.label, template: p.template }));
    }
    return DEFAULT_MESSAGE_PROMPTS.map((p) => ({ label: p.label, template: p.template }));
  }

  function normalizeMessagePrompts(list) {
    const defaults = defaultMessagePrompts();
    if (!Array.isArray(list) || !list.length) return defaults.slice();
    const out = [];
    for (let i = 0; i < defaults.length; i += 1) {
      const src = list[i] || defaults[i];
      const template = String((src && src.template) || defaults[i].template || "").trim();
      const label = String((src && src.label) || defaults[i].label || `Quick note ${i + 1}`).trim();
      out.push({ label, template: template || defaults[i].template });
    }
    return out;
  }

  function promptBodyFromTemplate(template) {
    const raw = String(template || "");
    const match = raw.match(/^\{station\}:\s*(.*)$/is);
    if (match) return match[1];
    const generic = raw.match(/^[^:]+:\s*(.*)$/s);
    return generic ? generic[1] : raw;
  }

  function templateFromPromptBody(body) {
    return `{station}: ${String(body || "").trim()}`;
  }

  function labelFromPromptBody(body, fallback) {
    const text = String(body || "").trim();
    if (!text) return fallback || "Blank message";
    const short = text.length > 36 ? `${text.slice(0, 33)}…` : text;
    return short;
  }

  function messagePromptsFor(ctx) {
    if (Array.isArray(ctx.workstationMessagePrompts) && ctx.workstationMessagePrompts.length) {
      return normalizeMessagePrompts(ctx.workstationMessagePrompts);
    }
    return defaultMessagePrompts();
  }

  function promptDisplayBody(template, stationRaw) {
    const filled = fillStationTemplate(template, stationRaw);
    const match = filled.match(/^[^:]+:\s*(.*)$/s);
    const body = match ? match[1] : filled;
    return { filled, body, blank: !String(body || "").trim() };
  }

  function promptTile(label, template, stationRaw) {
    const { filled, body, blank } = promptDisplayBody(template, stationRaw);
    const station = esc(stationRaw || "Workstation");
    const bodyHtml = blank
      ? `<span class="ws-prompt-tile__prefix">${station}:</span><span class="ws-prompt-tile__blank"> </span>`
      : `<span class="ws-prompt-tile__text">${esc(body)}</span>`;
    return `<button type="button" class="ws-prompt-tile" data-ws-office-prompt="${esc(filled)}" aria-label="${esc(label)}">
      ${bodyHtml}
    </button>`;
  }

  function workstationStations() {
    if (typeof WorkstationSchema !== "undefined" && Array.isArray(WorkstationSchema.STATIONS)) {
      return WorkstationSchema.STATIONS.slice();
    }
    if (typeof HalPage !== "undefined" && HalPage.WORKSTATION_STATIONS) return HalPage.WORKSTATION_STATIONS.slice();
    return [
      "Frontdesk 1",
      "Frontdesk 2",
      "Office Manager",
      "Room 1",
      "Room 2",
      "Room 3",
      "Room 4",
      "Room 5",
      "Server",
      "Darkroom",
    ];
  }

  function officeChannelTargetList(ctx) {
    if (Array.isArray(ctx.officeChannelTargets) && ctx.officeChannelTargets.length) {
      return ctx.officeChannelTargets;
    }
    const legacy = ctx.officeChannelTarget;
    if (legacy) return [legacy];
    return ["all"];
  }

  function isOfficeTargetSelected(name, ctx) {
    const list = officeChannelTargetList(ctx).map((t) => String(t).toLowerCase());
    const key = String(name === "all" ? "all" : name).toLowerCase();
    if (key === "all") return list.includes("all") || list.includes("everyone");
    return list.includes(key);
  }

  function targetsLabelFromList(targets) {
    const list = (targets || []).filter(Boolean);
    if (!list.length) return "Select workstations";
    if (list.some((t) => /^(all|everyone)$/i.test(String(t)))) return "Everyone";
    if (list.length === 1) return String(list[0]);
    if (list.length <= 4) return list.join(" · ");
    return `${list.slice(0, 3).join(" · ")} +${list.length - 3}`;
  }

  function targetLabel(target) {
    if (Array.isArray(target)) return targetsLabelFromList(target);
    const t = String(target || "all").trim();
    if (!t || t.toLowerCase() === "all" || t.toLowerCase() === "everyone") return "Everyone";
    if (t.includes(",")) return targetsLabelFromList(t.split(",").map((s) => s.trim()));
    return t;
  }

  function workstationRailItem(name, targetKey, ctx) {
    const stationRaw = ctx.stationLabel || "Workstation";
    const key = String(targetKey || name).toLowerCase();
    const isSelf = key === String(stationRaw).toLowerCase();
    const active = isOfficeTargetSelected(name === "all" ? "all" : name, ctx);
    const label = name === "all" ? "Everyone" : name;
    return `<button type="button" class="ws-station-rail__item${active ? " ws-station-rail__item--active" : ""}${isSelf ? " ws-station-rail__item--self" : ""}" data-ws-office-target="${esc(name === "all" ? "all" : name)}" aria-pressed="${active ? "true" : "false"}"${isSelf ? " disabled title='You are here'" : ""}>
      <span class="ws-station-rail__name">${esc(label)}</span>
      ${isSelf ? '<span class="ws-station-rail__hint">This PC</span>' : name === "all" ? '<span class="ws-station-rail__hint">All</span>' : ""}
    </button>`;
  }

  function officeMessagesForStation(messages, stationLabel) {
    const station = String(stationLabel || "").trim().toLowerCase();
    if (!station) return (messages || []).slice();
    return (messages || []).filter((m) => {
      if (!m) return false;
      const fromSelf = String(m.from || "").trim().toLowerCase() === station;
      const forMe =
        typeof OfficeHub !== "undefined" && OfficeHub.messageTargetsForStation
          ? OfficeHub.messageTargetsForStation(m, stationLabel)
          : true;
      return fromSelf || forMe;
    });
  }

  function stationSelectHtml(ctx) {
    const stations = workstationStations();
    const current = String(ctx.stationLabel || "Workstation");
    const options = stations
      .map((name) => {
        const sel = name.toLowerCase() === current.toLowerCase() ? " selected" : "";
        return `<option value="${esc(name)}"${sel}>${esc(name)}</option>`;
      })
      .join("");
    const unset = current === "Workstation";
    return `<label class="ws-station-pick">
      <span class="ws-station-pick__label">THIS PC</span>
      <select class="ws-station-pick__select" id="wsStationSelect" data-ws-station-select aria-label="This workstation name"${unset ? ' aria-describedby="wsStationPickHint"' : ""}>
        ${unset ? '<option value="">Select station…</option>' : ""}
        ${options}
      </select>
      ${unset ? '<span class="ws-station-pick__hint" id="wsStationPickHint">Name this PC so messages route correctly</span>' : ""}
    </label>`;
  }

  const SN_KEY_TONES = ["amber", "blue", "gold", "white", "amber", "blue", "gold", "white", "amber", "blue", "gold", "white"];

  function workstationGroups() {
    if (typeof WorkstationSchema !== "undefined" && Array.isArray(WorkstationSchema.STATION_GROUPS)) {
      return WorkstationSchema.STATION_GROUPS;
    }
    return [{ id: "everyone", label: "Everyone", members: ["all"] }];
  }

  function practiceNameFor(ctx) {
    if (ctx && ctx.practiceName) return String(ctx.practiceName);
    if (typeof WorkstationSchema !== "undefined" && WorkstationSchema.practiceName) {
      return WorkstationSchema.practiceName;
    }
    const page = workstationConfig();
    if (page && page.practiceName) return page.practiceName;
    return "Office";
  }

  function messageRowId(m) {
    return String((m && m.id) || `${m && m.from}-${m && m.at}-${m && m.text}`);
  }

  function isMessageUnread(m, ctx) {
    const id = messageRowId(m);
    const ids = ctx && ctx.workstationReadIds;
    if (ids && ids.has && ids.has(id)) return false;
    if (Array.isArray(ids) && ids.includes(id)) return false;
    return true;
  }

  function isBroadcastMessage(m) {
    if (typeof OfficeHub !== "undefined" && OfficeHub.normalizeTargets) {
      return OfficeHub.normalizeTargets(m || {}).targets.some((t) => /^(all|everyone)$/i.test(String(t)));
    }
    const target = String((m && m.target) || "").toLowerCase();
    return !target || target === "all" || target === "everyone";
  }

  function officeChatMessages(ctx) {
    return mergedInboxMessages(ctx).filter((m) => isBroadcastMessage(m) && String(m.text || "").trim());
  }

  function sideNotesUserItem(name, ctx) {
    const stationRaw = ctx.stationLabel || "Workstation";
    const key = String(name === "all" ? "all" : name).toLowerCase();
    const isSelf = key === String(stationRaw).toLowerCase();
    const active = isOfficeTargetSelected(name === "all" ? "all" : name, ctx);
    const label = name === "all" ? "Everyone" : name;
    return `<button type="button" class="ws-sn-user${active ? " ws-sn-user--active" : ""}${isSelf ? " ws-sn-user--self" : ""}" data-ws-sn-target="${esc(name === "all" ? "all" : name)}" aria-pressed="${active ? "true" : "false"}" title="${isSelf ? "Send to this PC (includes popup test)" : name === "all" ? "Send to all workstations" : active ? "Remove from recipients" : "Add to recipients"}">
      <span class="ws-sn-user__dot" aria-hidden="true"></span>
      <span class="ws-sn-user__name">${esc(label)}</span>
    </button>`;
  }

  function sideNotesKeyTile(label, template, stationRaw, index) {
    const { filled, body, blank } = promptDisplayBody(template, stationRaw);
    const tone = SN_KEY_TONES[index % SN_KEY_TONES.length];
    const text = blank
      ? `<span class="ws-sn-key__prefix">${esc(stationRaw)}:</span>`
      : `<span class="ws-sn-key__text">${esc(body)}</span>`;
    return `<button type="button" class="ws-sn-key ws-sn-key--${tone}" data-ws-office-prompt="${esc(filled)}" aria-label="${esc(label)}">${text}</button>`;
  }

  function sideNotesUserListHtml(ctx) {
    const stations = workstationStations();
    return [sideNotesUserItem("all", ctx)]
      .concat(stations.map((name) => sideNotesUserItem(name, ctx)))
      .join("");
  }

  function sideNotesGroupItem(group, ctx) {
    const active = String(ctx.officeChannelGroup || "") === String(group.id || "");
    const count = (group.members || []).length;
    const hint = group.members.some((m) => /^(all|everyone)$/i.test(String(m)))
      ? "All stations"
      : `${count} stations`;
    return `<button type="button" class="ws-sn-group${active ? " ws-sn-group--active" : ""}" data-ws-sn-group="${esc(group.id)}" aria-pressed="${active ? "true" : "false"}">
      <span class="ws-sn-group__name">${esc(group.label)}</span>
      <span class="ws-sn-group__hint">${esc(hint)}</span>
    </button>`;
  }

  function sideNotesLeftPanelHtml(ctx) {
    const leftTab = String(ctx.workstationLeftTab || "users").toLowerCase() === "groups" ? "groups" : "users";
    const usersActive = leftTab === "users";
    const groupsActive = leftTab === "groups";
    const stationRaw = ctx.stationLabel || "Workstation";
    const userList = sideNotesUserListHtml(ctx);
    const groupList = workstationGroups()
      .map((g) => sideNotesGroupItem(g, ctx))
      .join("");
    return `<aside class="ws-sn-left" aria-label="Recipients">
        <div class="ws-sn-left-tabs">
          <button type="button" class="ws-sn-left-tab${usersActive ? " ws-sn-left-tab--active" : ""}" data-ws-sn-left-tab="users">Active Users</button>
          <button type="button" class="ws-sn-left-tab${groupsActive ? " ws-sn-left-tab--active" : ""}" data-ws-sn-left-tab="groups">Groups</button>
        </div>
        <div class="ws-sn-userlist${usersActive ? "" : " ws-sn-userlist--hidden"}">${userList}</div>
        <p class="ws-sn-userlist-hint${usersActive ? "" : " ws-sn-userlist-hint--hidden"}">Tap stations to select multiple. Everyone sends to all.</p>
        <div class="ws-sn-grouplist${groupsActive ? "" : " ws-sn-grouplist--hidden"}">${groupList}</div>
        <div class="ws-sn-left-foot">
          <label class="ws-sn-this-pc">
            <span class="ws-sn-this-pc__label">This PC</span>
            <select class="ws-sn-this-pc__select" id="wsStationSelect" data-ws-station-select aria-label="This workstation name">
              ${stationRaw === "Workstation" ? '<option value="">Select…</option>' : ""}
              ${workstationStations()
                .map((name) => {
                  const sel = name.toLowerCase() === String(stationRaw).toLowerCase() ? " selected" : "";
                  return `<option value="${esc(name)}"${sel}>${esc(name)}</option>`;
                })
                .join("")}
            </select>
          </label>
        </div>
      </aside>`;
  }

  function sideNotesKeysBlockHtml(ctx, stationRaw) {
    const editing = !!ctx.workstationPromptsEditing;
    if (editing) return `<div class="ws-sn-keys ws-sn-keys--edit">${promptsUnderMessageHtml(ctx)}</div>`;
    const prompts = messagePromptsFor(ctx);
    const keys = prompts
      .map((p, i) => sideNotesKeyTile(p.label, p.template, stationRaw, i))
      .join("");
    return `<div class="ws-sn-keys">${keys}</div>`;
  }

  function sideNotesComposeActionsHtml(ctx, stationRaw, sendClass, sendLabel, loading, hasTargets) {
    return `<div class="ws-sn-actions">
            <button type="button" class="ws-sn-prompt-edit" data-ws-prompt-edit="1">Edit</button>
            <button type="button" class="ws-sn-clear" data-ws-office-clear="1">Clear</button>
            <button type="submit" class="${sendClass}" id="wsOfficeSendBtn" ${loading || !hasTargets || stationRaw === "Workstation" ? "disabled" : ""}>${sendLabel}</button>
          </div>`;
  }

  function sideNotesStatusBarHtml(ctx, station) {
    const hubLive = ctx.officeHubLive !== false || ctx.sidenotesLive === true;
    const practice = esc(practiceNameFor(ctx));
    return `<footer class="ws-sn-statusbar">
        <span class="ws-sn-statusbar__dot${hubLive ? " ws-sn-statusbar__dot--live" : ""}" aria-hidden="true"></span>
        <span class="ws-sn-statusbar__practice">${practice}</span>
        <span class="ws-sn-statusbar__station">${station}</span>
      </footer>`;
  }

  function sideNotesComposeShell(ctx, options) {
    const opts = options || {};
    const forceEveryone = !!opts.forceEveryone;
    const stationRaw = ctx.stationLabel || "Workstation";
    const station = esc(stationRaw);
    const loading = !!ctx.officeChannelLoading;
    const sentFlash = !!ctx.officeChannelSendFlash;
    const targets = forceEveryone ? ["all"] : officeChannelTargetList(ctx);
    const hasTargets = targets.length > 0;
    const toName = esc(forceEveryone ? "Everyone" : targetsLabelFromList(targets));
    const sendClass = sentFlash
      ? "ws-sn-send ws-sn-send--sent"
      : loading
        ? "ws-sn-send ws-sn-send--sending"
        : "ws-sn-send";
    const sendLabel = sentFlash ? "Sent" : loading ? "…" : "Send";
    const headLabel = forceEveryone ? "Office Chat" : "Compose Message";
    return `<div class="ws-sn-shell" id="wsComposeStack">
      <div class="ws-sn-body">
      ${sideNotesLeftPanelHtml(ctx)}
      <section class="ws-sn-right">
        <header class="ws-sn-right-head">${headLabel} <span class="ws-sn-right-to">→ ${toName}</span></header>
        <form class="ws-sn-form" id="wsOfficeForm">
          <textarea class="ws-sn-input" id="wsOfficeInput" rows="4" maxlength="500" enterkeyhint="send" placeholder="Type a message…" aria-label="Message to ${toName}">${esc(ctx.officeChannelDraft || "")}</textarea>
          ${sideNotesKeysBlockHtml(ctx, stationRaw)}
          ${sideNotesComposeActionsHtml(ctx, stationRaw, sendClass, sendLabel, loading, hasTargets)}
        </form>
      </section>
      </div>
      ${sideNotesStatusBarHtml(ctx, station)}
    </div>`;
  }

  function sideNotesToolbarHtml(ctx) {
    const active = workstationMainTab(ctx);
    const count = mergedInboxMessages(ctx).filter((m) => isMessageUnread(m, ctx)).length;
    const historyLabel = count ? `History (${count})` : "History";
    return `<div class="ws-sn-toolbar" role="tablist" aria-label="Workstation">
      <button type="button" class="ws-sn-toolbar-tab${active === "send" ? " ws-sn-toolbar-tab--active" : ""}" role="tab" data-ws-page-tab="send">Type a Message</button>
      <button type="button" class="ws-sn-toolbar-tab${active === "history" ? " ws-sn-toolbar-tab--active" : ""}" role="tab" data-ws-page-tab="history">${esc(historyLabel)}</button>
      <button type="button" class="ws-sn-toolbar-tab${active === "officechat" ? " ws-sn-toolbar-tab--active" : ""}" role="tab" data-ws-page-tab="officechat">Office Chat</button>
      <button type="button" class="ws-sn-toolbar-tab${active === "sync" ? " ws-sn-toolbar-tab--active" : ""}" role="tab" data-ws-page-tab="sync">Sync</button>
      <button type="button" class="ws-sn-toolbar-tab${active === "askhal" ? " ws-sn-toolbar-tab--active" : ""}" role="tab" data-ws-page-tab="askhal">Ask HAL</button>
    </div>`;
  }

  function messageListHtml(messages, ctx, stationLabel, emptyText) {
    if (!messages.length) {
      return `<li class="ws-msg-empty">${esc(emptyText)}</li>`;
    }
    return messages
      .slice()
      .reverse()
      .slice(0, 32)
      .map((m) => {
        const isAll = isBroadcastMessage(m);
        const fromSelf = String(m.from || "").trim().toLowerCase() === String(stationLabel).trim().toLowerCase();
        const unread = isMessageUnread(m, ctx);
        const rowClass = `${fromSelf ? "ws-msg-row ws-msg-row--out" : "ws-msg-row ws-msg-row--in"}${unread ? " ws-msg-row--unread" : ""}`;
        const who = fromSelf ? "You" : esc(m.from || "Office");
        const route = isAll ? "Everyone" : esc(messageTargetsLabel(m));
        const voiceNote = m.speak ? " · Voice" : "";
        const srcNote = m._source === "sidenotes" ? " · SideNotes" : "";
        const when = m.at ? esc(String(m.at).slice(11, 19)) : "";
        return `<li class="${rowClass}" data-ws-msg-id="${esc(messageRowId(m))}">
              <div class="ws-msg-row__head">
                <span class="ws-msg-row__who">${who}${unread ? '<span class="ws-msg-row__unread">NEW</span>' : ""}</span>
                <span class="ws-msg-row__route">${fromSelf ? "→ " + route : "for you · " + route}${voiceNote}${srcNote}</span>
                <span class="ws-msg-row__time">${when}</span>
              </div>
              <p class="ws-msg-row__text">${esc(m.text || "")}</p>
            </li>`;
      })
      .join("");
  }

  function officeChatLogHtml(ctx) {
    const stationLabel = ctx.stationLabel || "Workstation";
    const messages = officeChatMessages(ctx);
    const listHtml = messageListHtml(
      messages,
      ctx,
      stationLabel,
      "Office-wide messages to Everyone appear here.",
    );
    return `<div class="ws-sn-chat-log" id="wsOfficeChatLog"><ul class="ws-msg-list">${listHtml}</ul></div>`;
  }

  function officeChatPanelHtml(ctx) {
    const active = workstationMainTab(ctx) === "officechat";
    const chatCtx = Object.assign({}, ctx, { officeChannelTargets: ["all"], officeChannelGroup: "everyone" });
    const log = officeChatLogHtml(chatCtx);
    const stationRaw = chatCtx.stationLabel || "Workstation";
    const station = esc(stationRaw);
    const loading = !!chatCtx.officeChannelLoading;
    const sentFlash = !!chatCtx.officeChannelSendFlash;
    const sendClass = sentFlash
      ? "ws-sn-send ws-sn-send--sent"
      : loading
        ? "ws-sn-send ws-sn-send--sending"
        : "ws-sn-send";
    const sendLabel = sentFlash ? "Sent" : loading ? "…" : "Send";
    return `<div class="ws-page-panel ws-page-panel--officechat ws-sn-officechat-panel${active ? "" : " ws-page-panel--hidden"}" role="tabpanel" aria-hidden="${active ? "false" : "true"}">
      <div class="ws-sn-shell">
        <div class="ws-sn-body ws-sn-body--chat">
          ${sideNotesLeftPanelHtml(chatCtx)}
          <section class="ws-sn-right ws-sn-right--chat">
            <header class="ws-sn-right-head">Office Chat <span class="ws-sn-right-to">→ Everyone</span></header>
            ${log}
            <form class="ws-sn-form ws-sn-form--chat" id="wsOfficeChatForm">
              <textarea class="ws-sn-input ws-sn-input--chat" id="wsOfficeChatInput" rows="3" maxlength="500" enterkeyhint="send" placeholder="Message everyone…" aria-label="Office chat to Everyone">${esc(chatCtx.officeChannelDraft || "")}</textarea>
              ${sideNotesKeysBlockHtml(chatCtx, stationRaw)}
              ${sideNotesComposeActionsHtml(chatCtx, stationRaw, sendClass, sendLabel, loading, true)}
            </form>
          </section>
        </div>
        ${sideNotesStatusBarHtml(chatCtx, station)}
      </div>
    </div>`;
  }

  function historyPanelHtml(ctx) {
    const active = workstationMainTab(ctx) === "history";
    return `<div class="ws-page-panel ws-page-panel--history ws-sn-history-panel${active ? "" : " ws-page-panel--hidden"}" role="tabpanel" aria-hidden="${active ? "false" : "true"}">
      ${officeChannelSentHtml(ctx)}
    </div>`;
  }

  function roomTargetTile(name, ctx) {
    const stationRaw = ctx.stationLabel || "Workstation";
    const key = String(name === "all" ? "all" : name).toLowerCase();
    const isSelf = key === String(stationRaw).toLowerCase();
    const active = isOfficeTargetSelected(name === "all" ? "all" : name, ctx);
    const label = name === "all" ? "Everyone" : name;
    return `<button type="button" class="ws-room-tile${active ? " ws-room-tile--active" : ""}${isSelf ? " ws-room-tile--self" : ""}" data-ws-office-target="${esc(name === "all" ? "all" : name)}" aria-pressed="${active ? "true" : "false"}"${isSelf ? " disabled title='You are here'" : ""}>
      <span class="ws-room-tile__name">${esc(label)}</span>
      ${isSelf ? '<span class="ws-room-tile__hint">This PC</span>' : name === "all" ? '<span class="ws-room-tile__hint">All rooms</span>' : ""}
    </button>`;
  }

  function recipientPickerHtml(ctx) {
    const stations = workstationStations();
    const tiles = [roomTargetTile("all", ctx)]
      .concat(stations.map((name) => roomTargetTile(name, ctx)))
      .join("");
    return `<div class="ws-room-picker">
      <div class="ws-room-picker__bar">
        <button type="button" class="ws-compose-back" data-ws-close-picker="1">${uiIcon("chevronRight")} Done</button>
        <span class="ws-room-picker__lead">Send to</span>
      </div>
      <div class="ws-room-grid">${tiles}</div>
    </div>`;
  }

  function quickNotesHtml(ctx) {
    const stationRaw = ctx.stationLabel || "Workstation";
    const prompts = messagePromptsFor(ctx);
    const editing = !!ctx.workstationPromptsEditing;
    if (editing) return promptsUnderMessageHtml(ctx);
    const tiles = prompts.map((p) => promptTile(p.label, p.template, stationRaw)).join("");
    return `<div class="ws-sn-quick">
      <div class="ws-sn-quick__head">
        <span class="ws-compose-col__label">Quick send</span>
        <button type="button" class="ws-prompt-edit-btn ws-prompt-edit-btn--mini" data-ws-prompt-edit="1">Edit</button>
      </div>
      <div class="ws-prompt-grid ws-prompt-grid--sn">${tiles}</div>
    </div>`;
  }

  function promptsUnderMessageHtml(ctx) {
    const stationRaw = ctx.stationLabel || "Workstation";
    const prompts = messagePromptsFor(ctx);
    const editing = !!ctx.workstationPromptsEditing;
    const toolbar = `<div class="ws-prompt-toolbar">
      <h5 class="ws-compose-col__label ws-prompt-toolbar__label">QUICK NOTES</h5>
      ${
        editing
          ? `<span class="ws-prompt-toolbar__hint">Edit quick-note text, then save. Tapping a note sends immediately.</span>`
          : `<button type="button" class="ws-prompt-edit-btn" data-ws-prompt-edit="1">EDIT</button>`
      }
    </div>`;
    if (editing) {
      const fields = prompts
        .map((p, index) => {
          const body = promptBodyFromTemplate(p.template);
          return `<label class="ws-prompt-edit-field">
            <span class="ws-prompt-edit-field__num">${index + 1}</span>
            <input
              type="text"
              class="ws-prompt-edit-input"
              data-ws-prompt-body="${index}"
              maxlength="120"
              value="${esc(body)}"
              placeholder="Quick note text…"
              aria-label="Quick note ${index + 1}"
            />
          </label>`;
        })
        .join("");
      return `<div class="ws-prompt-under ws-prompt-under--edit">
        ${toolbar}
        <div class="ws-prompt-edit-grid">${fields}</div>
        <div class="ws-prompt-edit-actions">
          <button type="button" class="hp-ask__send ws-prompt-save-btn" data-ws-prompt-save="1">${uiIcon("check")} SAVE</button>
          <button type="button" class="ws-prompt-cancel-btn" data-ws-prompt-cancel="1">Cancel</button>
          <button type="button" class="ws-prompt-reset-btn" data-ws-prompt-reset="1">Reset defaults</button>
        </div>
      </div>`;
    }
    const tiles = prompts.map((p) => promptTile(p.label, p.template, stationRaw)).join("");
    return `<div class="ws-prompt-under">
      ${toolbar}
      <div class="ws-prompt-grid">${tiles}</div>
    </div>`;
  }

  function messageComposeHtml(ctx) {
    const stationRaw = ctx.stationLabel || "Workstation";
    const station = esc(stationRaw);
    const loading = !!ctx.officeChannelLoading;
    const sentFlash = !!ctx.officeChannelSendFlash;
    const targets = officeChannelTargetList(ctx);
    const hasTargets = targets.length > 0;
    const toName = esc(targetsLabelFromList(targets));
    const pickOpen = !!ctx.officeChannelPickerOpen;
    const pickClass = pickOpen ? " ws-compose-stack--pick" : "";
    const sendClass = sentFlash
      ? "hp-ask__send ws-msg-send ws-msg-send--sent"
      : loading
        ? "hp-ask__send ws-msg-send ws-msg-send--sending"
        : "hp-ask__send ws-msg-send";
    const sendLabel = sentFlash ? "SENT" : loading ? "…" : `${uiIcon("send")} SEND`;
    const compact =
      typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY;
    if (!compact) {
      return `<div class="ws-compose-stack" id="wsComposeStack">
      <div class="ws-compose-panel" data-panel="messageCompose">
        <div class="ws-compose-head">
          <div class="ws-compose-route">
            ${stationSelectHtml(ctx)}
            <span class="ws-compose-to">
              <span class="ws-oc-badge ws-oc-badge--route">TO</span> <strong>${toName}</strong>
            </span>
          </div>
        </div>
        <div class="ws-compose-layout">
          ${workstationRailHtml(ctx)}
          <div class="ws-compose-main">
            <form class="hp-ask__box hp-live-form ws-msg-form" id="wsOfficeForm">
              <textarea class="hp-live-textarea ws-msg-input" id="wsOfficeInput" rows="3" maxlength="500" enterkeyhint="send" placeholder="Type a message or tap a quick note to send…" aria-label="Office message from ${station} to ${toName}">${esc(ctx.officeChannelDraft || "")}</textarea>
              <div class="hp-ask__bar ws-msg-bar">
                <button type="submit" class="${sendClass}" id="wsOfficeSendBtn" ${loading || !hasTargets || stationRaw === "Workstation" ? "disabled" : ""}>${sendLabel}</button>
              </div>
            </form>
            ${promptsUnderMessageHtml(ctx)}
          </div>
        </div>
      </div>
    </div>`;
    }
    return `<div class="ws-compose-stack ws-compose-stack--sn${pickClass}" id="wsComposeStack">
      <div class="ws-compose-panel ws-compose-panel--form" data-panel="messageCompose">
        <div class="ws-sn-toolbar">
          ${stationSelectHtml(ctx)}
          <button type="button" class="hp-sn-compose__to" data-ws-open-picker="1" aria-expanded="${pickOpen ? "true" : "false"}">
            <span class="ws-oc-badge ws-oc-badge--route">TO</span> <strong>${toName}</strong>
          </button>
        </div>
        ${quickNotesHtml(ctx)}
        <form class="hp-ask__box hp-live-form ws-sn-form" id="wsOfficeForm">
          <textarea class="hp-live-textarea ws-msg-input" id="wsOfficeInput" rows="2" maxlength="500" enterkeyhint="send" placeholder="Type a message…" aria-label="Office message from ${station} to ${toName}">${esc(ctx.officeChannelDraft || "")}</textarea>
          <div class="hp-ask__bar ws-msg-bar">
            <button type="submit" class="${sendClass}" id="wsOfficeSendBtn" ${loading || !hasTargets || stationRaw === "Workstation" ? "disabled" : ""}>${sendLabel}</button>
          </div>
        </form>
      </div>
      <div class="ws-compose-panel ws-compose-panel--rooms" data-panel="recipientPick">
        ${recipientPickerHtml(ctx)}
      </div>
    </div>`;
  }

  function workstationRailHtml(ctx) {
    const stations = workstationStations();
    const items = [workstationRailItem("all", "all", ctx)]
      .concat(stations.map((name) => workstationRailItem(name, name, ctx)))
      .join("");
    return `<div class="ws-compose-stations-col">
      <div class="ws-station-rail">${items}</div>
    </div>`;
  }

  function askHalChatRowsHtml(ctx) {
    const { workstationChatHistory, workstationAskLoading } = ctx;
    const messages = (workstationChatHistory || []).slice(-2);
    if (!messages.length && !workstationAskLoading) {
      return '<p class="ws-sn-hal-empty">Ask HAL about procedures, codes, policies, or patient care.</p>';
    }
    const rows = messages
      .map((m) => {
        const followups =
          m.role === "hal" && m.followUpChips && m.followUpChips.length
            ? `<div class="ws-sn-hal-chips">${m.followUpChips
                .slice(0, 3)
                .map((c) => actionChip(c.label, `data-hal-followup="${esc(c.query)}"`))
                .join("")}</div>`
            : "";
        return `<div class="ws-sn-hal-row ws-sn-hal-row--${m.role === "user" ? "user" : "hal"}">
            <div class="ws-sn-hal-row__head">
              <span>${m.role === "user" ? "You" : "HAL"}${m.lane ? ` · ${esc(m.lane)}` : ""}</span>
              ${m.role === "hal" ? `<button type="button" class="ws-sn-hal-copy" data-hal-copy-response title="Copy response">${uiIcon("copy")}</button>` : ""}
            </div>
            <p class="ws-sn-hal-row__text">${esc(m.text)}</p>
            ${followups}
          </div>`;
      })
      .join("");
    if (workstationAskLoading && (!messages.length || messages[messages.length - 1].role === "user")) {
      return (
        rows +
        `<div class="ws-sn-hal-row ws-sn-hal-row--hal ws-sn-hal-row--loading">
            <div class="ws-sn-hal-row__head"><span>HAL · thinking</span></div>
            <p class="ws-sn-hal-row__text ws-sn-hal-row__text--pulse">…</p>
          </div>`
      );
    }
    return rows;
  }

  function askHalSideNotesShell(ctx) {
    const { workstationAskDraft, workstationAskLoading } = ctx;
    const station = esc(ctx.stationLabel || "Workstation");
    const hubLive = ctx.officeHubLive === true;
    const halStatus = workstationAskLoading ? "HAL thinking…" : hubLive ? "HAL · hub live" : "HAL · local";
    const suggestions = askHalSuggestionsFor(ctx).slice(0, 4);
    const sendLabel = workstationAskLoading ? "…" : "Ask HAL";
    const chips = suggestions.length
      ? `<div class="ws-sn-hal-suggest">${suggestions.map((s) => actionChip(s, `data-hal-suggest="${esc(s)}"`)).join("")}</div>`
      : "";
    return `<div class="ws-sn-hal-shell" data-panel="askHal">
      <div class="ws-sn-hal-log" id="wsQaLog">${askHalChatRowsHtml(ctx)}</div>
      ${chips}
      <form class="ws-sn-hal-form" id="wsQaForm">
        <textarea class="ws-sn-hal-input" id="wsQaInput" rows="2" maxlength="2000" enterkeyhint="send" placeholder="Ask HAL…" aria-label="Ask HAL">${esc(workstationAskDraft || "")}</textarea>
        <button type="submit" class="ws-sn-hal-send" ${workstationAskLoading ? "disabled" : ""}>${sendLabel}</button>
      </form>
      <footer class="ws-sn-statusbar">
        <span class="ws-sn-statusbar__dot${hubLive || workstationAskLoading ? " ws-sn-statusbar__dot--live" : ""}" aria-hidden="true"></span>
        <span class="ws-sn-statusbar__station">${station} · ${esc(halStatus)}</span>
      </footer>
    </div>`;
  }

  function askHalPanelHtml(ctx) {
    const active = workstationMainTab(ctx) === "askhal";
    const compact =
      typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY;
    if (compact) {
      return `<div class="ws-page-panel ws-page-panel--askhal ws-sn-hal-panel${active ? "" : " ws-page-panel--hidden"}" role="tabpanel" aria-hidden="${active ? "false" : "true"}">
        ${askHalSideNotesShell(ctx)}
      </div>`;
    }
    const { workstationChatHistory, workstationAskDraft, workstationAskLoading } = ctx;
    const suggestions = askHalSuggestionsFor(ctx).slice(0, 4);
    const messages = (workstationChatHistory || []).slice(-1);
    const chatHtml = messages.length
      ? messages
          .map((m) => {
            const followups =
              m.role === "hal" && m.followUpChips && m.followUpChips.length
                ? `<div class="hp-chips hp-live-actions">${m.followUpChips
                    .slice(0, 3)
                    .map((c) => actionChip(c.label, `data-hal-followup="${esc(c.query)}"`))
                    .join("")}</div>`
                : "";
            return `<div class="hp-chat-row hp-chat-row--${m.role === "user" ? "user" : "hal"}">
                <div class="hp-chat-row__head">
                  <span>${m.role === "user" ? "You" : "HAL"}${m.lane ? ` · ${esc(m.lane)}` : ""}</span>
                  ${m.role === "hal" ? `<button type="button" class="hp-chat-copy" data-hal-copy-response title="Copy response">${uiIcon("copy")}</button>` : ""}
                </div>
                <p>${esc(m.text)}</p>
                ${followups}
              </div>`;
          })
          .join("")
      : '<p class="ws-empty">Ask HAL about procedures, codes, policies, or patient care.</p>';
    return `<div class="ws-page-panel ws-page-panel--askhal${active ? "" : " ws-page-panel--hidden"}" role="tabpanel" aria-hidden="${active ? "false" : "true"}">
      <section class="hp-card hp-card--ask" data-panel="askHal">
        ${cardHead("ASK HAL", "askHal", "Ask HAL about procedures, policies, and patient care", cardIconRaw("hal"))}
        <form class="hp-ask__box hp-live-form ws-ask-panel-form" id="wsQaForm">
          <textarea class="hp-live-input hp-live-textarea" id="wsQaInput" rows="2" enterkeyhint="send" placeholder="Ask HAL…" aria-label="Ask HAL">${esc(workstationAskDraft || "")}</textarea>
          <div class="hp-ask__bar">
            <button class="hp-ask__send hp-live-send" type="submit" ${workstationAskLoading ? "disabled" : ""}>${workstationAskLoading ? "…" : `${uiIcon("send")} ASK HAL`}</button>
          </div>
        </form>
        <div class="hp-inline-chat hp-inline-chat--compact" id="wsQaLog">${chatHtml}</div>
        <div class="hp-chips hp-live-actions">${suggestions.map((s) => actionChip(s, `data-hal-suggest="${esc(s)}"`)).join("")}</div>
      </section>
    </div>`;
  }

  function messageTargetsLabel(m) {
    if (typeof OfficeHub !== "undefined" && OfficeHub.normalizeTargets) {
      const { targets } = OfficeHub.normalizeTargets(m || {});
      return targetsLabelFromList(targets);
    }
    return targetLabel(m && m.target);
  }

  function mergedInboxMessages(ctx) {
    const stationLabel = ctx.stationLabel || "Workstation";
    const officeAll = (ctx.officeChannel && ctx.officeChannel.messages) || [];
    const office = officeMessagesForStation(officeAll, stationLabel).map((m) =>
      Object.assign({}, m, { _source: "office" }),
    );
    const snRaw = Array.isArray(ctx.sidenotesMessages) ? ctx.sidenotesMessages : [];
    const sn = snRaw
      .filter((m) => {
        if (typeof SideNotesHub !== "undefined" && SideNotesHub.messageTargetsForStation) {
          return SideNotesHub.messageTargetsForStation(m, stationLabel);
        }
        return true;
      })
      .filter((m) => String(m.text || "").trim())
      .map((m) => Object.assign({}, m, { _source: "sidenotes" }));
    const seen = new Set();
    const merged = [];
    office.forEach((m) => {
      const key = String(m.id || `${m.from}-${m.at}-${m.text}`);
      if (seen.has(key)) return;
      seen.add(key);
      merged.push(m);
    });
    sn.forEach((m) => {
      const key = String(m.id || `${m.from}-${m.at}-${m.text}`);
      if (seen.has(key)) return;
      seen.add(key);
      merged.push(m);
    });
    return merged
      .sort((a, b) => String(a.at || "").localeCompare(String(b.at || "")))
      .slice(-48);
  }

  function officeChannelSentHtml(ctx) {
    const hubLive = ctx.officeHubLive !== false || ctx.sidenotesLive === true;
    const stationLabel = ctx.stationLabel || "Workstation";
    const messages = mergedInboxMessages(ctx);
    const statusBadge = hubLive
      ? '<span class="ws-oc-badge ws-oc-badge--ok">LIVE</span>'
      : '<span class="ws-oc-badge ws-oc-badge--off">OFFLINE</span>';
    const listHtml = messageListHtml(
      messages,
      ctx,
      stationLabel,
      "Messages you send and messages routed to you appear here.",
    );
    return `<div class="ws-msg-feed" data-panel="officeChannel">
      <div class="ws-msg-feed__head">
        <h4 class="ws-msg-feed__title">Inbox</h4>
        ${statusBadge}
      </div>
      <ul class="ws-msg-list" id="wsOfficeLog">${listHtml}</ul>
    </div>`;
  }

  function workstationMainTab(ctx) {
    const tab = String(ctx.workstationMainTab || "send").toLowerCase();
    if (tab === "askhal") return "askhal";
    if (tab === "history") return "history";
    if (tab === "officechat") return "officechat";
    if (tab === "sync") return "sync";
    return "send";
  }

  function syncPanelHtml(ctx) {
    const active = workstationMainTab(ctx) === "sync";
    const status = ctx.workstationSyncStatus || {};
    const loading = !!status.loading;
    const message = status.message || "Trigger QuickBooks or SoftDent sync from this workstation.";
    const consent = status.consentEnabled !== false;
    const disabled = loading || !consent ? " disabled" : "";
    const consentNote = consent
      ? ""
      : '<p class="ws-sync-note">Sync disabled — set NR2_CONSENT_EXECUTOR=1 on the NR2 server.</p>';
    return `<div class="ws-page-panel ws-page-panel--sync${active ? "" : " ws-page-panel--hidden"}" role="tabpanel" aria-hidden="${active ? "false" : "true"}">
      <section class="widget-card ws-sync-panel" data-panel="workstationSync">
        ${cardHead("DATA SYNC", "workstationSync", "QuickBooks and SoftDent refresh", cardIconRaw("nav", "quickbooks"))}
        <p class="widget-meta">${esc(message)}</p>
        ${consentNote}
        <div class="prompt-chips prompt-chips--live ws-sync-actions">
          <button type="button" class="prompt-chip prompt-chip--action" data-ws-sync="qb"${disabled}>${uiIcon("check")} Sync QuickBooks</button>
          <button type="button" class="prompt-chip prompt-chip--action" data-ws-sync="softdent"${disabled}>${uiIcon("check")} Sync SoftDent</button>
          <button type="button" class="prompt-chip prompt-chip--action" data-ws-sync="imports"${disabled}>Refresh imports</button>
          <button type="button" class="prompt-chip" data-ws-open-hal>Open HAL hub (8765)</button>
        </div>
        ${status.lastHealth ? `<p class="widget-footer">DB ${esc(String(status.lastHealth.db_size_mb != null ? status.lastHealth.db_size_mb + " MB" : "—"))} · bundle age ${esc(String(status.lastHealth.import_bundle_age_minutes != null ? status.lastHealth.import_bundle_age_minutes + "m" : "—"))}</p>` : ""}
      </section>
    </div>`;
  }

  function workstationPageTabBarHtml(ctx) {
    const compact =
      typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY;
    if (compact) return sideNotesToolbarHtml(ctx);
    const active = workstationMainTab(ctx);
    return `<div class="ws-page-tabs" role="tablist" aria-label="Workstation">
      <button type="button" class="ws-page-tab${active === "send" ? " ws-page-tab--active" : ""}" role="tab" aria-selected="${active === "send" ? "true" : "false"}" data-ws-page-tab="send">Send Message</button>
      <button type="button" class="ws-page-tab${active === "askhal" ? " ws-page-tab--active" : ""}" role="tab" aria-selected="${active === "askhal" ? "true" : "false"}" data-ws-page-tab="askhal">Ask HAL</button>
    </div>`;
  }

  function sendMessagePanelHtml(ctx) {
    const active = workstationMainTab(ctx) === "send";
    const compact =
      typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY;
    if (compact) {
      return `<div class="ws-page-panel ws-page-panel--send ws-page-panel--sn${active ? "" : " ws-page-panel--hidden"}" role="tabpanel" aria-hidden="${active ? "false" : "true"}">
        ${sideNotesComposeShell(ctx)}
      </div>`;
    }
    const hubLive = ctx.officeHubLive !== false || ctx.sidenotesLive === true;
    const inbox = ctx.halSideNotesInbox;
    const watcherOnline =
      typeof HalPage !== "undefined" && HalPage.isSideNotesInboxLive
        ? HalPage.isSideNotesInboxLive(inbox)
        : false;
    const stationCount = (inbox && inbox.monitor && inbox.monitor.stationCount) || 0;
    const totalStations =
      (inbox && inbox.monitor && inbox.monitor.totalStations) ||
      (typeof HalPage !== "undefined" && HalPage.WORKSTATION_STATIONS ? HalPage.WORKSTATION_STATIONS.length : 10);
    const channelChip = hubLive
      ? '<span class="ws-oc-badge ws-oc-badge--ok">Channel live</span>'
      : '<span class="ws-oc-badge ws-oc-badge--off">Channel offline</span>';
    const nr2Count = (inbox && inbox.monitor && inbox.monitor.nr2WorkstationCount) || 0;
    const stationChip =
      stationCount > 0
        ? `<span class="ws-oc-badge ws-oc-badge--muted">${stationCount}/${totalStations} office stations live${nr2Count ? ` (${nr2Count} NR2)` : ""}</span>`
        : "";
    const watcherChip = watcherOnline && !stationCount ? `<span class="ws-oc-badge ws-oc-badge--muted">SideNotes watcher</span>` : stationChip;
    return `<div class="ws-page-panel ws-page-panel--send${active ? "" : " ws-page-panel--hidden"}" role="tabpanel" aria-hidden="${active ? "false" : "true"}">
      <section class="hp-card hp-card--office" data-panel="officeChannel">
        ${cardHead("OFFICE MESSAGES", "sidenotes", "Send to workstations and read the office channel", cardIconRaw("ui", "send"))}
        <div class="ws-card-tools">${channelChip}${watcherChip}</div>
        ${messageComposeHtml(ctx)}
        <div class="ws-send-feed">
          ${officeChannelSentHtml(ctx)}
          <details class="ws-watcher-strip">
            <summary class="ws-watcher-strip__summary">SideNotes watcher <span class="ws-watcher-strip__hint">routing metadata only — open SideNotesIM for full text</span></summary>
            <div class="ws-watcher-strip__body">${sideNotesBlock(ctx)}</div>
          </details>
        </div>
      </section>
    </div>`;
  }

  function sideNotesBlock(ctx) {
    if (typeof HalPage !== "undefined" && HalPage.sideNotesMonitorHtml) {
      return HalPage.sideNotesMonitorHtml(
        ctx.halSideNotes,
        ctx.halSideNoteMonitor,
        ctx.halSideNotesInbox,
        ctx.nr2SidenotesHubPath,
        {
          expandWatchers: true,
          staffFacing: true,
          stationLabel: ctx.stationLabel,
          hideWorkstationRoster: true,
          hideLocalNotes: true,
        },
      );
    }
    return '<p class="hp-sn-empty">SideNotes monitor unavailable.</p>';
  }

  function render(ctx) {
    const root = ctx.root;
    if (!root) return;
    const station = esc(ctx.stationLabel || "Workstation");
    const tabsHtml = workstationPageTabBarHtml(ctx);
    const panelsHtml = `<div class="ws-page-panels">${sendMessagePanelHtml(ctx)}${historyPanelHtml(ctx)}${officeChatPanelHtml(ctx)}${syncPanelHtml(ctx)}${askHalPanelHtml(ctx)}</div>`;
    const toolbar = `<span class="hp-status"><i class="hp-status__dot hp-status__dot--ok" aria-hidden="true"></i>STATION <b>${station}</b></span>`;
    const PC = typeof PageChrome !== "undefined" ? PageChrome : null;
    const compact =
      typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY;
    if (compact) {
      root.innerHTML = `<article class="pv pv--workstation pv--app pv--workstation-compact pv--sidenotes" data-pv-page="workstation">
        ${tabsHtml}
        ${panelsHtml}
      </article>`;
    } else if (PC && typeof PC.canvasShell === "function") {
      const state =
        typeof PageViews !== "undefined" && PageViews.buildPageState
          ? PageViews.buildPageState(ctx.halData, "workstation", ctx.halWidgetFeed, ctx.halProgramSnapshot)
          : { pageId: "workstation", halData: ctx.halData };
      root.innerHTML = `<article class="pv pv--workstation pv--app pv--canvas" data-pv-page="workstation">
        ${tabsHtml}
        ${PC.canvasShell(state, { toolbarActions: toolbar, compact: true })}
        <div class="pv-canvas-body">${panelsHtml}</div>
      </article>`;
    } else {
      root.innerHTML = `${tabsHtml}${panelsHtml}`;
    }

    const qaLog = root.querySelector("#wsQaLog");
    const officeLog = root.querySelector("#wsOfficeLog");
    const chatLog = root.querySelector("#wsOfficeChatLog");
    if (qaLog) qaLog.scrollTop = qaLog.scrollHeight;
    if (officeLog) officeLog.scrollTop = 0;
    if (chatLog) chatLog.scrollTop = chatLog.scrollHeight;
  }

  return {
    render,
    defaultMessagePrompts,
    normalizeMessagePrompts,
    promptBodyFromTemplate,
    templateFromPromptBody,
    labelFromPromptBody,
  };
})();

if (typeof globalThis !== "undefined") globalThis.WorkstationPage = WorkstationPage;
