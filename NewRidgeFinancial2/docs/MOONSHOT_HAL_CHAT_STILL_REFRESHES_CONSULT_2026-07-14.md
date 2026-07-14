# Moonshot AI — HAL Chat Still Refreshes (CONSULT ONLY)

**Date:** 2026-07-14  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10626  
**Script:** `scripts/run_moonshot_hal_chat_still_refreshes_consult.py`  
**Apply:** DO NOT APPLY until operator validates.

## Operator request (verbatim)

> ask moonshot why it still does it

---

# Verdict

The HAL chat box continues to refresh because **apex-hal-bridge.js line 58 performs a non-silent HAL remount** when the suggestion banner's "Ask HAL" button is clicked and the preferred entry point is missing. Additionally, if the chat form submission handler (not fully shown in snippets) triggers board actions that return a `navigate` directive or fails to prevent default browser form submission, the stage will remount or the browser will hard reload.

## 0. Operator Intent
Stop the HAL chat composer from wiping/remounting when the operator attempts to submit a question, ensuring the conversation persists across the interaction.

## 1. What "still does it" means (reload vs remount vs visual)
- **True browser reload**: Full page navigation (white flash, URL reload, network waterfall). Caused by `location.reload()` or unhandled `<form>` submit.
- **Apex stage remount**: `loadPage("hal")` without `{ silent: true }` wipes `#apex-stage` innerHTML and re-renders widgets. Looks like a refresh but URL doesn't change.
- **Visual glitch**: `flashStage()` (apex-motion-helper.js:22) adds `is-glitching` CSS class for 200ms, creating a "refresh feel" without actual DOM loss.

## 2. Why it can STILL happen after hal-10626
Ranked by likelihood based on provided code:

| Rank | Cause | File:Line | Evidence |
|------|-------|-----------|----------|
| 1 | **Bridge fallback non-silent remount** | apex-hal-bridge.js:58 | `window.Apex.loadPage("hal")` called without `{ silent: true }` when `askHalFromBridge` is undefined. Clicking "Ask HAL" in the suggestion banner triggers a full HAL remount, wiping the composer. |
| 2 | **Board action navigate to HAL** | apex-core.js:5327 | `runHalBoardActions` processes `type: "navigate"` with `await loadPage(page)` (no silent flag). If the chat submission triggers a HAL board response containing `"navigate":"hal"`, the stage remounts. |
| 3 | **Chat form default submission** | *(implied, not in snippets)* | If the HAL chat `<form>` submit handler omits `event.preventDefault()`, the browser performs a full POST/GET reload. |
| 4 | **Silent refresh_page glitch** | apex-core.js:5331 | `refresh_page` action calls `loadPage(currentPage, { silent: true })`. While silent, if `flashStage()` is invoked concurrently, the 200ms `is-glitching` animation can feel like a refresh. |
| 5 | **SW/build skew** | sw.js:2 | BUILD_ID is "hal-10626". If the client has a stale SW or cached `apex-hal-bridge.js` from pre-10626, the old hard-remount code may still execute. |

## 3. Most likely root cause right now
**apex-hal-bridge.js:58** — The fallback path in the suggestion banner handler. When the operator clicks "Ask HAL" in the toast banner (or if the chat widget internally falls back to this path), `loadPage("hal")` is invoked without the silent option. This destroys the current stage DOM (including the chat composer textarea) and rebuilds it, appearing as a full refresh. The fix in hal-10626 only removed the remount from `nr2-insight-sse.js`; it did not patch the bridge's fallback navigation.

## 4. Fast verify plan (operator can do in 2 minutes)
1. **DevTools Console**: Type `window.Apex.askHalFromBridge` and press Enter.  
   - If `undefined`, the fallback at line 58 will definitely fire when the banner is clicked.
2. **Sources Search**: Press Ctrl+Shift+F, search for `loadPage("hal")` (include quotes).  
   - Should show apex-hal-bridge.js line 58. If it lacks `{ silent: true }`, that's the culprit.
3. **Network Panel**: Check "Preserve log". Trigger the chat refresh.  
   - If you see a new `hal` XHR/fetch and the page URL changes/reloads, it's a hard navigation.  
   - If you see `api/hal/evaluate-query` followed by `api/apex/hal/board-actions` returning `"navigate":"hal"`, it's the board action remount (apex-core.js:5327).
4. **Application > Service Workers**: Check if SW status shows "Update found" or a different BUILD_ID than hal-10626. If so, hard refresh (Ctrl+F5) to clear skew.

## 5. Minimal fix package (paste-ready only if needed)
**File**: `apex-hal-bridge.js`  
**Change**: Pass `{ silent: true }` to preserve the chat composer state.

```javascript
// Line 55-60
} else if (window.Apex && typeof window.Apex.loadPage === "function") {
  window.Apex.loadPage("hal", { silent: true }); // Add { silent: true }
}
```

**Additional safeguard** (if chat form exists in unshown code):
```javascript
// In HAL chat form submit handler
event.preventDefault();
event.stopPropagation();
```

## 6. Do Not Apply Gate
Do not apply the code change until:
- You have verified in DevTools that `askHalFromBridge` is missing or that `loadPage("hal")` is called without the silent flag (Step 4 above).
- You have confirmed the operator is not experiencing a browser hard reload (which would indicate a missing `preventDefault()` rather than the bridge fallback).