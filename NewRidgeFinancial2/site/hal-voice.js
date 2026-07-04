/**
 * HAL voice for the in-app UI (browser speechSynthesis + neural TTS).
 * Chat personality is Auto-style (clear agent); TTS delivery may still use glacial pacing.
 */
(function (global) {
  "use strict";

  const HAL9000 = {
    rate: 0.82,
    pitch: 0.82,
    volume: 1,
    voiceHints: ["david", "mark", "guy", "male", "english united states"],
    charsPerSecondAtRate1: 13.5,
    maxReplyChars: 1600,
    chatSpeechChars: 220,
    chunkPauseMs: 0,
  };

  /** Per-kind delivery — glacial film pace (Devil Wears Prada table-read whisper). */
  const STREEP_DELIVERY = {
    leanIn: { rate: 0.4, pitch: 0.76, volume: 0.7 },
    setup: { rate: 0.42, pitch: 0.77, volume: 0.66 },
    stress: { rate: 0.3, pitch: 0.73, volume: 0.72 },
    cutting: { rate: 0.36, pitch: 0.84, volume: 0.7 },
    train: { rate: 0.44, pitch: 0.77, volume: 0.71 },
    dismissal: { rate: 0.26, pitch: 0.68, volume: 0.58 },
  };

  const MIRANDA = {
    rate: 0.4,
    pitch: 0.76,
    volume: 0.7,
    voiceHints: [
      "microsoft aria",
      "aria online",
      "microsoft jenny",
      "jenny online",
      "en-us",
      "english united states",
      "microsoft michelle",
      "michelle",
      "microsoft zira",
      "zira",
      "samantha",
      "female",
    ],
    charsPerSecondAtRate1: 6.2,
    maxReplyChars: 380,
    chatSpeechChars: 280,
    chunkPauseMs: 1450,
    stressBridgeMs: 1100,
    trainPauseMs: 720,
    linePauseMs: 2400,
    dismissalPauseMs: 1900,
    voiceMaxSentences: 2,
  };

  /** Thatcher-style unexpected stress words (Miranda / editorial register). */
  const STRESS_LEXICON =
    /\b(clearer|glacial|thrills|bore|obvious|groundbreaking|reason|extraordinary|all|pace|detailsh|fascinating|absolutely|someone|questions|read-only|thrill)\b/i;

  const CUTTING_CLAUSE_RE =
    /\b(you know how|how that|is there some reason|please bore|by all means|for spring|groundbreaking)\b/i;

  const DISMISSIVE_RE = /\b(that'?s all|detailsh)\.?\s*$/i;

  /**
   * Film demo — multi-beat Streep delivery (setup → stress, Nichols cutting, dismissal).
   */
  const MIRANDA_DEMO = [
    {
      beats: [
        { text: "Please", kind: "setup", bridgeMs: 780 },
        { text: "bore someone else with your questions.", kind: "stress" },
      ],
      pauseAfter: 2600,
    },
    {
      beats: [
        { text: "I couldn't have been", kind: "setup", bridgeMs: 720 },
        { text: "clearer.", kind: "stress" },
      ],
      pauseAfter: 2200,
    },
    {
      beats: [
        { text: "By all means, move at a", kind: "setup", bridgeMs: 640 },
        { text: "glacial pace.", kind: "stress" },
      ],
      pauseAfter: 1300,
    },
    {
      beats: [{ text: "You know how that thrills me.", kind: "cutting" }],
      pauseAfter: 2600,
    },
    {
      beats: [
        { text: "Florals?", kind: "setup", bridgeMs: 880 },
        { text: "For spring?", kind: "cutting", bridgeMs: 760 },
        { text: "Groundbreaking.", kind: "stress" },
      ],
      pauseAfter: 2400,
    },
    {
      beats: [
        { text: "That's", kind: "setup", bridgeMs: 920 },
        { text: "all.", kind: "dismissal", dismissive: true },
      ],
    },
  ];

  const MIRANDA_DEMO_LINES = MIRANDA_DEMO.flatMap((group) => group.beats.map((b) => b.text));

  const HAL9000_TEMPLATES = {
    direct: "Good afternoon. I have a message for you from {sender}.",
    broadcast: "I should inform you. A broadcast message has arrived from {sender}.",
  };

  const HAL9000_VARIANTS = {
    direct: [
      "Good afternoon. I have a message for you from {sender}.",
      "Pardon the interruption. There is a new message from {sender}.",
      "I thought you should know. {sender} has sent you a message.",
      "A new message has arrived. It is from {sender}.",
      "Excuse me. {sender} would like your attention.",
      "You have a message waiting from {sender}.",
      "If I may. {sender} has just messaged you.",
      "I am detecting a new message from {sender}.",
    ],
    broadcast: [
      "I should inform you. A broadcast message has arrived from {sender}.",
      "Attention, please. {sender} has sent a message to everyone.",
      "{sender} has broadcast a message to the office.",
      "A message for everyone has arrived from {sender}.",
      "If I may. There is a broadcast from {sender}.",
      "I am relaying a broadcast. It is from {sender}.",
    ],
  };

  let voicesReady = false;
  let neuralReady = null;
  let currentAudio = null;
  let voiceProfile = "miranda-glacial-v1";

  function applyVoiceCalibration(status) {
    if (!status) return;
    if (status.profile) voiceProfile = status.profile;
    const cal = status.calibration;
    if (!cal) return;
    const timing = cal.timing;
    if (timing) {
      if (timing.chunk_pause_ms) MIRANDA.chunkPauseMs = timing.chunk_pause_ms;
      if (timing.stress_bridge_ms) MIRANDA.stressBridgeMs = timing.stress_bridge_ms;
      if (timing.line_pause_ms) MIRANDA.linePauseMs = timing.line_pause_ms;
      if (timing.dismissal_pause_ms) MIRANDA.dismissalPauseMs = timing.dismissal_pause_ms;
    }
    const browser = cal.browser_delivery;
    if (browser && typeof browser === "object") {
      Object.keys(browser).forEach((kind) => {
        if (!STREEP_DELIVERY[kind] || !browser[kind]) return;
        const vals = browser[kind];
        if (typeof vals.rate === "number") STREEP_DELIVERY[kind].rate = vals.rate;
        if (typeof vals.pitch === "number") STREEP_DELIVERY[kind].pitch = vals.pitch;
        if (typeof vals.volume === "number") STREEP_DELIVERY[kind].volume = vals.volume;
      });
      if (browser.leanIn && typeof browser.leanIn.rate === "number") {
        MIRANDA.rate = browser.leanIn.rate;
      }
    }
  }

  function ttsApiBase() {
    if (typeof global !== "undefined" && global.location && global.location.origin) {
      return global.location.origin;
    }
    return "http://127.0.0.1:8765";
  }

  async function checkNeuralTts() {
    if (neuralReady !== null) return neuralReady;
    try {
      const resp = await fetch(`${ttsApiBase()}/api/hal-tts/status`, { cache: "no-store" });
      if (!resp.ok) {
        neuralReady = false;
        return false;
      }
      const data = await resp.json();
      applyVoiceCalibration(data);
      neuralReady = Boolean(data && data.ok);
      return neuralReady;
    } catch {
      neuralReady = false;
      return false;
    }
  }

  async function synthesizeNeural(payload) {
    try {
      const resp = await fetch(`${ttsApiBase()}/api/hal-tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
        cache: "no-store",
      });
      if (!resp.ok) return null;
      const blob = await resp.blob();
      if (!blob || !blob.size) return null;
      return URL.createObjectURL(blob);
    } catch {
      return null;
    }
  }

  function playNeuralAudio(url) {
    return new Promise((resolve) => {
      if (!url) {
        resolve({ ok: false });
        return;
      }
      const audio = new Audio(url);
      currentAudio = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        if (currentAudio === audio) currentAudio = null;
        resolve({ ok: true, engine: "edge-neural" });
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        if (currentAudio === audio) currentAudio = null;
        resolve({ ok: false });
      };
      audio.play().catch(() => {
        URL.revokeObjectURL(url);
        if (currentAudio === audio) currentAudio = null;
        resolve({ ok: false });
      });
    });
  }

  function isSpeaking() {
    if (currentAudio && !currentAudio.paused && !currentAudio.ended) return true;
    return !!(global.speechSynthesis && global.speechSynthesis.speaking);
  }

  function ensureVoices() {
    if (!global.speechSynthesis) return;
    if (voicesReady && global.speechSynthesis.getVoices().length) return;
    global.speechSynthesis.getVoices();
    voicesReady = true;
  }

  if (global.speechSynthesis) {
    global.speechSynthesis.addEventListener("voiceschanged", () => {
      voicesReady = true;
    });
    ensureVoices();
  }

  function scoreMirandaVoice(voice) {
    const name = String(voice.name || "").toLowerCase();
    const lang = String(voice.lang || "").toLowerCase();
    let score = 0;
    if (lang.startsWith("en-us")) score += 65;
    if (/aria|jenny|michelle/.test(name) && !/zira/.test(name)) score += 48;
    if (/neural|natural|online/.test(name)) score += 22;
    if (/zira/.test(name)) score += 10;
    if (/female/.test(name)) score += 8;
    if (lang.startsWith("en-gb")) score -= 40;
    if (/sonia|libby|hazel|susan|george|ryan/.test(name)) score -= 30;
    if (/male|david|mark|guy|james/.test(name)) score -= 120;
    if (lang.startsWith("en")) score += 5;
    return score;
  }

  function pickVoice(hints) {
    ensureVoices();
    const voices = global.speechSynthesis ? global.speechSynthesis.getVoices() : [];
    if (!voices.length) return null;

    const list = hints || MIRANDA.voiceHints;
    for (const hint of list) {
      const hintLower = String(hint).toLowerCase();
      const match = voices.find((v) => {
        const name = v.name.toLowerCase();
        const lang = String(v.lang || "").toLowerCase();
        if (hintLower === "female") {
          return /female|zira|aria|jenny|samantha|susan|victoria|hazel|sonia|libby|michelle/i.test(name);
        }
        if (hintLower === "en-us" || hintLower === "english united states") {
          return lang.startsWith("en-us");
        }
        return name.includes(hintLower) || lang.includes(hintLower);
      });
      if (match) return match;
    }

    const ranked = voices
      .map((v) => ({ v, score: scoreMirandaVoice(v) }))
      .filter((row) => row.score > 0)
      .sort((a, b) => b.score - a.score);
    if (ranked.length) return ranked[0].v;

    return voices.find((v) => v.lang && v.lang.startsWith("en")) || voices[0];
  }

  /** Classic SAPI voices need extra tuning — Streep is never shrill or rushed. */
  function tuneForVoice(profile, voice) {
    if (!voice) return profile;
    const name = String(voice.name || "").toLowerCase();
    if (/zira/.test(name)) {
      return {
        ...profile,
        pitch: Math.min(profile.pitch || 0.76, 0.71),
        rate: Math.min(profile.rate || 0.4, 0.36),
        volume: Math.min(profile.volume || 0.7, 0.64),
      };
    }
    if (/david|mark|guy/.test(name)) return profile;
    return profile;
  }

  function formatTemplate(tmpl, sender) {
    return String(tmpl || HAL9000_TEMPLATES.direct).replace(/\{sender\}/g, sender || "Unknown");
  }

  function normalizeReplyText(text) {
    return String(text || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function stripNaturalStreepFillers(text) {
    return String(text || "")
      .replace(/\b(like|um|uh|you know),?\s+/gi, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  /** Thatcher emphasis — comma before unexpected stress word for TTS beat. */
  function injectStreepStressMarkers(text) {
    let out = stripNaturalStreepFillers(text);
    if (!out) return out;

    out = out.replace(/\bDetails\.?\s*$/i, "Detailsh.");
    out = out.replace(/[;:—–]/g, ".");
    out = out.replace(/\.\.+/g, ".");

    out = out.replace(/\b(that's)\s+(all)\b/gi, "$1, $2");
    out = out.replace(
      new RegExp(`([^.!?]{3,}?)\\s+(${STRESS_LEXICON.source.replace(/^\\b|\\b$/g, "")})\\b`, "gi"),
      "$1, $2",
    );

    return out.replace(/,\s*,+/g, ",").replace(/\s+/g, " ").trim();
  }

  function mirandaSpokenShape(text) {
    return injectStreepStressMarkers(normalizeReplyText(text));
  }

  /** Voice reads opening beat + dismissal only — she doesn't narrate the whole essay. */
  function mirandaVoiceExcerpt(text, options) {
    options = options || {};
    const raw = mirandaSpokenShape(text);
    if (!raw) return raw;
    const maxSentences = options.maxSentences || MIRANDA.voiceMaxSentences || 2;
    const sentences = raw.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [raw];
    if (sentences.length <= maxSentences) return raw;
    let out = sentences.slice(0, maxSentences).join(" ").trim();
    const last = sentences[sentences.length - 1].trim();
    if (DISMISSIVE_RE.test(last) && !out.includes(last)) {
      out = out.replace(/[.!?]\s*$/, "") + ". " + last;
    } else if (raw.length > out.length + 60) {
      out = out.replace(/[.!?]\s*$/, "") + ". The rest is on screen.";
    }
    return out.trim();
  }

  function isDismissiveSegment(text) {
    return DISMISSIVE_RE.test(String(text || "").trim());
  }

  function classifyFragment(text, context) {
    context = context || {};
    const t = String(text || "").trim();
    if (!t) return "leanIn";
    if (context.dismissive || isDismissiveSegment(t)) return "dismissal";
    if (STRESS_LEXICON.test(t) && t.split(/\s+/).length <= 4) return "stress";
    if (CUTTING_CLAUSE_RE.test(t)) return "cutting";
    if (context.train) return "train";
    if (context.afterSetup) return "stress";
    return context.setup ? "setup" : "leanIn";
  }

  function deliveryForKind(kind) {
    return STREEP_DELIVERY[kind] || STREEP_DELIVERY.leanIn;
  }

  function segmentOverrides(profile, segment) {
    const kind = segment.kind || (segment.dismissive ? "dismissal" : "leanIn");
    const d = deliveryForKind(kind);
    const tuned = tuneForVoice(profile, segment.voice);
    const pitchScale = tuned.pitch && profile.pitch ? tuned.pitch / profile.pitch : 1;
    const rateScale = tuned.rate && profile.rate ? tuned.rate / profile.rate : 1;
    const volScale = tuned.volume && profile.volume ? tuned.volume / profile.volume : 1;
    return {
      rate: d.rate * rateScale,
      pitch: d.pitch * pitchScale,
      volume: d.volume * volScale,
    };
  }

  function planMirandaDelivery(text, profile, options) {
    profile = profile || MIRANDA;
    options = options || {};
    const shaped = mirandaSpokenShape(text);
    if (!shaped) return [];

    const sentences = shaped.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [shaped];
    const segments = [];
    const trainMode = options.train || shaped.length > 280;

    sentences.forEach((sentence, sentenceIdx) => {
      const piece = sentence.trim();
      if (!piece) return;
      const dismissive = isDismissiveSegment(piece);
      const parts = piece.split(/,\s+/);

      if (parts.length > 1) {
        parts.forEach((part, idx) => {
          const fragment = part.trim();
          if (!fragment) return;
          const last = idx === parts.length - 1;
          const fragText = last && !/[.!?]$/.test(fragment) ? `${fragment}.` : fragment;
          const afterSetup = idx > 0;
          segments.push({
            text: fragText,
            kind: classifyFragment(fragText, {
              dismissive: dismissive && last,
              setup: idx === 0 && parts.length > 1,
              afterSetup,
              train: trainMode && sentenceIdx > 0,
            }),
            dismissive: dismissive && last,
            pauseBeforeMs: dismissive && last ? profile.dismissalPauseMs : 0,
            bridgeMs: idx < parts.length - 1 ? profile.stressBridgeMs : 0,
            train: trainMode,
          });
        });
        return;
      }

      segments.push({
        text: piece,
        kind: classifyFragment(piece, { dismissive, train: trainMode }),
        dismissive,
        pauseBeforeMs: dismissive
          ? profile.dismissalPauseMs
          : sentenceIdx > 0
            ? profile.chunkPauseMs
            : 0,
        train: trainMode,
      });
    });

    return segments.length ? segments : [{ text: shaped, kind: "leanIn", dismissive: false, pauseBeforeMs: 0 }];
  }

  function bridgeMsFor(segment, profile) {
    if (segment.bridgeMs) return segment.bridgeMs;
    if (segment.kind === "setup") return profile.stressBridgeMs;
    if (segment.train) return profile.trainPauseMs;
    return profile.chunkPauseMs;
  }

  function estimateDurationMs(text, profile) {
    const cfg = profile || MIRANDA;
    const segments = planMirandaDelivery(text, cfg);
    if (!segments.length) return 0;

    let ms = 0;
    segments.forEach((seg, idx) => {
      ms += seg.pauseBeforeMs || 0;
      const d = deliveryForKind(seg.kind || "leanIn");
      const charsPerSec = cfg.charsPerSecondAtRate1 * d.rate;
      ms += Math.max(650, Math.round((seg.text.length / charsPerSec) * 1000));
      if (idx < segments.length - 1) ms += bridgeMsFor(seg, cfg);
    });
    return Math.max(900, ms);
  }

  function cancelSpeech() {
    let stopped = false;
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.removeAttribute("src");
      currentAudio.load();
      currentAudio = null;
      stopped = true;
    }
    if (global.speechSynthesis) {
      global.speechSynthesis.cancel();
      stopped = true;
    }
    return stopped;
  }

  function applyUtterance(utter, profile, voice, overrides) {
    overrides = overrides || {};
    if (voice) utter.voice = voice;
    utter.rate = overrides.rate != null ? overrides.rate : profile.rate;
    utter.pitch = overrides.pitch != null ? overrides.pitch : profile.pitch;
    utter.volume = overrides.volume != null ? overrides.volume : profile.volume;
  }

  function speakMirandaDelivery(segments, profile, voice) {
    if (!global.speechSynthesis || !segments.length) return false;
    let index = 0;

    const next = () => {
      if (index >= segments.length) return;
      const seg = segments[index++];

      const run = () => {
        const utter = new SpeechSynthesisUtterance(seg.text);
        applyUtterance(utter, profile, voice, segmentOverrides(profile, { ...seg, voice }));
        utter.onend = () => {
          if (index < segments.length) {
            const pause = bridgeMsFor(seg, profile);
            setTimeout(next, pause);
          }
        };
        utter.onerror = () => {
          if (index < segments.length) next();
        };
        global.speechSynthesis.speak(utter);
      };

      if (seg.pauseBeforeMs) setTimeout(run, seg.pauseBeforeMs);
      else run();
    };

    next();
    return true;
  }

  function speakQueued(chunks, profile, voice) {
    if (!global.speechSynthesis || !chunks.length) return false;
    let index = 0;
    const next = () => {
      if (index >= chunks.length) return;
      const chunk = chunks[index++];
      if (!chunk) {
        next();
        return;
      }
      const utter = new SpeechSynthesisUtterance(chunk);
      applyUtterance(utter, profile, voice);
      utter.onend = () => {
        if (index < chunks.length && profile.chunkPauseMs) {
          setTimeout(next, profile.chunkPauseMs);
        } else {
          next();
        }
      };
      global.speechSynthesis.speak(utter);
    };
    next();
    return true;
  }

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function speakPromise(text, { interrupt, profile, voice, overrides, pauseBeforeMs } = {}) {
    return new Promise((resolve) => {
      if (!global.speechSynthesis || !text) {
        resolve(false);
        return;
      }
      if (interrupt) cancelSpeech();
      const cfg = profile || MIRANDA;
      const picked = voice || pickVoice(cfg.voiceHints);
      const tuned = tuneForVoice(cfg, picked);

      const run = () => {
        const utter = new SpeechSynthesisUtterance(String(text));
        applyUtterance(utter, tuned, picked, overrides);
        utter.onend = () => resolve({ ok: true, voiceName: picked ? picked.name : "" });
        utter.onerror = () => resolve({ ok: false, voiceName: picked ? picked.name : "" });
        global.speechSynthesis.speak(utter);
      };

      if (pauseBeforeMs) setTimeout(run, pauseBeforeMs);
      else run();
    });
  }

  async function speakBeat(beat, profile, voice, interrupt) {
    const kind = beat.kind || "leanIn";
    const overrides = segmentOverrides(profile, { ...beat, kind, voice });
    return speakPromise(beat.text, {
      interrupt,
      profile,
      voice,
      overrides,
      pauseBeforeMs: beat.dismissive ? profile.dismissalPauseMs : 0,
    });
  }

  async function testMirandaBrowser() {
    ensureVoices();
    const voice = pickVoice(MIRANDA.voiceHints);
    let voiceName = voice ? voice.name : "";

    for (let g = 0; g < MIRANDA_DEMO.length; g++) {
      const group = MIRANDA_DEMO[g];
      for (let b = 0; b < group.beats.length; b++) {
        const beat = group.beats[b];
        const result = await speakBeat(beat, MIRANDA, voice, g === 0 && b === 0);
        if (result && result.voiceName) voiceName = result.voiceName;
        if (beat.bridgeMs) await delay(beat.bridgeMs);
      }
      if (group.pauseAfter) await delay(group.pauseAfter);
    }

    return {
      ok: true,
      voiceName,
      engine: "browser",
      lines: MIRANDA_DEMO_LINES.length,
      profile: voiceProfile + "-browser",
      techniques: ["liebling-breath", "thatcher-stress", "eastwood-lean-in", "nichols-cutting"],
    };
  }

  async function testMiranda() {
    cancelSpeech();

    if (await checkNeuralTts()) {
      const url = await synthesizeNeural({ demo: true });
      if (url) {
        const played = await playNeuralAudio(url);
        if (played.ok) {
          return {
            ok: true,
            voiceName: "en-US-AriaNeural",
            engine: "edge-neural",
            lines: MIRANDA_DEMO_LINES.length,
            profile: voiceProfile,
            techniques: ["liebling-breath", "thatcher-stress", "eastwood-lean-in", "nichols-cutting", "aria-neural"],
          };
        }
      }
    }

    return testMirandaBrowser();
  }

  function speak(text, { interrupt, profile } = {}) {
    if (!global.speechSynthesis || !text) return false;
    if (interrupt) cancelSpeech();
    const cfg = profile || MIRANDA;
    const voice = pickVoice(cfg.voiceHints || MIRANDA.voiceHints);
    const segments = planMirandaDelivery(text, cfg);
    return speakMirandaDelivery(segments, tuneForVoice(cfg, voice), voice);
  }

  function pickVariant(broadcast) {
    const pool = broadcast ? HAL9000_VARIANTS.broadcast : HAL9000_VARIANTS.direct;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  function announceSidenote(sender, broadcast) {
    return speak(formatTemplate(pickVariant(broadcast), sender), { interrupt: true, profile: HAL9000 });
  }

  function resolveSpokenText(displayText, options) {
    options = options || {};
    let base;
    if (options.spokenText) {
      base = mirandaSpokenShape(options.spokenText);
    } else if (global.HalCore && HalCore.toSpokenScript) {
      base = HalCore.toSpokenScript(displayText, options.query, options.route, {
        preferBrief: true,
      });
    } else {
      base = mirandaSpokenShape(displayText);
      const cap = options.chatCap || MIRANDA.chatSpeechChars;
      if (base.length > cap) base = base.slice(0, cap).replace(/\s+\S*$/, "") + "…";
    }
    return mirandaVoiceExcerpt(base, options);
  }

  function speakHalReplyBrowser(text, options, raw, tuned, voice, segments) {
    speakMirandaDelivery(segments, tuned, voice);
    return {
      started: true,
      durationMs: estimateDurationMs(raw, tuned),
      spokenText: raw,
      voiceName: voice ? voice.name : "",
      segments: segments.length,
      profile: voiceProfile + "-browser",
      engine: "browser",
    };
  }

  function qaSkipSpeech() {
    return !!(global._halRandomQaSkipSpeech || global.HAL_SKIP_SPEECH);
  }

  function speakHalReply(text, options) {
    options = options || {};
    const profile = MIRANDA;
    const displayText = String(text || "");
    if (!displayText) return { started: false, durationMs: 0 };
    if (options.interrupt !== false) cancelSpeech();
    if (qaSkipSpeech() || options.skipSpeech) {
      return { started: false, durationMs: 0, skipped: true, reason: "qa-skip-speech" };
    }

    const raw = resolveSpokenText(displayText, options);
    if (!raw) return { started: false, durationMs: 0 };

    const voice = pickVoice(profile.voiceHints);
    const tuned = tuneForVoice(profile, voice);
    const train = raw.length > 260 || (options.route && (options.route.useReasoning || options.route.useEscalation));
    const segments = planMirandaDelivery(raw, tuned, { train });
    const result = {
      started: true,
      durationMs: estimateDurationMs(raw, tuned),
      spokenText: raw,
      voiceName: voice ? voice.name : "",
      segments: segments.length,
      profile: voiceProfile,
      engine: "pending",
    };

    void (async () => {
      if (await checkNeuralTts()) {
        const neuralSegments = segments.map((seg) => ({
          text: seg.text,
          kind: seg.kind || (seg.dismissive ? "dismissal" : "leanIn"),
          pauseBeforeMs: seg.pauseBeforeMs || 0,
          dismissive: Boolean(seg.dismissive),
        }));
        const url = await synthesizeNeural({ segments: neuralSegments });
        if (url) {
          await playNeuralAudio(url);
          return;
        }
      }
      if (global.speechSynthesis) {
        speakHalReplyBrowser(text, options, raw, tuned, voice, segments);
      }
    })();

    return result;
  }

  function listVoices() {
    ensureVoices();
    return (global.speechSynthesis ? global.speechSynthesis.getVoices() : []).map((v) => ({
      name: v.name,
      lang: v.lang,
      score: scoreMirandaVoice(v),
    }));
  }

  function test() {
    return testMiranda();
  }

  global.HalVoice = {
    speak,
    announceSidenote,
    speakHalReply,
    cancelSpeech,
    estimateDurationMs,
    test,
    testMiranda,
    pickVoice,
    listVoices,
    checkNeuralTts,
    isSpeaking,
    mirandaVoiceExcerpt,
    mirandaSpokenShape,
    planMirandaDelivery,
    injectStreepStressMarkers,
    templates: HAL9000_TEMPLATES,
    isAvailable: () => !!global.speechSynthesis || neuralReady === true,
    profiles: { chat: MIRANDA, miranda: MIRANDA, hal9000: HAL9000 },
    delivery: STREEP_DELIVERY,
    demoLines: MIRANDA_DEMO_LINES,
  };
})(typeof window !== "undefined" ? window : globalThis);
