# Moonshot HAL 190Q Fix — Phase 3 APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_HAL_190Q_WHATS_NEXT_2026-07-12.md`  
**Operator:** proceed  

## Goal

Cut perceived latency by painting tokens as they arrive (TTFT), with early typing meta, anti-proxy buffering headers, Apex chat streaming, and no fake typewriter after live streams.

## Applied (real paths)

| Piece | Where |
|-------|--------|
| Early `status: typing` / `ttft` SSE meta | `nr2_hal_gateway.evaluate_query_sse_frames` |
| `X-Accel-Buffering: no` + keep-alive on chat SSE | `nr2_http_server` `POST /api/v1/hal/stream-sse` |
| `onToken` passes **accumulated** text (matches cloud/app.js) | `desktop-bridge.evaluateHalQueryStream` |
| `nr2-hal-stream-typing` event | `desktop-bridge.js` |
| Apex `askHal` progressive SSE when DesktopBridge available | `apex-core.js` |
| Skip workstation typewriter after live stream | `app.js` (`streamedLive`) |
| Streaming caret CSS | `styles.css` |
| Tests | `test_hal_stream_ttft.py` |

## Honesty / unchanged

- Phase 2 deliverable asks still aggregate (JSON→markdown) before emit  
- Orchestrator path remains non-stream JSON  
- Empty ≠ $0 / no invented dollars unchanged  

## Validate

1. `python -m unittest test_hal_stream_ttft -q` (from `NewRidgeFinancial2/`)  
2. Warm Apex HAL ask → pending bubble shows “HAL is typing…” then tokens grow  
3. Confirm response headers on `/api/v1/hal/stream-sse` include `X-Accel-Buffering: no`  
