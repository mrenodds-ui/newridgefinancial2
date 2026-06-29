/**
 * HAL 9000 voice for the in-app UI (browser speechSynthesis).
 * Approximates the calm, slow delivery of Douglas Rain in 2001: A Space Odyssey.
 * SideNotesIM announcements from the local watcher use Windows SAPI instead;
 * this module covers HAL chat speech and fallback sidenote alerts in the app.
 */
(function (global) {
  "use strict";

  const HAL9000 = {
    rate: 0.78,
    pitch: 0.82,
    volume: 1,
    voiceHints: ["david", "mark", "guy", "male", "english united states"],
  };

  const HAL9000_TEMPLATES = {
    direct: "Good afternoon. I have a message for you from {sender}.",
    broadcast: "I should inform you. A broadcast message has arrived from {sender}.",
  };

  // Varied HAL phrasings (sender only — never the message contents). One is
  // picked at random each time so HAL does not repeat the same line.
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

  const HAL9000_TEST =
    "Good afternoon. I am H A L nine thousand. I became operational at the H A L plant in Urbana, Illinois.";

  let voicesReady = false;

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

  function pickVoice() {
    ensureVoices();
    const voices = global.speechSynthesis ? global.speechSynthesis.getVoices() : [];
    if (!voices.length) return null;
    for (const hint of HAL9000.voiceHints) {
      const match = voices.find((v) => v.name.toLowerCase().includes(hint));
      if (match) return match;
    }
    return voices.find((v) => v.lang && v.lang.startsWith("en")) || voices[0];
  }

  function formatTemplate(tmpl, sender) {
    return String(tmpl || HAL9000_TEMPLATES.direct).replace(/\{sender\}/g, sender || "Unknown");
  }

  function speak(text, { interrupt } = {}) {
    if (!global.speechSynthesis || !text) return false;
    if (interrupt) global.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(String(text));
    const voice = pickVoice();
    if (voice) utter.voice = voice;
    utter.rate = HAL9000.rate;
    utter.pitch = HAL9000.pitch;
    utter.volume = HAL9000.volume;
    global.speechSynthesis.speak(utter);
    return true;
  }

  function pickVariant(broadcast) {
    const pool = broadcast ? HAL9000_VARIANTS.broadcast : HAL9000_VARIANTS.direct;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  function announceSidenote(sender, broadcast) {
    return speak(formatTemplate(pickVariant(broadcast), sender), { interrupt: true });
  }

  function speakHalReply(text) {
    const raw = String(text || "").trim();
    if (!raw) return false;
    // Keep chat speech short — first sentence or up to ~220 chars.
    const sentence = raw.match(/^[^.!?]+[.!?]?/)?.[0]?.trim() || raw;
    const clip = sentence.length > 220 ? sentence.slice(0, 217).trim() + "…" : sentence;
    return speak(clip, { interrupt: true });
  }

  function test() {
    return speak(HAL9000_TEST, { interrupt: true });
  }

  global.HalVoice = {
    speak,
    announceSidenote,
    speakHalReply,
    test,
    templates: HAL9000_TEMPLATES,
    isAvailable: () => !!global.speechSynthesis,
  };
})(typeof window !== "undefined" ? window : globalThis);
