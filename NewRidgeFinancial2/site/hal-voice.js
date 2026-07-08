/**
 * HAL voice for the in-app UI (browser speechSynthesis + Edge neural TTS).
 */
(function (global) {
  "use strict";

  const HAL_CHAT = {
    rate: 1.0,
    pitch: 0.95,
    volume: 1,
    voiceHints: [
      "microsoft guy",
      "guy online",
      "david",
      "mark",
      "guy",
      "male",
      "en-us",
      "english united states",
    ],
    charsPerSecondAtRate1: 14,
    maxReplyChars: 480,
    chatSpeechChars: 320,
    chunkPauseMs: 80,
    voiceMaxSentences: 3,
  };

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

  const TEST_LINE = "Good afternoon. HAL is online and ready.";

  let voicesReady = false;
  let neuralReady = null;
  let currentAudio = null;
  let speechGeneration = 0;
  let voiceProfile = "hal-conversational-v1";

  function beginSpeechGeneration() {
    speechGeneration += 1;
    cancelSpeech();
    return speechGeneration;
  }

  function speechGenerationAlive(gen) {
    return gen === speechGeneration;
  }

  function applyVoiceCalibration(status) {
    if (status && status.profile) voiceProfile = String(status.profile);
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

  function playNeuralAudio(url, gen) {
    return new Promise((resolve) => {
      if (!url) {
        resolve({ ok: false });
        return;
      }
      if (gen != null && !speechGenerationAlive(gen)) {
        URL.revokeObjectURL(url);
        resolve({ ok: false, cancelled: true });
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

  function scoreHalVoice(voice) {
    const name = String(voice.name || "").toLowerCase();
    const lang = String(voice.lang || "").toLowerCase();
    let score = 0;
    if (lang.startsWith("en-us")) score += 65;
    if (/guy|david|mark|james|ryan/.test(name)) score += 48;
    if (/neural|natural|online/.test(name)) score += 22;
    if (/male/.test(name)) score += 8;
    if (lang.startsWith("en-gb")) score -= 20;
    if (/aria|jenny|zira|samantha|female/.test(name)) score -= 40;
    if (lang.startsWith("en")) score += 5;
    return score;
  }

  function pickVoice(hints) {
    ensureVoices();
    const voices = global.speechSynthesis ? global.speechSynthesis.getVoices() : [];
    if (!voices.length) return null;

    const list = hints || HAL_CHAT.voiceHints;
    for (const hint of list) {
      const hintLower = String(hint).toLowerCase();
      const match = voices.find((v) => {
        const name = v.name.toLowerCase();
        const lang = String(v.lang || "").toLowerCase();
        if (hintLower === "male") {
          return /male|david|mark|guy|james|ryan|george/i.test(name);
        }
        if (hintLower === "en-us" || hintLower === "english united states") {
          return lang.startsWith("en-us");
        }
        return name.includes(hintLower) || lang.includes(hintLower);
      });
      if (match) return match;
    }

    const ranked = voices
      .map((v) => ({ v, score: scoreHalVoice(v) }))
      .filter((row) => row.score > 0)
      .sort((a, b) => b.score - a.score);
    if (ranked.length) return ranked[0].v;

    return voices.find((v) => v.lang && v.lang.startsWith("en")) || voices[0];
  }

  function tuneForVoice(profile, voice) {
    if (!voice) return profile;
    const name = String(voice.name || "").toLowerCase();
    if (/david|mark/.test(name)) {
      return {
        ...profile,
        pitch: Math.max(profile.pitch || 0.95, 0.9),
        rate: Math.min(profile.rate || 1.0, 0.98),
      };
    }
    return profile;
  }

  function normalizeReplyText(text) {
    return String(text || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function spokenShape(text) {
    return normalizeReplyText(text);
  }

  function voiceExcerpt(text, options) {
    options = options || {};
    const raw = spokenShape(text);
    if (!raw) return raw;
    const maxSentences = options.maxSentences || HAL_CHAT.voiceMaxSentences || 3;
    const sentences = raw.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [raw];
    if (sentences.length <= maxSentences) return raw;
    let out = sentences.slice(0, maxSentences).join(" ").trim();
    if (raw.length > out.length + 60) {
      out = out.replace(/[.!?]\s*$/, "") + ". The rest is on screen.";
    }
    return out.trim();
  }

  function chunksFromText(text, profile) {
    const cfg = profile || HAL_CHAT;
    const raw = String(text || "").trim();
    if (!raw) return [];
    const sentences = raw.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [raw];
    const maxSentences = cfg.voiceMaxSentences || HAL_CHAT.voiceMaxSentences || 3;
    return sentences.slice(0, maxSentences).map((s) => s.trim()).filter(Boolean);
  }

  function estimateConversationalDurationMs(text, profile) {
    const cfg = profile || HAL_CHAT;
    const raw = String(text || "").trim();
    if (!raw) return 0;
    const cps = cfg.charsPerSecondAtRate1 * (cfg.rate || 1);
    const pause =
      Math.max(0, (raw.match(/[.!?]+/g) || []).length - 1) * (cfg.chunkPauseMs || 80);
    return Math.max(600, Math.round((raw.length / cps) * 1000) + pause);
  }

  function estimateDurationMs(text, profile) {
    return estimateConversationalDurationMs(text, profile);
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

  function applyUtterance(utter, profile, voice) {
    if (voice) utter.voice = voice;
    utter.rate = profile.rate;
    utter.pitch = profile.pitch;
    utter.volume = profile.volume;
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

  function speakConversationalBrowser(raw, tuned, voice, gen) {
    if (gen != null && !speechGenerationAlive(gen)) {
      return { started: false, durationMs: 0, cancelled: true };
    }
    const chunks = chunksFromText(raw, tuned);
    speakQueued(chunks, tuned, voice);
    return {
      started: true,
      durationMs: estimateConversationalDurationMs(raw, tuned),
      spokenText: raw,
      voiceName: voice ? voice.name : "",
      segments: chunks.length,
      profile: voiceProfile + "-browser",
      engine: "browser",
    };
  }

  async function speakConversationalAsync(text, profile, options) {
    options = options || {};
    const cfg = profile || HAL_CHAT;
    const raw = spokenShape(text);
    if (!raw) return { started: false, durationMs: 0 };

    const gen = options._speechGen != null ? options._speechGen : beginSpeechGeneration();
    const voice = pickVoice(cfg.voiceHints);
    const tuned = tuneForVoice(cfg, voice);
    const chunks = chunksFromText(raw, tuned);
    const result = {
      started: true,
      durationMs: estimateConversationalDurationMs(raw, tuned),
      spokenText: raw,
      voiceName: voice ? voice.name : "",
      segments: chunks.length,
      profile: voiceProfile,
      engine: "pending",
    };

    if (await checkNeuralTts()) {
      if (!speechGenerationAlive(gen)) return { started: false, durationMs: 0, cancelled: true };
      const url = await synthesizeNeural({
        segments: chunks.map((chunk) => ({ text: chunk })),
        voice: "hal",
      });
      if (url && speechGenerationAlive(gen)) {
        const played = await playNeuralAudio(url, gen);
        if (played.ok) {
          return { ...result, engine: "edge-neural", voiceName: "en-US-GuyNeural" };
        }
      }
    }

    if (!speechGenerationAlive(gen)) return { started: false, durationMs: 0, cancelled: true };
    if (global.speechSynthesis) {
      return speakConversationalBrowser(raw, tuned, voice, gen);
    }
    return { started: false, durationMs: 0 };
  }

  function speak(text, { interrupt, profile } = {}) {
    if (!text) return false;
    void speakConversationalAsync(text, profile || HAL_CHAT, { interrupt: interrupt !== false });
    return true;
  }

  function independentThoughtActive(options) {
    const hm = options && options.halModels;
    if (hm && typeof HalIndependentThought !== "undefined" && HalIndependentThought.isEnabled(hm)) return true;
    if (typeof window !== "undefined" && window.halModels && typeof HalIndependentThought !== "undefined") {
      return HalIndependentThought.isEnabled(window.halModels);
    }
    return false;
  }

  function announceSidenote(sender, broadcast) {
    const name = sender || "a station";
    const line = broadcast
      ? `Broadcast from ${name}. Check SideNotes when you can.`
      : `Message from ${name}. Check SideNotes when you can.`;
    return speak(line, { interrupt: true });
  }

  function speakOfficeAnnounce(text) {
    const line = String(text || "").replace(/\s+/g, " ").trim();
    if (!line) return { started: false, durationMs: 0 };
    void speakConversationalAsync(line, HAL_CHAT, { interrupt: true });
    return {
      started: true,
      durationMs: estimateConversationalDurationMs(line, HAL_CHAT),
      spokenText: line,
      profile: voiceProfile,
      engine: "pending",
    };
  }

  function resolveSpokenText(displayText, options) {
    options = options || {};
    if (independentThoughtActive(options)) {
      const IT = typeof HalIndependentThought !== "undefined" ? HalIndependentThought : null;
      const excerpt = IT && IT.spokenExcerpt ? IT.spokenExcerpt(displayText, options.halModels || window.halModels) : null;
      if (excerpt) return excerpt;
    }
    let base;
    if (options.spokenText) {
      base = spokenShape(options.spokenText);
    } else if (global.HalCore && HalCore.toSpokenScript) {
      base = HalCore.toSpokenScript(displayText, options.query, options.route, {
        preferBrief: true,
      });
    } else {
      base = spokenShape(displayText);
      const cap = options.chatCap || HAL_CHAT.chatSpeechChars;
      if (base.length > cap) base = base.slice(0, cap).replace(/\s+\S*$/, "") + "…";
    }
    return voiceExcerpt(base, options);
  }

  function speakIndependentReply(text, options) {
    options = options || {};
    const raw = String(text || "").replace(/\s+/g, " ").trim();
    if (!raw) return { started: false, durationMs: 0 };
    const IT = typeof HalIndependentThought !== "undefined" ? HalIndependentThought : null;
    const excerpt =
      IT && IT.spokenExcerpt ? IT.spokenExcerpt(raw, options.halModels || (window && window.halModels)) : raw.slice(0, 420);
    const gen = options.interrupt !== false ? beginSpeechGeneration() : speechGeneration;
    void speakConversationalAsync(excerpt, HAL_CHAT, { _speechGen: gen });
    return {
      started: true,
      durationMs: estimateConversationalDurationMs(excerpt, HAL_CHAT),
      spokenText: excerpt,
      profile: voiceProfile,
      engine: "pending",
    };
  }

  function qaSkipSpeech() {
    return !!(global._halRandomQaSkipSpeech || global.HAL_SKIP_SPEECH);
  }

  function speakHalReply(text, options) {
    options = options || {};
    if (independentThoughtActive(options)) {
      return speakIndependentReply(text, options);
    }
    const displayText = String(text || "");
    if (!displayText) return { started: false, durationMs: 0 };
    if (qaSkipSpeech() || options.skipSpeech) {
      return { started: false, durationMs: 0, skipped: true, reason: "qa-skip-speech" };
    }

    const raw = resolveSpokenText(displayText, options);
    if (!raw) return { started: false, durationMs: 0 };

    const gen = options.interrupt !== false ? beginSpeechGeneration() : speechGeneration;
    const voice = pickVoice(HAL_CHAT.voiceHints);
    const tuned = tuneForVoice(HAL_CHAT, voice);
    const chunks = chunksFromText(raw, tuned);
    const result = {
      started: true,
      durationMs: estimateConversationalDurationMs(raw, tuned),
      spokenText: raw,
      voiceName: voice ? voice.name : "",
      segments: chunks.length,
      profile: voiceProfile,
      engine: "pending",
    };

    void speakConversationalAsync(raw, HAL_CHAT, { _speechGen: gen });

    return result;
  }

  async function speakHalBriefing(text, options) {
    options = options || {};
    if (
      typeof HalIndependentThought !== "undefined" &&
      !HalIndependentThought.allowScriptSpeech(options.halModels || (window && window.halModels))
    ) {
      return { started: false, durationMs: 0, skipped: true, reason: "independent-thought" };
    }
    const raw = String(text || "").trim();
    if (!raw || qaSkipSpeech() || options.skipSpeech) {
      return { started: false, durationMs: 0, skipped: true };
    }
    const excerpt = raw.length > 420 ? raw.slice(0, 420).replace(/\s+\S*$/, "") + "…" : raw;
    return speakConversationalAsync(excerpt, HAL_CHAT, { interrupt: true });
  }

  async function testVoice() {
    const gen = beginSpeechGeneration();
    if (await checkNeuralTts()) {
      const url = await synthesizeNeural({ test: true });
      if (url) {
        const played = await playNeuralAudio(url, gen);
        if (played.ok) {
          return {
            ok: true,
            voiceName: "en-US-GuyNeural",
            engine: "edge-neural",
            profile: voiceProfile,
          };
        }
      }
    }
    return speakConversationalAsync(TEST_LINE, HAL_CHAT, { _speechGen: gen });
  }

  function listVoices() {
    ensureVoices();
    return (global.speechSynthesis ? global.speechSynthesis.getVoices() : []).map((v) => ({
      name: v.name,
      lang: v.lang,
      score: scoreHalVoice(v),
    }));
  }

  global.HalVoice = {
    speak,
    speakHalBriefing,
    speakHal9000Briefing: speakHalBriefing,
    announceSidenote,
    speakOfficeAnnounce,
    speakHalReply,
    cancelSpeech,
    estimateDurationMs,
    estimateConversationalDurationMs,
    test: testVoice,
    testVoice,
    pickVoice,
    listVoices,
    checkNeuralTts,
    isSpeaking,
    voiceExcerpt,
    spokenShape,
    templates: HAL9000_TEMPLATES,
    isAvailable: () => !!global.speechSynthesis || neuralReady === true,
    profiles: { chat: HAL_CHAT, hal9000: HAL_CHAT },
  };
})(typeof window !== "undefined" ? window : globalThis);
