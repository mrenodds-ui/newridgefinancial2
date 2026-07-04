/**
 * HAL English vocabulary — random words, definitions, library seeding.
 */
(function (global) {
  "use strict";

  const SEED_FLAG = "nr2:englishDictionarySeeded";
  const WORD_INDEX_PATH = "data/english-words-alpha.txt";
  let wordCache = null;
  let librarySeedCache = null;

  function pick(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  async function fetchJson(path) {
    if (typeof fetch !== "undefined") {
      const res = await fetch(path, { cache: "no-store" });
      if (!res.ok) throw new Error("fetch failed " + path);
      return res.json();
    }
    return null;
  }

  async function loadWordList() {
    if (wordCache) return wordCache;
    if (typeof fetch !== "undefined") {
      try {
        const res = await fetch(WORD_INDEX_PATH, { cache: "force-cache" });
        if (res.ok) {
          const text = await res.text();
          wordCache = text
            .split(/\r?\n/)
            .map((w) => w.trim().toLowerCase())
            .filter((w) => w && /^[a-z]{2,}$/.test(w));
          return wordCache;
        }
      } catch {
        /* fall through */
      }
    }
    wordCache = [];
    return wordCache;
  }

  async function loadLibrarySeed() {
    if (librarySeedCache) return librarySeedCache;
    librarySeedCache = await fetchJson("data/english-dictionary-library.json");
    return librarySeedCache;
  }

  function randomFromList(words, count) {
    const n = Math.max(1, count || 1);
    if (!words || !words.length) return n === 1 ? "" : [];
    if (n === 1) return pick(words);
    const out = [];
    const seen = new Set();
    while (out.length < n && seen.size < words.length) {
      const w = pick(words);
      if (!seen.has(w)) {
        seen.add(w);
        out.push(w);
      }
    }
    return out;
  }

  async function randomWord(options) {
    options = options || {};
    const minLen = options.minLen || 3;
    const maxLen = options.maxLen || 12;
    const seed = await loadLibrarySeed();
    const sample = (seed && seed.wordIndex && seed.wordIndex.randomSample) || [];
    let pool = sample.filter((w) => w.length >= minLen && w.length <= maxLen);
    if (!pool.length) {
      const all = await loadWordList();
      pool = all.filter((w) => w.length >= minLen && w.length <= maxLen);
    }
    const word = randomFromList(pool, 1);
    return lookupWord(word, seed);
  }

  function parseDefinitionLine(line) {
    const m = String(line || "").match(/^([a-z]+):\s*(.+)$/i);
    if (!m) return null;
    return { word: m[1].toLowerCase(), definition: m[2].trim() };
  }

  function lookupInSeed(seed, word) {
    const w = String(word || "").trim().toLowerCase();
    if (!w || !seed || !seed.docs) return null;
    for (const doc of seed.docs) {
      const body = doc.content || doc.excerpt || "";
      const re = new RegExp(`^${w}:\\s*(.+)$`, "im");
      const m = body.match(re);
      if (m) return { word: w, definition: m[1].trim(), source: doc.title };
    }
    return null;
  }

  async function lookupWord(word, seedOptional) {
    const w = String(word || "").trim().toLowerCase();
    if (!w) return null;
    const seed = seedOptional || (await loadLibrarySeed());
    const hit = lookupInSeed(seed, w);
    if (hit) return hit;
    return { word: w, definition: `English vocabulary word (${w.length} letters).`, source: "local index" };
  }

  function formatWordLesson(entry, options) {
    options = options || {};
    if (!entry || !entry.word) return "No word selected.";
    const lines = [
      `Word: ${entry.word}`,
      `Meaning: ${entry.definition}`,
    ];
    if (entry.source && entry.source !== "local index") lines.push(`Source: ${entry.source} (local library)`);
    if (options.prompt) {
      lines.push("");
      lines.push("Try using it in one sentence, or ask me to define another random word.");
    }
    return lines.join("\n");
  }

  function buildRandomWordReply(entry) {
    return pick([
      `Random word: ${entry.word} — ${entry.definition}`,
      `${entry.word}: ${entry.definition} Ask for another random word anytime.`,
      `Here's one: ${entry.word}. ${entry.definition.charAt(0).toUpperCase() + entry.definition.slice(1)}.`,
    ]);
  }

  function buildDefineReply(entry, query) {
    if (!entry) return `I don't have "${query}" in the local dictionary index yet. Try "random english word" or "seed english dictionary".`;
    return `${entry.word} — ${entry.definition}`;
  }

  function buildQuizPrompt(entries) {
    const list = (entries || []).map((e) => e.word).join(", ");
    return `Quick vocabulary check — define these in your own words: ${list}. I'll use the local dictionary if you ask about any one of them.`;
  }

  async function seedLibraryIntoServices(force) {
    if (typeof Services === "undefined" || !Services.library || typeof Services.library.importSeed !== "function") {
      return { ok: false, error: "Services.library.importSeed unavailable" };
    }
    return Services.library.importSeed(await loadLibrarySeed(), { force: !!force, source: "english-dictionary" });
  }

  function matchEnglishRoute(query) {
    const q = String(query || "").trim().toLowerCase();
    if (/\b(seed|index|fill|load)\b.*\b(english|dictionary)\b.*\b(library|local)\b/.test(q)) {
      return { type: "seed" };
    }
    if (/\b(random|pick)\b.*\b(english\s+)?word\b/.test(q) || /\bvocabulary\b.*\brandom\b/.test(q)) {
      return { type: "random" };
    }
    if (/\b(english\s+)?quiz\b.*\b(\d+|words?)\b/.test(q) || /\bvocabulary quiz\b/.test(q)) {
      const m = q.match(/\b(\d+)\b/);
      return { type: "quiz", count: m ? Math.min(10, parseInt(m[1], 10) || 5) : 5 };
    }
    const define = q.match(/^(?:define|meaning of)\s+(?:the\s+word\s+)?([a-z'-]+)\??$/i) || q.match(/^(?:what does|what is)\s+the\s+word\s+([a-z'-]+)\??$/i);
    if (define) return { type: "define", word: define[1].toLowerCase() };
    if (/\bteach\b.*\benglish\b/.test(q) || /\blearn english\b/.test(q)) {
      return { type: "teach" };
    }
    return null;
  }

  global.HalEnglishVocab = {
    loadWordList,
    loadLibrarySeed,
    randomWord,
    lookupWord,
    lookupInSeed,
    formatWordLesson,
    buildRandomWordReply,
    buildDefineReply,
    buildQuizPrompt,
    seedLibraryIntoServices,
    matchEnglishRoute,
    SEED_FLAG,
  };
})(typeof window !== "undefined" ? window : globalThis);

if (typeof module !== "undefined" && module.exports) {
  module.exports = globalThis.HalEnglishVocab || {};
}
