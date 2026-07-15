"""BlueNote HAL smoke test — reader, short announce, slow TTS, watcher, speak."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

NR2 = Path(__file__).resolve().parents[1] / "NewRidgeFinancial2"
if not (NR2 / "bluenote_bridge.py").is_file():
    NR2 = Path(r"C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2")

sys.path.insert(0, str(NR2))
sys.path.insert(0, str(NR2 / "bluenote-helper"))
sys.path.insert(0, str(NR2 / "sidenotes-helper"))


def main() -> int:
    print("=== BlueNote HAL smoke test ===")
    ok = True

    from bluenote_reader import bluenote_running, read_panel_name, scan_events

    running = bluenote_running()
    panel = read_panel_name()
    snap = scan_events()
    snap_ok = snap.get("ok")
    inbox = snap.get("inboxCount")
    print(f"[reader] running={running} panel={panel!r} ok={snap_ok} inbox={inbox}")
    if not running:
        ok = False
        print("[reader] FAIL BlueNoteCL not running")

    from announcer import Announcer, clip_spoken_message, pick_bluenote_announcement

    script = "Open the light options window when clicking on a Popup Alert"
    clipped = clip_spoken_message(script)
    phrase = pick_bluenote_announcement("Frontdesk 2", message=script)
    print(f"[phrase] script_clip={clipped!r}")
    print(f"[phrase] announce={phrase!r} words={len(phrase.split())}")
    if clipped:
        ok = False
        print("[phrase] FAIL script was not blocked")
    if len(phrase.split()) > 12 or "options window" in phrase.lower():
        ok = False
        print("[phrase] FAIL announce too long / contains script")

    import importlib.util

    spec = importlib.util.spec_from_file_location("hal_tts", NR2 / "hal_tts.py")
    ht = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(ht)
    ssml = ht.segments_to_ssml([{"text": phrase}])
    rate_ok = 'rate="-28%"' in ssml
    print(f"[tts] rate_-28%={rate_ok}")
    if not rate_ok:
        ok = False
        print("[tts] FAIL expected rate -28%")

    from bluenote_bridge import bluenote_status, ensure_bluenote_watcher

    st = bluenote_status()
    print(
        f"[bridge] watcherRunning={st['watcher']['watcherRunning']} pid={st['watcher']['watcherPid']}"
    )
    if not st["watcher"]["watcherRunning"]:
        r = ensure_bluenote_watcher()
        print(f"[bridge] started {r}")
        time.sleep(2)
        st = bluenote_status()
    print(f"[bridge] final watcherRunning={st['watcher']['watcherRunning']}")
    if not st["watcher"]["watcherRunning"]:
        ok = False
        print("[bridge] FAIL watcher not running")

    hub = Path(r"C:\softdent\HAL-BlueNote-Workstation\data\sidenotes-inbox.json")
    site = NR2 / "site" / "data" / "sidenotes-inbox.json"
    for p in (hub, site):
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            mon = data.get("monitor") or {}
            src = (data.get("meta") or {}).get("source")
            print(
                f"[inbox] {p.name} source={src} checked={mon.get('checkedAt')} station={mon.get('station')}"
            )
        else:
            print(f"[inbox] MISSING {p}")

    neural = Path(r"C:\Users\mreno\newridgefamilyfinancial\.venv\Scripts\python.exe")
    a = Announcer(
        rate=-2,
        volume=100,
        voice_style="hal9000",
        neural_tts=True,
        neural_python=str(neural),
    )
    sample = pick_bluenote_announcement("Frontdesk 2")
    print(f"[speak] {sample}")
    a.speak(sample)
    print(f"[speak] engine={a.last_engine}")
    if "edge" not in str(a.last_engine):
        ok = False
        print("[speak] FAIL expected edge-neural engine")

    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
