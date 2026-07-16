"""SoftDent GUI report export helpers (read-only; no SoftDent write-back).

For SoftDent data that cannot be reached via ODBC/database extract, Sign On and use
the SoftDent UI to export reports (Register / Collections / daysheet / aging / trans),
then ingest.

Drives SDWIN menus into C:\\SoftDentReportExports. Credentials are never handled
here — use softdent_signon. Menu keys come from softdent_gui_menu_map.json.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import date
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

EXPORT_ROOT = Path(r"C:\SoftDentReportExports")
EXPORT_ROOT_SHORT = r"C:\SOFTDE~1"  # SoftDent save dialog rejects some long paths
MIRROR_ROOT = Path(r"C:\SoftDent\softdentexportreports")
STATUS_ROOT = Path(r"C:\SoftDentFinancialExports")
MENU_MAP_PATH = Path(__file__).resolve().parent / "softdent_gui_menu_map.json"

PHASE1_IDS = ("register", "collections", "transactions", "daysheet", "aging")

# Post-export honesty: empty file ≠ valid SoftDent Excel (never invent $0 from ∅).
EXPORT_MIN_BYTES = 64
EXPORT_RETRY_DELAYS_SEC = (2.0, 5.0, 10.0)

# Never send SoftDent hotkeys / clicks to these (AMD Adrenalin steals focus on this PC).
_FOCUS_BLOCKLIST_SUBSTR = (
    "amd software",
    "adrenalin",
    "radeonsoftware",
    "radeon software",
    "intel® graphics",
    "intel graphics",
)


def _softdent_pids() -> set[int]:
    """PIDs for SDWIN.EXE only (Toolhelp — no nested PowerShell)."""
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    TH32CS_SNAPPROCESS = 0x00000002
    kernel32 = ctypes.windll.kernel32
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap in (0, -1, ctypes.c_void_p(-1).value):
        return set()
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    out: set[int] = set()
    try:
        if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                name = (pe.szExeFile or "").upper()
                if name.startswith("SDWIN"):
                    out.add(int(pe.th32ProcessID))
                if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return out


def _window_pid(hwnd: int) -> int | None:
    import win32process

    try:
        _, pid = win32process.GetWindowThreadProcessId(int(hwnd))
        return int(pid)
    except Exception:
        return None


def _is_blocked_focus_title(title: str) -> bool:
    lower = (title or "").strip().lower()
    return any(s in lower for s in _FOCUS_BLOCKLIST_SUBSTR)


def _minimize_focus_thieves() -> int:
    """Do NOT touch AMD windows (minimizing/activating can launch Adrenalin).

    SoftDent Reports must not use Alt+R — AMD Instant Replay steals that chord.
    Return 0 always; callers rely on SoftDent-only foreground + F10 menus.
    """
    return 0


def _force_foreground(hwnd: int) -> bool:
    """Reliable foreground activation (AttachThreadInput) for SoftDent only."""
    import ctypes
    import win32con
    import win32gui
    import win32process

    hwnd = int(hwnd)
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception:
        pass
    try:
        fg = win32gui.GetForegroundWindow()
        if fg == hwnd:
            return True
        # Never steal focus from / interact with AMD — wait and retry SoftDent only.
        fg_title = ""
        try:
            fg_title = win32gui.GetWindowText(fg) or ""
        except Exception:
            pass
        if _is_blocked_focus_title(fg_title):
            logger.warning("Foreground is focus thief %r — activating SoftDent without touching it", fg_title)
        cur_tid = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
        tgt_tid = win32process.GetWindowThreadProcessId(hwnd)[0]
        attached = False
        if cur_tid and tgt_tid and cur_tid != tgt_tid:
            attached = bool(ctypes.windll.user32.AttachThreadInput(cur_tid, tgt_tid, True))
        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        finally:
            if attached:
                ctypes.windll.user32.AttachThreadInput(cur_tid, tgt_tid, False)
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        try:
            win32gui.SetForegroundWindow(hwnd)
            return win32gui.GetForegroundWindow() == hwnd
        except Exception:
            return False


def _assert_softdent_foreground(hwnd: int | None = None) -> int:
    """Ensure SoftDent owns keyboard focus; refuse if AMD/other thief is foreground."""
    import win32gui

    target = int(hwnd or _main_softdent_hwnd())
    for attempt in range(6):
        _force_foreground(target)
        time.sleep(0.12 + 0.05 * attempt)
        fg = win32gui.GetForegroundWindow()
        fg_title = win32gui.GetWindowText(fg) or ""
        if _is_blocked_focus_title(fg_title):
            raise RuntimeError(
                f"Refusing SoftDent keys — AMD/other thief owns foreground: {fg_title!r}. "
                "Close or leave AMD alone; do not Alt+R (AMD Instant Replay)."
            )
        fg_pid = _window_pid(fg)
        sd_pids = _softdent_pids()
        if not sd_pids:
            raise RuntimeError("SoftDent (SDWIN) is not running")
        if fg_pid is not None and fg_pid in sd_pids:
            return target
        if fg == target:
            return target
        # Cursor / IDE often steals focus mid-automation — retry SoftDent only
        if "cursor" in fg_title.lower():
            continue
        if attempt == 5:
            raise RuntimeError(
                f"Refusing SoftDent keys — foreground not SoftDent: {fg_title!r}"
            )
    return target


def _send_softdent_keys(keys: str, *, pause: float = 0.05, hwnd: int | None = None) -> None:
    """Type keys only while a SoftDent window is foreground. Never sends Escape."""
    from pywinauto.keyboard import send_keys

    if "{ESC}" in keys.upper() or "{ESCAPE}" in keys.upper():
        raise RuntimeError("Escape is forbidden — it prompts SoftDent to close")
    _assert_softdent_foreground(hwnd)
    send_keys(keys, pause=pause)


def _desktop_dialogs() -> Iterable[Any]:
    """SoftDent-owned #32770 dialogs only (never AMD / other apps).

    Enumerate via win32gui first — Desktop().windows() can raise InvalidWindowHandle
    when ephemeral dialogs close mid-scan (common on 64-bit Python × 32-bit SoftDent).
    """
    import win32gui
    from pywinauto.controls.hwndwrapper import HwndWrapper

    pids = _softdent_pids()
    handles: list[int] = []

    def _cb(hwnd: int, _: Any) -> bool:
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return True
            if (win32gui.GetClassName(hwnd) or "") != "#32770":
                return True
            handles.append(int(hwnd))
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        # Last resort: pywinauto desktop scan (may raise — swallow)
        try:
            from pywinauto import Desktop

            for w in Desktop(backend="win32").windows():
                try:
                    handles.append(int(w.handle))
                except Exception:
                    continue
        except Exception:
            return

    for hwnd in handles:
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                continue
            if (win32gui.GetClassName(hwnd) or "") != "#32770":
                continue
            title = (win32gui.GetWindowText(hwnd) or "").strip()
            if _is_blocked_focus_title(title):
                continue
            pid = _window_pid(hwnd)
            if pids and pid not in pids:
                continue
            yield HwndWrapper(hwnd)
        except Exception:
            continue


def find_dialog(title: str):
    for w in _desktop_dialogs():
        if w.window_text() == title:
            return w
    return None


_PRINTER_TITLE_HINTS = (
    "print",
    "printer",
    "printing",
    "spooler",
    "default printer",
    "cannot print",
    "unable to print",
    "printer offline",
    "printer not",
    "no printers",
    "select printer",
    "looking for",
    "waiting for printer",
    "printer connection",
    "device not ready",
    "not available",
    "offline",
    "out of paper",
    "print setup",
    "print to",
)

# Dialogs we must never cancel as "printer" (export flow).
_EXPORT_DIALOG_TITLES = frozenset(
    {
        "Output Options",
        "Report Setup",
        "Select File Name",
        "Save As",
        "SoftDent Login",
        "Transactions For A Period",
    }
)


def _is_export_flow_dialog(title: str) -> bool:
    """True for SoftDent report setup / save dialogs that must never get Alt+C."""
    t = (title or "").strip()
    if t in _EXPORT_DIALOG_TITLES:
        return True
    low = t.lower()
    return (
        "transactions for a period" in low
        or low.endswith(" setup")
        or "report setup" in low
        or low in {"select file name", "save as"}
    )


def _dialog_text_blob(dlg) -> str:
    """Title + static labels for printer-detection (best-effort)."""
    parts: list[str] = []
    try:
        parts.append(dlg.window_text() or "")
    except Exception:
        pass
    try:
        for c in dlg.descendants():
            try:
                cls = (c.class_name() or "").lower()
                if cls in {"static", "button"} or "static" in cls:
                    t = (c.window_text() or "").strip()
                    if t:
                        parts.append(t)
            except Exception:
                continue
    except Exception:
        pass
    return " ".join(parts).lower()


def _is_printer_dialog(dlg) -> bool:
    blob = _dialog_text_blob(dlg)
    if not blob:
        return False
    return any(h in blob for h in _PRINTER_TITLE_HINTS)


def _keyboard_cancel_dialog(hwnd: int) -> bool:
    """Cancel a printer dialog with keyboard only. Never Escape. Never mouse/BM_CLICK.

    Order: Alt+C → Tab to Cancel + Enter/Space → more Tab+Enter.
    """
    from pywinauto.keyboard import send_keys
    import win32gui

    hwnd = int(hwnd)

    def _gone() -> bool:
        try:
            return not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd)
        except Exception:
            return True

    _force_foreground(hwnd)
    time.sleep(0.12)

    # 1) Alt+C (Cancel accelerator)
    try:
        send_keys("%c")
        time.sleep(0.45)
        if _gone():
            return True
    except Exception:
        pass

    # 2) Tab through controls; when Cancel may be focused, Enter/Space
    try:
        _force_foreground(hwnd)
        for _ in range(8):
            send_keys("{TAB}")
            time.sleep(0.07)
            send_keys("{ENTER}")
            time.sleep(0.2)
            if _gone():
                return True
            send_keys("{SPACE}")
            time.sleep(0.2)
            if _gone():
                return True
            send_keys("%c")
            time.sleep(0.25)
            if _gone():
                return True
    except Exception:
        pass
    return _gone()


def cancel_printer_dialogs(*, max_rounds: int = 10) -> int:
    """Anytime SoftDent (or Windows) asks for a printer — cancel via keyboard.

    Never Escape (SoftDent quit). Never mouse. Prefer Alt+C.
    """
    from pywinauto import Desktop

    cancelled = 0
    for _ in range(max_rounds):
        hit = False
        candidates = []
        candidates.extend(list(_desktop_dialogs()))
        try:
            for w in Desktop(backend="win32").windows():
                try:
                    if not w.is_visible() or w.class_name() != "#32770":
                        continue
                    title = (w.window_text() or "").strip()
                    if _is_blocked_focus_title(title):
                        continue
                    if _is_export_flow_dialog(title):
                        continue
                    if _is_printer_dialog(w) or any(h in title.lower() for h in _PRINTER_TITLE_HINTS):
                        candidates.append(w)
                except Exception:
                    continue
        except Exception:
            pass

        seen: set[int] = set()
        for w in candidates:
            try:
                h = int(w.handle)
            except Exception:
                continue
            if h in seen:
                continue
            seen.add(h)
            title = ""
            try:
                title = (w.window_text() or "").strip()
            except Exception:
                pass
            if _is_export_flow_dialog(title):
                continue
            # SoftDent alert with printer body text → cancel (do not OK/retry print)
            is_printer = _is_printer_dialog(w) or any(
                hint in title.lower() for hint in _PRINTER_TITLE_HINTS
            )
            if not is_printer:
                continue
            try:
                if _keyboard_cancel_dialog(h):
                    cancelled += 1
                    hit = True
                    logger.info("Keyboard-cancelled printer dialog title=%r", title)
                    time.sleep(0.35)
                    break
            except Exception as exc:
                logger.warning("Printer dialog cancel failed: %s", type(exc).__name__)
                continue
        if not hit:
            break
    return cancelled


def dismiss_softdent_alerts(*, max_rounds: int = 6) -> int:
    """Dismiss SoftDent alerts. Printer prompts → keyboard Cancel first; else Enter/OK.

    Never Escape.
    """
    dismissed = cancel_printer_dialogs(max_rounds=max(3, max_rounds))
    pids = _softdent_pids()
    for _ in range(max_rounds):
        hit = False
        # Always clear printer prompts before OK'ing anything else
        n = cancel_printer_dialogs(max_rounds=3)
        if n:
            dismissed += n
            hit = True
            continue
        for w in list(_desktop_dialogs()):
            title = (w.window_text() or "").strip()
            if title == "SoftDent Login" or _is_export_flow_dialog(title):
                continue
            if _is_printer_dialog(w):
                # Safety: cancel, never Enter (Enter may retry printer)
                if _keyboard_cancel_dialog(int(w.handle)):
                    dismissed += 1
                    hit = True
                    break
                continue
            if title not in {"SoftDent", ""}:
                continue
            pid = _window_pid(w.handle)
            if pids and pid not in pids:
                continue
            try:
                if not _force_foreground(w.handle):
                    continue
                time.sleep(0.15)
                _send_softdent_keys("{ENTER}", hwnd=int(w.handle))
                dismissed += 1
                hit = True
                time.sleep(0.3)
                break
            except Exception:
                continue
        if not hit:
            break
    return dismissed


def cancel_stale_report_dialogs(*, max_rounds: int = 8) -> int:
    """Close leftover SoftDent report/setup dialogs between multi-report pulls.

    Multi-report automation leaves Output Options / Report Setup / named report
    dialogs open when a pull fails mid-flow — that blocks the next menu open
    (ElementNotEnabled / missing Output Options). Keyboard Cancel (Alt+C) only.
    Never Escape (SoftDent quit). Never cancel SoftDent Login.
    """
    cancelled = 0
    for _ in range(max_rounds):
        hit = False
        cancel_printer_dialogs(max_rounds=2)
        for w in list(_desktop_dialogs()):
            try:
                title = (w.window_text() or "").strip()
                if not title or title == "SoftDent Login":
                    continue
                low = title.lower()
                is_stale = (
                    title in _EXPORT_DIALOG_TITLES
                    or _is_export_flow_dialog(title)
                    or low == "output options"
                    or low == "date wizard"
                    or "date wizard" in low
                    or low.endswith(" setup")
                    or " for a period" in low
                    or low in {"daysheet", "account aging", "collection summary"}
                    or ("report" in low and "softdent software" not in low)
                )
                if not is_stale:
                    continue
                if _keyboard_cancel_dialog(int(w.handle)):
                    cancelled += 1
                    hit = True
                    logger.info("Cancelled stale SoftDent report dialog title=%r", title)
                    time.sleep(0.4)
                    break
            except Exception:
                continue
        if not hit:
            break
    try:
        hwnd = _main_softdent_hwnd()
        _force_foreground(hwnd)
        time.sleep(0.25)
    except Exception:
        pass
    dismiss_softdent_alerts(max_rounds=2)
    return cancelled


def prepare_softdent_for_next_report() -> dict[str, Any]:
    """Reset SoftDent UI so the next catalog report can open cleanly."""
    out: dict[str, Any] = {"ok": False, "staleCancelled": 0, "printerCancelled": 0}
    try:
        out["printerCancelled"] = int(cancel_printer_dialogs(max_rounds=4) or 0)
        out["staleCancelled"] = int(cancel_stale_report_dialogs(max_rounds=8) or 0)
        _minimize_focus_thieves()
        hwnd = _main_softdent_hwnd()
        _force_foreground(hwnd)
        time.sleep(0.35)
        out["ok"] = True
        out["mainHwnd"] = int(hwnd)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}:{exc}"
    return out


def softdent_main_running() -> bool:
    try:
        _main_softdent_hwnd()
        return True
    except Exception:
        return False


def ensure_softdent_ready_for_gui_export(*, timeout_s: float = 60.0) -> dict[str, Any]:
    """Launch SoftDent via CS SoftDent Software.lnk + Sign On when main is down.

    Autonomous morning/HAL paths call this before Excel export. Never bare SDWIN.EXE.
    SoftDent write-back remains forbidden. empty ≠ $0.
    """
    out: dict[str, Any] = {
        "ok": False,
        "alreadyRunning": False,
        "launched": False,
        "signedOn": False,
        "steps": [],
    }
    if softdent_main_running():
        out["alreadyRunning"] = True
        out["signedOn"] = True
        out["steps"].append("already_running")
        # Still force SoftDent foreground — Optical Bench / Cursor often steal focus
        # and morning Excel export then refuses keys (empty ≠ invent path).
        try:
            hwnd = _main_softdent_hwnd()
            _force_foreground(hwnd)
            time.sleep(0.35)
            _assert_softdent_foreground(hwnd)
            out["ok"] = True
            out["focused"] = True
            out["steps"].append("focused_main")
        except Exception as exc:  # noqa: BLE001
            out["ok"] = False
            out["focused"] = False
            out["error"] = f"softDent_focus_failed: {exc}"[:240]
            out["steps"].append("focus_failed")
        return out
    try:
        from softdent_signon import ensure_softdent_signed_on

        assist = ensure_softdent_signed_on(
            timeout_s=max(15.0, float(timeout_s)),
            force_change_login=False,
        )
        out["steps"].extend(list(assist.get("steps") or []))
        out["signedOn"] = bool(assist.get("signedOn") or assist.get("ok"))
        out["launched"] = any(
            str(s).startswith("launched_via_shortcut") for s in (assist.get("steps") or [])
        )
        if assist.get("launchShortcut"):
            out["launchShortcut"] = assist.get("launchShortcut")
        if assist.get("error"):
            out["error"] = assist.get("error")
        # Give SoftDent a beat after launch/sign-on before GUI automation.
        if out["launched"] or out["signedOn"]:
            time.sleep(2.0)
        if softdent_main_running():
            out["ok"] = True
            out["steps"].append("main_window_ready")
            return out
        out["error"] = out.get("error") or (
            assist.get("error")
            or "SoftDent main window not available after launch/sign-on"
        )
        return out
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"[:240]
        return out


def _validate_export_file(path: Path, *, report_id: str = "") -> int:
    """Require a real Excel drop — empty/missing must not become money truth."""
    produced = Path(path)
    if not produced.is_file():
        raise RuntimeError(f"{report_id or 'export'}: exported file missing: {produced}")
    try:
        size = int(produced.stat().st_size)
    except OSError as exc:
        raise RuntimeError(f"{report_id or 'export'}: exported file unreadable: {exc}") from exc
    if size < EXPORT_MIN_BYTES:
        raise RuntimeError(
            f"{report_id or 'export'}: exported file too small ({size} bytes < {EXPORT_MIN_BYTES}) "
            f"at {produced} — empty ≠ $0; refuse."
        )
    return size


def _main_softdent_hwnd() -> int:
    """Main SoftDent frame owned by SDWIN — never AMD / Login dialog."""
    import win32gui
    import win32process

    pids = _softdent_pids()
    if not pids:
        raise RuntimeError("SoftDent (SDWIN) is not running")

    candidates: list[tuple[int, str, str]] = []

    def _cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if int(pid) not in pids:
                return True
            title = win32gui.GetWindowText(hwnd) or ""
            cls = win32gui.GetClassName(hwnd) or ""
            if _is_blocked_focus_title(title):
                return True
            if "login" in title.lower():
                return True
            candidates.append((int(hwnd), title, cls))
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_cb, None)
    for hwnd, title, cls in candidates:
        if "SoftDent Software" in title or "SOFTDENT" in cls.upper():
            return hwnd
    if candidates:
        return candidates[0][0]
    raise RuntimeError("SoftDent main window not found (SDWIN running but no main UI)")


def _keyboard_activate_dialog(dlg) -> None:
    """Bring a SoftDent dialog to foreground for keyboard input (no mouse)."""
    _force_foreground(int(dlg.handle))
    time.sleep(0.15)
    _assert_softdent_foreground(int(dlg.handle))


def _keyboard_press_ok(hwnd: int | None = None) -> None:
    """Press default OK via Enter (keyboard only)."""
    _send_softdent_keys("{ENTER}", hwnd=hwnd)


def _focus_main():
    """Focus SoftDent main frame for keyboard menus. No Escape. No mouse clicks."""
    import win32gui

    hwnd = _main_softdent_hwnd()
    if not _force_foreground(hwnd):
        time.sleep(0.25)
        _force_foreground(hwnd)
    _assert_softdent_foreground(hwnd)
    # set_focus via win32 only — avoid click_input (can hit AMD/other windows)
    try:
        from pywinauto import Application

        Application(backend="win32").connect(handle=hwnd).window(handle=hwnd).set_focus()
    except Exception:
        pass
    time.sleep(0.25)
    dismiss_softdent_alerts()
    # Re-assert SoftDent after dismissing alerts (never Escape — Escape asks to close).
    cancel_printer_dialogs()
    _assert_softdent_foreground(hwnd)
    return hwnd


def _softdent_click(ctrl) -> None:
    """Mouse click only if the control belongs to SoftDent (SDWIN). Never click AMD/other."""
    pids = _softdent_pids()
    try:
        hwnd = int(ctrl.handle)
    except Exception as exc:
        raise RuntimeError(f"SoftDent click: no handle ({type(exc).__name__})") from exc
    pid = _window_pid(hwnd)
    # Child controls may report parent process — also accept if SoftDent main is parent chain
    if pids and pid not in pids:
        # Walk parent hwnds
        import win32gui

        cur = hwnd
        owned = False
        for _ in range(8):
            try:
                cur = int(win32gui.GetParent(cur) or 0)
            except Exception:
                break
            if not cur:
                break
            if _window_pid(cur) in pids:
                owned = True
                break
        if not owned:
            raise RuntimeError(f"Refusing click — control pid {pid} is not SoftDent {sorted(pids)}")
    ctrl.click_input()
    time.sleep(0.2)
    cancel_printer_dialogs(max_rounds=2)


def _open_report_via_win32_menu(menu_path: str) -> bool:
    """Open SoftDent report via classic Win32 menu (mouse/menu API on SoftDent only).

    SoftDent v19 exposes a real HMENU — UIA only shows top-level bar items, so cascade
    leaves like Accounting/Registers are selected via menu_select / GetMenu.

    Example: 'Reports->Accounting->Registers->Period'
    """
    from pywinauto import Application

    _focus_main()
    cancel_printer_dialogs()
    hwnd = _main_softdent_hwnd()
    _force_foreground(hwnd)
    try:
        app = Application(backend="win32").connect(handle=hwnd)
        win = app.window(handle=hwnd)
        # SoftDent-owned window only
        if _softdent_pids() and _window_pid(hwnd) not in _softdent_pids():
            return False
        win.menu_select(menu_path)
    except Exception as exc:
        logger.warning("SoftDent menu_select(%s) failed: %s", menu_path, type(exc).__name__)
        return False
    time.sleep(0.6)
    for _ in range(24):
        cancel_printer_dialogs(max_rounds=1)
        if find_dialog("Output Options"):
            return True
        time.sleep(0.25)
    return bool(find_dialog("Output Options"))


def _open_report_via_keys(keys_after_reports_accounting: str) -> None:
    """Fallback: SoftDent menu via F10 + letters (never global Alt+R — AMD Instant Replay)."""
    _focus_main()
    cancel_printer_dialogs()
    _send_softdent_keys("{F10}")
    time.sleep(0.35)
    cancel_printer_dialogs(max_rounds=2)
    _send_softdent_keys("r")
    time.sleep(0.35)
    _send_softdent_keys("a")
    time.sleep(0.35)
    for ch in keys_after_reports_accounting:
        if ch.isspace():
            continue
        cancel_printer_dialogs(max_rounds=1)
        _send_softdent_keys(ch)
        time.sleep(0.35)
    time.sleep(0.8)
    cancel_printer_dialogs()


def _open_accounting_report(report_id: str, menu_keys: str) -> None:
    """Open SoftDent accounting report per Carestream docs.

    SoftDent is 32-bit; 64-bit Python ``menu_select`` often hits ElementNotEnabled.
    Prefer F10 keyboard for aging (and whenever win32 fails). Never Esc on SoftDent main.
    """
    # Probed on CS SoftDent v19.1.4 (classic HMENU under Reports)
    win32_paths: dict[str, list[str]] = {
        "register": ["Reports->Accounting->Registers->Period"],
        "daysheet": ["Reports->Accounting->Daysheet", "Reports->5. Daysheet"],
        "transactions": ["Reports->Accounting->Trans for a Period"],
        "aging": ["Reports->Accounting->Account Aging"],
        # Collections live under Practice Management on this build (not Accounting)
        "collections": [
            "Reports->Practice Management->Collection Reports->Summary",
            "Reports->Practice Management->Collection Reports->Reconciliation",
        ],
        "writeoff_totals": [
            "Reports->Practice Management->Insurance Reports->Writeoff Totals",
        ],
        "insurance_payment_distribution": [
            "Reports->Accounting->Insurance Payment Distribution",
            "Reports->Accounting->Insurance Check Distribution",
        ],
        "insurance_payment_analysis": [
            "Reports->Practice Management->Insurance Reports->Insurance Income",
            "Reports->Practice Management->Insurance Reports->Contractual Plan Analysis",
            "Reports->Practice Management->Production Reports->Payment Allocation",
            "Reports->Accounting->Insurance Payment Distribution",
        ],
    }
    # F10-first for reports where 64-bit menu_select is flaky on this build.
    prefer_f10 = report_id in {"aging", "daysheet", "writeoff_totals"}
    if prefer_f10:
        for keys in (menu_keys, *(report_id == "aging" and ["g", "aa", "n"] or [])):
            if not keys:
                continue
            _open_report_via_keys(str(keys))
            for _ in range(16):
                cancel_printer_dialogs(max_rounds=1)
                if find_dialog("Output Options"):
                    return
                time.sleep(0.25)
    for path in win32_paths.get(report_id) or []:
        if _open_report_via_win32_menu(path):
            return
    if not prefer_f10:
        _open_report_via_keys(menu_keys)
    if not find_dialog("Output Options") and report_id in win32_paths:
        for path in win32_paths[report_id]:
            if _open_report_via_win32_menu(path):
                return
    if not find_dialog("Output Options"):
        raise RuntimeError(
            "Output Options dialog did not appear after SoftDent menu "
            f"(report={report_id}). Ensure Excel path — Printer triggers waiting dialog."
        )


def load_menu_map(path: Path | None = None) -> dict[str, Any]:
    map_path = path or MENU_MAP_PATH
    if not map_path.is_file():
        raise FileNotFoundError(f"SoftDent GUI menu map missing: {map_path}")
    return json.loads(map_path.read_text(encoding="utf-8-sig"))


def resolve_menu_keys(report: dict[str, Any], override: str | None = None) -> str:
    if override and str(override).strip():
        return str(override).strip()
    env_name = str(report.get("menu_keys_env") or "").strip()
    if env_name:
        env_val = str(os.environ.get(env_name) or "").strip()
        if env_val:
            return env_val
    keys = str(report.get("menu_keys") or "").strip()
    if not keys:
        raise RuntimeError(f"No menu_keys for report {report.get('id')}")
    return keys


def _format_stem(template: str, start: date, end: date) -> str:
    return (
        template.replace("{yy}", f"{start.year % 100:02d}")
        .replace("{mm}", f"{start.month:02d}")
        .replace("{dd}", f"{end.day:02d}")
        .replace("{end_yy}", f"{end.year % 100:02d}")
        .replace("{end_mm}", f"{end.month:02d}")
        .replace("{end_dd}", f"{end.day:02d}")
    )


def _softdent_file_stem(short_stem: str) -> str:
    """SoftDent 'Select File Name' historically takes an 8.3-style name.

    Blind ``[:8]`` truncation turns ``AGE260715`` into ``AGE26071`` (wrong day).
    Prefer a lossless 8-char alias when the natural stem is longer.
    """
    cleaned = "".join(ch for ch in str(short_stem or "") if ch.isalnum()).upper()
    if not cleaned:
        return "EXPORT01"
    if len(cleaned) <= 8:
        return cleaned
    # AGE / DAY / WOF / IPD / IPA + yymmdd (9) → drop one letter of prefix.
    for prefix in ("AGE", "DAY", "WOF", "IPD", "IPA", "TRN", "REG", "COL"):
        if cleaned.startswith(prefix) and len(cleaned) == len(prefix) + 6:
            # AGyyMMdd / DAyyMMdd / etc. (8 chars) — keep full date.
            return (prefix[:2] + cleaned[len(prefix) :])[:8]
    # Last resort: keep head unique prefix + tail of date digits.
    return cleaned[:2] + cleaned[-6:]


def _format_canonical(template: str, start: date, end: date) -> str:
    return (
        template.replace("{start}", start.isoformat())
        .replace("{end}", end.isoformat())
        .replace("{yy}", f"{start.year % 100:02d}")
        .replace("{mm}", f"{start.month:02d}")
        .replace("{dd}", f"{end.day:02d}")
    )


def _escape_pywinauto_keys(text: str) -> str:
    """Escape pywinauto special chars so paths like SOFTDE~1 type literally (~ is Enter)."""
    out: list[str] = []
    for ch in str(text):
        if ch in {"+", "^", "%", "~", "(", ")", "{", "}", "[", "]"}:
            out.append("{" + ch + "}")
        else:
            out.append(ch)
    return "".join(out)


def _type_keys_clear_and_text(text: str, *, hwnd: int | None = None) -> None:
    """Clear current field and type text via keyboard only."""
    _send_softdent_keys("^a{BACKSPACE}", hwnd=hwnd)
    time.sleep(0.05)
    safe = _escape_pywinauto_keys(str(text))
    if safe:
        _send_softdent_keys(safe, hwnd=hwnd, pause=0.03)
    time.sleep(0.08)


def _set_edit_text_win32(edit_hwnd: int, text: str) -> None:
    """Set an Edit control via WM_SETTEXT (safe for paths with ~)."""
    import ctypes

    WM_SETTEXT = 0x000C
    buf = ctypes.create_unicode_buffer(str(text))
    ctypes.windll.user32.SendMessageW(int(edit_hwnd), WM_SETTEXT, 0, buf)


def _softdent_select_file_path(stem_only: str, current: str = "") -> str:
    """Build SoftDent Select File Name value using SoftDent's own directory.

    SoftDent v19 shows ONE edit (e.g. ``E:\\OneDrive\\Documents\\AcctAge``) plus
    static ``.XLS``. That folder is SoftDent's valid export path for this office —
    never replace it with ``C:\\SOFTDE~1`` / SoftDentReportExports (SoftDent
    rejects those as invalid directory). Only swap the file stem; NR2 copies
    into SoftDentReportExports after SoftDent writes the XLS.
    """
    stem = _softdent_file_stem(stem_only)
    cur = str(current or "").strip().strip('"')
    for suf in (".xls", ".XLS", ".xlsx", ".XLSX", ".csv", ".CSV"):
        if cur.lower().endswith(suf.lower()):
            cur = cur[: -len(suf)]
            break
    if not cur:
        raise RuntimeError(
            "SoftDent Select File Name has no path — refuse inventing a directory. "
            "SoftDent must show its own folder (e.g. OneDrive\\Documents\\AcctAge)."
        )
    p = Path(cur)
    folder = str(p.parent) if str(p.parent) not in {".", ""} else ""
    # SoftDent must already have a real folder (drive/UNC). Do not invent one.
    if not folder or folder in {".", ""} or not (
        "\\" in cur or "/" in cur or (len(cur) >= 2 and cur[1] == ":")
    ):
        raise RuntimeError(
            f"SoftDent Select File Name folder invalid/missing from {current!r}. "
            "Do not substitute SoftDentReportExports — SoftDent rejects it."
        )
    # SoftDent File dialog: SoftDentFolder\STEM (no extension — UI shows .XLS)
    return str(Path(folder) / stem)


def _focus_select_file_name_filename_edit(dlg) -> tuple[int, str]:
    """Focus SoftDent Select File Name edit; return (hwnd, current_text).

    SoftDent Account Aging uses a single path edit (folder + stem), not a bare name.
    """
    _keyboard_activate_dialog(dlg)
    try:
        from pywinauto import Application

        app = Application(backend="win32").connect(handle=int(dlg.handle))
        win = app.window(handle=int(dlg.handle))
        edits: list[Any] = []
        for e in win.descendants(class_name="Edit"):
            try:
                if e.is_visible() and e.is_enabled():
                    edits.append(e)
            except Exception:
                continue
        if not edits:
            raise RuntimeError("Select File Name has no Edit controls")
        edit = edits[0]
        try:
            cur = str(edit.window_text() or "")
        except Exception:
            cur = ""
        try:
            edit.set_focus()
        except Exception:
            _softdent_click(edit)
        time.sleep(0.12)
        return int(edit.handle), cur
    except Exception as exc:
        logger.warning(
            "Select File Name focus failed (%s)",
            type(exc).__name__,
        )
        return int(dlg.handle), ""


def _select_output_option_prompt(kind: str = "excel") -> None:
    """SoftDent Output Options: Excel, File, or Print Preview — never Printer.

    HARD RULE: never use Printer (offline hang). Prefer enabled Excel; when Excel is
    disabled SoftDent often still offers File (Select File Name) — use that for
    machine-readable period exports. Print Preview is visual-only.
    SoftDent often defaults Printer — never Enter until a safe prompt is selected.
    """
    raw = str(kind or "excel").strip().lower()
    if raw in {"printer", "print", "lpt", "spool"}:
        raise RuntimeError(
            "Refusing SoftDent Output Options 'Printer' — use Excel, File, or Print Preview only."
        )
    # excel kind: prefer Excel, fall back to File when Excel control is disabled
    want_file_export = raw in {"excel", "xls", "file", "xlsx"}
    want_preview = raw in {"print preview", "print_preview", "preview"}
    if not want_file_export and not want_preview:
        raise RuntimeError(
            f"SoftDent Output Options kind must be excel/file or print_preview (got {kind!r})"
        )

    out = None
    for _ in range(40):
        cancel_printer_dialogs(max_rounds=2)
        out = find_dialog("Output Options")
        if out:
            break
        time.sleep(0.25)
    if not out:
        raise RuntimeError("Output Options dialog did not appear")

    _keyboard_activate_dialog(out)
    hwnd = int(out.handle)

    def _btn_enabled(btn) -> bool:
        try:
            return bool(btn.is_enabled())
        except Exception:
            return True

    def _pick_button() -> str | None:
        """Click a safe output radio. Returns 'excel'|'file'|'preview' or None."""
        try:
            from pywinauto import Application

            app_out = Application(backend="win32").connect(handle=out.handle)
            d_out = app_out.window(handle=out.handle)
            excel_btn = None
            file_btn = None
            preview_btn = None
            for b in d_out.descendants(class_name="Button"):
                label = (b.window_text() or "").replace("&", "").strip()
                lab = label.lower()
                if lab == "printer":
                    continue
                if lab == "excel":
                    excel_btn = b
                elif lab == "file":
                    file_btn = b
                elif "preview" in lab:
                    preview_btn = b

            chosen = None
            target = None
            if want_preview:
                target, chosen = preview_btn, "preview"
            elif excel_btn is not None and _btn_enabled(excel_btn):
                target, chosen = excel_btn, "excel"
            elif file_btn is not None and _btn_enabled(file_btn):
                # Excel greyed out on some SoftDent states — File → Select File Name
                target, chosen = file_btn, "file"
                logger.info("SoftDent Output Options: Excel disabled — using File export")
            elif preview_btn is not None and _btn_enabled(preview_btn):
                # Last safe option for visual; caller may not ingest
                target, chosen = preview_btn, "preview"
                logger.warning(
                    "SoftDent Output Options: Excel/File unavailable — Print Preview only"
                )
            if target is None or chosen is None:
                return None
            _softdent_click(target)
            time.sleep(0.15)
            _softdent_click(target)
            time.sleep(0.12)
            return chosen
        except Exception as exc:
            logger.warning("Output Options click failed: %s", type(exc).__name__)
            return None

    chosen = _pick_button()
    if not chosen:
        # Accelerators: E=Excel, F=File. Never send P (Printer). V ≈ Pre&view.
        if want_preview:
            _send_softdent_keys("v", hwnd=hwnd)
            chosen = "preview"
        else:
            _send_softdent_keys("e", hwnd=hwnd)
            time.sleep(0.2)
            # If Excel is disabled, SoftDent may ignore E — try File (F)
            _send_softdent_keys("f", hwnd=hwnd)
            chosen = "file"
        time.sleep(0.25)

    # Sweep printer again BEFORE Enter — default Printer can still steal focus
    cancel_printer_dialogs(max_rounds=2)
    if not find_dialog("Output Options"):
        cancelled_early = cancel_printer_dialogs(max_rounds=4)
        if cancelled_early:
            raise RuntimeError(
                "SoftDent selected Printer before OK — cancelled wait. Retry Excel/File/Preview only."
            )
        raise RuntimeError("Output Options closed unexpectedly before OK")

    time.sleep(0.2)
    _send_softdent_keys("{ENTER}", hwnd=hwnd)
    time.sleep(1.0)
    cancelled = cancel_printer_dialogs(max_rounds=6)
    if cancelled:
        raise RuntimeError(
            "SoftDent opened a printer-wait dialog after Output Options — "
            "Printer must not be used. Click Excel, File, or Print Preview only, then Enter."
        )


# SoftDent Excel titles/stems: temp SDWIN*.csv OR classic short names (REG2607.XLS).
_SOFTDENT_EXCEL_STEM_PREFIXES = (
    "SDWIN",
    "REG",
    "COL",
    "AGE",
    "DAY",
    "TXN",
    "TRA",
    "WOF",
    "IPA",
    "INS",
)


def _is_softdent_excel_workbook_name(name: str, full: str = "") -> bool:
    """True for SoftDent-produced Excel workbook names (not arbitrary office files)."""
    blob = f"{name} {full}".upper()
    if "SDWIN" in blob:
        return True
    stem = Path(str(name or "").strip() or "x").stem.upper()
    if not stem:
        return False
    # Classic SoftDent short export: REGyyMM / COL / AGE260713 etc.
    return any(stem.startswith(p) for p in _SOFTDENT_EXCEL_STEM_PREFIXES)


def _excel_sdwin_workbook_open() -> bool:
    """True when SoftDent has an Excel workbook open (SDWIN* temp or REG*/COL* short)."""
    try:
        import win32gui

        found = []

        def _cb(h, _):
            if win32gui.IsWindowVisible(h):
                t = (win32gui.GetWindowText(h) or "").strip()
                tu = t.upper()
                if "EXCEL" not in tu:
                    return True
                # "REG2607 - Excel" / "SDWIN12 - Excel" / full path in title
                left = tu.split(" - EXCEL")[0].strip()
                if _is_softdent_excel_workbook_name(left, t):
                    found.append(t)
            return True

        win32gui.EnumWindows(_cb, None)
        if found:
            return True
    except Exception:
        pass
    try:
        import win32com.client

        excel = win32com.client.GetObject(Class="Excel.Application")
        for i in range(1, int(excel.Workbooks.Count) + 1):
            wb = excel.Workbooks(i)
            name = str(wb.Name or "")
            full = str(wb.FullName or "")
            if _is_softdent_excel_workbook_name(name, full):
                return True
    except Exception:
        return False
    return False


def _save_excel_sdwin_copy(dest: Path) -> Path | None:
    """SaveCopyAs SoftDent Excel workbook into dest (hal-10576 atomic + retry).

    SoftDent often opens ``%TEMP%\\SDWIN*.csv`` or short ``REG*.XLS`` and skips Select File Name.
    Finalize via NamedTemporaryFile + os.replace (empty ≠ $0; no SoftDent write-back).
    """
    try:
        import win32com.client
    except ImportError:
        return None
    try:
        excel = win32com.client.GetObject(Class="Excel.Application")
    except Exception:
        return None
    target = None
    newest_mtime = -1.0
    for i in range(1, int(excel.Workbooks.Count) + 1):
        wb = excel.Workbooks(i)
        name = str(wb.Name or "")
        full = str(wb.FullName or "")
        if not _is_softdent_excel_workbook_name(name, full):
            continue
        try:
            mtime = Path(full).stat().st_mtime if full and Path(full).is_file() else time.time()
        except OSError:
            mtime = time.time()
        if mtime >= newest_mtime:
            newest_mtime = mtime
            target = wb
    if target is None:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)

    from softdent_excel_temp import call_with_excel_temp_retry
    from softdent_practice_exports import atomic_write_excel_export

    def _save_one(candidate: Path) -> Path:
        def _write(tmp: Path, wb=target) -> None:
            wb.SaveCopyAs(str(tmp))

        meta = atomic_write_excel_export(
            candidate,
            _write,
            min_bytes=1,
            event="collections_summary_export_success",
        )
        if not candidate.is_file() or int(meta.get("bytes") or 0) < 1:
            raise OSError(f"atomic SaveCopyAs produced empty file: {candidate}")
        logger.info(
            "SoftDent Excel SaveCopyAs ok path=%s bytes=%s temp_cleanup=%s",
            candidate,
            meta.get("bytes"),
            meta.get("temp_cleanup"),
        )
        return candidate

    def _save() -> Path:
        # SoftDent temps are often .csv opened in Excel; prefer dest suffix, fall back to .csv
        try:
            return _save_one(dest)
        except Exception:
            return _save_one(dest.with_suffix(".csv"))

    try:
        return call_with_excel_temp_retry(_save)
    except Exception as exc:
        logger.warning("SoftDent Excel SaveCopyAs retry exhausted: %s", type(exc).__name__)
        return None


def _complete_output_setup_and_save(
    *,
    start: date,
    end: date,
    short_stem: str,
    dest_root: Path,
    canonical_name: str,
    also_copy_as: list[str] | None = None,
) -> Path:
    """Drive Output Options → Report Setup → Save (SoftDent keyboard/mouse only).

    Output Options: click Excel prompt, then Enter (never Printer).
    For visual-only review use open_report_print_preview (click Print Preview, then Enter;
    read last page for totals).
    No Escape on SoftDent main. Printer wait → Alt+C cancel.
    """
    dismiss_softdent_alerts()
    cancel_printer_dialogs()
    _select_output_option_prompt("excel")

    setup = None
    for _ in range(50):
        cancel_printer_dialogs(max_rounds=2)
        dismiss_softdent_alerts(max_rounds=2)
        setup = find_dialog("Report Setup")
        if not setup:
            # SoftDent titles vary: "Collection Summary Report Setup", "Register Setup", …
            pids = _softdent_pids()
            for w in _desktop_dialogs():
                try:
                    t = (w.window_text() or "").strip()
                    if not t or "softdent software" in t.lower():
                        continue
                    if pids and _window_pid(int(w.handle)) not in pids:
                        continue
                    if "setup" in t.lower():
                        setup = w
                        break
                except Exception:
                    continue
        if setup:
            break
        time.sleep(0.25)
    if not setup:
        raise RuntimeError("Report Setup dialog did not appear")

    _keyboard_activate_dialog(setup)
    start_txt = start.strftime("%m/%d/%y")
    end_txt = end.strftime("%m/%d/%y")
    # SoftDent Report Setup edits: Tab from first field → start → end → provider
    # Typical order: title, start, end, provider — Tab once into start date.
    h = int(setup.handle)
    _send_softdent_keys("{TAB}", hwnd=h)
    time.sleep(0.1)
    _type_keys_clear_and_text(start_txt, hwnd=h)
    _send_softdent_keys("{TAB}", hwnd=h)
    time.sleep(0.1)
    _type_keys_clear_and_text(end_txt, hwnd=h)
    _send_softdent_keys("{TAB}", hwnd=h)
    time.sleep(0.1)
    _type_keys_clear_and_text("999", hwnd=h)  # all providers
    time.sleep(0.15)
    _keyboard_press_ok(hwnd=h)
    time.sleep(1.0)
    cancel_printer_dialogs()
    dismiss_softdent_alerts()

    save = None
    for _ in range(60):
        cancel_printer_dialogs(max_rounds=2)
        dismiss_softdent_alerts(max_rounds=2)
        save = find_dialog("Select File Name")
        if save:
            break
        # SoftDent often skips Select File Name and opens Excel on %TEMP%\SDWIN*.csv
        if _excel_sdwin_workbook_open():
            break
        time.sleep(0.25)
    if save:
        # SoftDent Select File Name: ONE path edit (SoftDentFolder\stem) + static .XLS.
        # Keep SoftDent's folder verbatim (e.g. E:\OneDrive\Documents). Never
        # substitute SoftDentReportExports / C:\SOFTDE~1 — SoftDent rejects those.
        stem_only = _softdent_file_stem(short_stem)
        if any(ch in stem_only for ch in (":", "\\", "/", " ")):
            raise RuntimeError(
                f"Refusing SoftDent File stem {stem_only!r} — alphanumeric only"
            )
        full_stem = "".join(ch for ch in str(short_stem) if ch.isalnum()).upper()
        file_hwnd, current_path = _focus_select_file_name_filename_edit(save)
        save_path = _softdent_select_file_path(stem_only, current_path)
        logger.info(
            "SoftDent Select File Name: keep SoftDent dir, current=%r → save=%r",
            current_path,
            save_path,
        )
        try:
            _set_edit_text_win32(file_hwnd, save_path)
        except Exception:
            _type_keys_clear_and_text(save_path, hwnd=file_hwnd)
        time.sleep(0.15)
        _keyboard_press_ok(hwnd=int(save.handle))
        time.sleep(1.0)
        # SoftDent alert: dismiss only — do not invent SoftDentReportExports as retry path
        for w in list(_desktop_dialogs()):
            try:
                blob = _dialog_text_blob(w)
                bad = (
                    "invalid character" in blob
                    or "takes only file name" in blob
                    or "invalid directory" in blob
                    or "directory name" in blob
                )
                if not bad:
                    continue
                _force_foreground(int(w.handle))
                _send_softdent_keys("{ENTER}", hwnd=int(w.handle))
                time.sleep(0.35)
                raise RuntimeError(
                    f"SoftDent rejected Select File Name path {save_path!r} "
                    f"(from SoftDent field {current_path!r}). "
                    "Keep SoftDent's own folder; do not use SoftDentReportExports here."
                )
            except RuntimeError:
                raise
            except Exception:
                continue
        preferred_folder: Path | None = None
        try:
            preferred_folder = Path(save_path).parent
        except Exception:
            preferred_folder = None
        cancel_printer_dialogs()
        dismiss_softdent_alerts()
        time.sleep(2.0)

        dest_root.mkdir(parents=True, exist_ok=True)
        # SoftDent writes into SoftDent's folder; NR2 then copies into dest_root.
        min_mtime = time.time() - 180.0
        search_roots: list[Path] = []
        if preferred_folder and preferred_folder.is_dir():
            search_roots.append(preferred_folder)
        onedrive_docs = Path(r"E:\OneDrive\Documents")
        if onedrive_docs.is_dir() and onedrive_docs not in search_roots:
            search_roots.append(onedrive_docs)
        search_roots.extend(
            [
                dest_root,
                MIRROR_ROOT,
                Path(r"C:\SoftDentFinancialExports"),
                Path(r"C:\SoftDent"),
                Path(r"C:\SoftDent\softdentexportreports"),
            ]
        )
        candidates: list[Path] = []
        stem_patterns = {f"{stem_only}.*", f"{stem_only.upper()}.*"}
        if full_stem and full_stem != stem_only:
            stem_patterns.add(f"{full_stem}.*")
        # SoftDent sometimes lands classic AGE*.XLS even when File stem was aliased.
        if full_stem.startswith("AGE") or stem_only.startswith("AG"):
            stem_patterns.add("AGE*.*")
            stem_patterns.add("AG*.*")
        for root in search_roots:
            if not root.is_dir():
                continue
            for pattern in stem_patterns:
                for cand in root.glob(pattern):
                    if not cand.is_file():
                        continue
                    if cand.suffix.lower() not in {
                        ".xls",
                        ".xlsx",
                        ".csv",
                        ".txt",
                        ".rep",
                    }:
                        continue
                    try:
                        if float(cand.stat().st_mtime) < min_mtime:
                            continue
                    except OSError:
                        continue
                    candidates.append(cand)
        if not candidates:
            raise RuntimeError(
                f"Expected export not found for File stem {stem_only} "
                f"(from {short_stem!r}) under {dest_root}, {MIRROR_ROOT}, or SoftDent dirs"
            )
        # Prefer newest match; when AG* wildcards widen the net, still take mtime tip.
        produced = max(candidates, key=lambda p: p.stat().st_mtime)
    else:
        # Excel-on-temp path (validated on SoftDent v19.1.4 Trans/Register/Collections)
        dest_root.mkdir(parents=True, exist_ok=True)
        produced = _save_excel_sdwin_copy(dest_root / f"{short_stem}.xls")
        if not produced or not produced.is_file():
            raise RuntimeError(
                "Select File Name dialog did not appear and no SoftDent Excel "
                "(SDWIN*/REG*/COL*) workbook was available to SaveCopyAs"
            )

    canonical = dest_root / canonical_name
    try:
        from softdent_excel_temp import copy_file_with_retry

        copy_file_with_retry(produced, canonical)
    except Exception:
        shutil.copy2(produced, canonical)
    for extra in also_copy_as or []:
        try:
            from softdent_excel_temp import copy_file_with_retry

            copy_file_with_retry(produced, dest_root / extra)
        except OSError as exc:
            logger.warning("SoftDent extra copy %s failed: %s", extra, type(exc).__name__)
    if MIRROR_ROOT.is_dir():
        try:
            from softdent_excel_temp import copy_file_with_retry

            copy_file_with_retry(produced, MIRROR_ROOT / canonical.name)
            copy_file_with_retry(produced, MIRROR_ROOT / produced.name)
            for extra in also_copy_as or []:
                try:
                    copy_file_with_retry(produced, MIRROR_ROOT / extra)
                except OSError:
                    shutil.copy2(produced, MIRROR_ROOT / extra)
        except OSError as exc:
            logger.warning("SoftDent export mirror copy failed: %s", type(exc).__name__)
    return canonical


def export_report_by_id(
    report_id: str,
    *,
    start: date,
    end: date,
    dest_root: Path | None = None,
    menu_keys: str | None = None,
    menu_map: dict[str, Any] | None = None,
    retries: int | None = None,
) -> Path:
    """Export one catalog report with SoftDent GUI Excel path retries.

    SoftDent Select File Name keeps SoftDent's folder — never SoftDentReportExports.
    NR2 copies into EXPORT_ROOT after SoftDent saves. Retries transient dialog failures.
    """
    last_exc: BaseException | None = None
    max_attempts = 1 + len(EXPORT_RETRY_DELAYS_SEC)
    if retries is not None:
        max_attempts = max(1, int(retries) + 1)
    for attempt in range(1, max_attempts + 1):
        try:
            if not softdent_main_running():
                ready = ensure_softdent_ready_for_gui_export(timeout_s=60.0)
                if not ready.get("ok"):
                    raise RuntimeError(
                        "SoftDent desktop not running. "
                        + str(
                            ready.get("error")
                            or "Launch CS SoftDent Software.lnk (-sus), then retry."
                        )
                    )
            if attempt > 1:
                prepare_softdent_for_next_report()
            out = _export_report_by_id_once(
                report_id,
                start=start,
                end=end,
                dest_root=dest_root,
                menu_keys=menu_keys,
                menu_map=menu_map,
            )
            size = _validate_export_file(out, report_id=report_id)
            logger.info(
                "SoftDent GUI export ok report=%s attempt=%s bytes=%s path=%s",
                report_id,
                attempt,
                size,
                out,
            )
            return out
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "SoftDent GUI export failed report=%s attempt=%s/%s: %s",
                report_id,
                attempt,
                max_attempts,
                exc,
            )
            try:
                cancel_stale_report_dialogs(max_rounds=6)
                cancel_printer_dialogs(max_rounds=3)
            except Exception:
                pass
            if attempt >= max_attempts:
                break
            delay = EXPORT_RETRY_DELAYS_SEC[min(attempt - 1, len(EXPORT_RETRY_DELAYS_SEC) - 1)]
            time.sleep(delay)
    raise RuntimeError(
        f"{report_id}: SoftDent GUI export failed after {max_attempts} attempts "
        f"({type(last_exc).__name__}: {last_exc})"
    ) from last_exc


def _export_report_by_id_once(
    report_id: str,
    *,
    start: date,
    end: date,
    dest_root: Path | None = None,
    menu_keys: str | None = None,
    menu_map: dict[str, Any] | None = None,
) -> Path:
    """Single SoftDent GUI Excel export attempt (no outer retries)."""
    catalog = menu_map or load_menu_map()
    reports = catalog.get("reports") or {}
    report = reports.get(report_id)
    if not isinstance(report, dict):
        raise KeyError(f"Unknown SoftDent GUI report id: {report_id}")

    # Prefer Excel file ingest when SoftDent offers it. Print Preview path is separate
    # (click Print Preview prompt → Enter → visually read; last page for totals).
    try:
        from softdent_master_reports import load_master_reports

        master = ((load_master_reports().get("reports") or {}).get(report_id) or {})
        if bool(master.get("visualReadRequired")) and not bool(master.get("excelExport")):
            raise RuntimeError(
                f"{report_id} requires SoftDent Print Preview (click Print Preview, then Enter). "
                "Visually read the report — go to the LAST page for exact totals. "
                "Do not invent dollars."
            )
    except ImportError:
        pass
    if str(report.get("outputMode") or "").strip().lower() == "print_preview_only":
        raise RuntimeError(
            f"{report_id} is SoftDent Print Preview only — click Print Preview then Enter; "
            "read the last page for totals."
        )

    dest = dest_root or EXPORT_ROOT
    date_mode = str(report.get("date_mode") or "range")
    use_start, use_end = start, end
    if date_mode == "as_of":
        use_start = end
        use_end = end

    keys = resolve_menu_keys(report, menu_keys)
    stem = _format_stem(str(report.get("short_stem_template") or "RPT"), use_start, use_end)
    canonical = _format_canonical(
        str(report.get("canonical_template") or f"{report_id}.xls"),
        use_start,
        use_end,
    )
    also = [str(x) for x in (report.get("also_copy_as") or []) if str(x).strip()]
    # Best-effort clear prior short-stem files so SoftDent writes a fresh drop.
    before: dict[str, tuple[float, int]] = {}
    for root in (dest, MIRROR_ROOT):
        if not root.is_dir():
            continue
        for stale in list(root.glob(f"{stem}.*")):
            if not stale.is_file():
                continue
            try:
                st = stale.stat()
                before[str(stale.resolve())] = (float(st.st_mtime), int(st.st_size))
            except OSError:
                continue
            try:
                stale.unlink()
            except OSError:
                logger.warning("Could not remove stale SoftDent export %s", stale)
    _open_accounting_report(report_id, keys)
    out_path = _complete_output_setup_and_save(
        start=use_start,
        end=use_end,
        short_stem=stem,
        dest_root=dest,
        canonical_name=canonical,
        also_copy_as=also,
    )
    produced = Path(out_path)
    try:
        st = produced.stat()
        key = str(produced.resolve())
        prev = before.get(key)
        refreshed = prev is None or prev[0] + 0.05 < float(st.st_mtime) or prev[1] != int(st.st_size)
    except OSError as exc:
        raise RuntimeError(f"{report_id}: exported path unreadable: {exc}") from exc
    if not refreshed:
        # SoftDent sometimes rewrites an open/locked stem without bumping mtime.
        # Accept only when the Select File Name / Excel path completed (we have a path).
        logger.warning(
            "SoftDent export %s path=%s may be locked/stale mtime — keeping dialog result",
            report_id,
            produced,
        )
    return out_path


def navigate_softdent_print_preview_pages(
    *,
    max_next_pages: int = 40,
    pause_s: float = 0.45,
) -> dict[str, Any]:
    """Page through SoftDent Print Preview / MDI report for a complete visual read.

    SoftDent insurance/writeoff previews often hide detail on later pages — Page 1 is
    incomplete. Walk forward with PageDown (Next page), then Ctrl+End / End for the
    LAST page totals. Never invent dollars. Never Esc on SoftDent main.
    """
    out: dict[str, Any] = {
        "ok": False,
        "pagesAdvanced": 0,
        "maxNextPages": int(max_next_pages),
        "endedOnLastPage": False,
        "method": "PageDown then Ctrl+End/End",
        "honesty": "empty != $0; page 1 alone is incomplete — read next pages and last page",
    }
    try:
        hwnd = _main_softdent_hwnd()
        _force_foreground(hwnd)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"focus_failed:{type(exc).__name__}:{exc}"
        return out

    advanced = 0
    for _ in range(max(0, int(max_next_pages))):
        cancel_printer_dialogs(max_rounds=1)
        # Page Down = next preview page on SoftDent MDI / Print Preview
        _send_softdent_keys("{PGDN}")
        time.sleep(pause_s)
        advanced += 1
    out["pagesAdvanced"] = advanced

    # Final totals live on the last page
    try:
        _send_softdent_keys("^{END}")
        time.sleep(0.4)
        _send_softdent_keys("{END}")
        time.sleep(0.3)
        # Some SoftDent previews use Ctrl+PageDown to last page
        _send_softdent_keys("^{PGDN}")
        time.sleep(0.35)
        out["endedOnLastPage"] = True
    except Exception as exc:  # noqa: BLE001
        out["lastPageError"] = f"{type(exc).__name__}:{exc}"

    out["ok"] = True
    out["nextStep"] = (
        "Visually read SoftDent Print Preview: intermediate pages for line detail, "
        "LAST page for exact totals. Do not invent dollars from page 1 alone."
    )
    return out


def list_softdent_window_titles() -> list[str]:
    """SoftDent-owned window titles (for Print Preview / MDI report detection)."""
    import win32gui

    titles: list[str] = []
    pids = _softdent_pids()

    def _cb(hwnd: int, _: Any) -> bool:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if pids and _window_pid(int(hwnd)) not in pids:
                return True
            t = (win32gui.GetWindowText(hwnd) or "").strip()
            if t:
                titles.append(t)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass
    return titles


def softdent_report_preview_visible(titles: list[str] | None = None) -> bool:
    """True when Print Preview dialog or SoftDent MDI report window is showing."""
    titles = titles if titles is not None else list_softdent_window_titles()
    for t in titles:
        low = t.lower()
        if "sorting" in low:
            continue
        if "preview" in low:
            return True
        # MDI: "CS SoftDent Software v19.1.4 - [INSURANCE INCOME REPORT]"
        if "[" in t and "report" in low:
            return True
        if any(
            key in low
            for key in (
                "insurance income",
                "contractual plan",
                "payment allocation",
                "payment distribution",
                "writeoff",
                "write-off",
            )
        ):
            return True
    return False


def open_report_print_preview(
    report_id: str,
    *,
    start: date,
    end: date,
    menu_keys: str | None = None,
    page_through: bool = True,
    max_next_pages: int = 40,
) -> dict[str, Any]:
    """Open SoftDent report via Print Preview for visual read (no file ingest).

    Output Options: click **Print Preview** prompt, then Enter (same pattern as Excel).
    After SoftDent shows the preview, page through with Next/PageDown (detail often
    spans pages), then go to the **last page** for exact totals.
    Never invent dollars from page 1 alone. Never use Printer.
    Some reports (Insurance Income / writeoff) have Excel unavailable.
    """
    catalog = load_menu_map()
    report = (catalog.get("reports") or {}).get(report_id)
    if not isinstance(report, dict):
        raise KeyError(f"Unknown SoftDent GUI report id: {report_id}")
    keys = resolve_menu_keys(report, menu_keys)
    # Practice Management insurance reports: prefer win32 path (not Accounting F10 r a)
    opened = False
    win32_paths: dict[str, list[str]] = {
        "insurance_payment_analysis": [
            "Reports->Practice Management->Insurance Reports->Insurance Income",
            "Reports->Practice Management->Insurance Reports->Contractual Plan Analysis",
        ],
        "writeoff_totals": [
            "Reports->Practice Management->Insurance Reports->Writeoff Totals",
        ],
        "insurance_payment_distribution": [
            "Reports->Accounting->Insurance Payment Distribution",
        ],
    }
    for path in win32_paths.get(report_id) or []:
        if _open_report_via_win32_menu(path):
            opened = True
            break
    if not opened:
        _open_accounting_report(report_id, keys)
    _select_output_option_prompt("print_preview")
    # Setup if it appears — fill dates then OK into preview
    setup = None
    for _ in range(40):
        cancel_printer_dialogs(max_rounds=2)
        from pywinauto import Desktop

        pids = _softdent_pids()
        for w in Desktop(backend="win32").windows():
            try:
                t = (w.window_text() or "").strip()
                if pids and _window_pid(int(w.handle)) not in pids:
                    continue
                if "setup" in t.lower() and "softdent software" not in t.lower():
                    setup = w
                    break
            except Exception:
                continue
        if setup or find_dialog("Print Preview") or softdent_report_preview_visible():
            break
        time.sleep(0.25)
    if setup:
        _keyboard_activate_dialog(setup)
        h = int(setup.handle)
        start_txt = start.strftime("%m/%d/%y")
        end_txt = end.strftime("%m/%d/%y")
        _send_softdent_keys("{TAB}", hwnd=h)
        time.sleep(0.1)
        _type_keys_clear_and_text(start_txt, hwnd=h)
        _send_softdent_keys("{TAB}", hwnd=h)
        time.sleep(0.1)
        _type_keys_clear_and_text(end_txt, hwnd=h)
        _send_softdent_keys("{TAB}", hwnd=h)
        time.sleep(0.1)
        _type_keys_clear_and_text("999", hwnd=h)
        time.sleep(0.15)
        _keyboard_press_ok(hwnd=h)
        time.sleep(1.2)
        cancel_printer_dialogs()

    # Wait out SoftDent "Sorting Report" splash
    for _ in range(60):
        titles = list_softdent_window_titles()
        if any("sorting" in t.lower() for t in titles):
            time.sleep(0.5)
            continue
        break

    titles = list_softdent_window_titles()
    preview = softdent_report_preview_visible(titles)
    nav: dict[str, Any] | None = None
    if preview and page_through:
        nav = navigate_softdent_print_preview_pages(max_next_pages=max_next_pages)
        titles = list_softdent_window_titles()
        preview = softdent_report_preview_visible(titles) or preview

    return {
        "ok": True,
        "reportId": report_id,
        "outputMode": "print_preview",
        "printPreviewOpen": preview,
        "titles": titles[:12],
        "pageNavigation": nav,
        "nextStep": (
            "SoftDent Print Preview / MDI report is open (or pending). "
            "Page through with Next/PageDown for detail; LAST page for exact totals. "
            "Do not invent dollars from page 1 alone."
        ),
    }


def export_register_for_period(
    *,
    start: date,
    end: date,
    dest_root: Path | None = None,
) -> Path:
    """Reports → Accounting → Registers → Period → Excel."""
    return export_report_by_id("register", start=start, end=end, dest_root=dest_root)


def export_collections_for_period(
    *,
    start: date,
    end: date,
    dest_root: Path | None = None,
    menu_keys: str | None = None,
) -> Path:
    """Reports → Accounting → Collections (keys configurable)."""
    return export_report_by_id(
        "collections",
        start=start,
        end=end,
        dest_root=dest_root,
        menu_keys=menu_keys,
    )


def export_transactions_for_period(
    *,
    start: date,
    end: date,
    dest_root: Path | None = None,
    menu_keys: str | None = None,
) -> Path:
    return export_report_by_id(
        "transactions",
        start=start,
        end=end,
        dest_root=dest_root,
        menu_keys=menu_keys,
    )


def export_daysheet(
    *,
    start: date,
    end: date,
    dest_root: Path | None = None,
    menu_keys: str | None = None,
) -> Path:
    return export_report_by_id(
        "daysheet",
        start=start,
        end=end,
        dest_root=dest_root,
        menu_keys=menu_keys,
    )


def export_account_aging(
    *,
    as_of: date | None = None,
    dest_root: Path | None = None,
    menu_keys: str | None = None,
) -> Path:
    day = as_of or date.today()
    return export_report_by_id(
        "aging",
        start=day,
        end=day,
        dest_root=dest_root,
        menu_keys=menu_keys,
    )


def run_catalog_exports(
    *,
    start: date | None = None,
    end: date | None = None,
    report_ids: list[str] | None = None,
    ensure_signon: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run Phase-1 (or selected) SoftDent GUI exports. Never returns password."""
    today = date.today()
    start = start or date(today.year, today.month, 1)
    end = end or today
    catalog = load_menu_map()
    order = list(report_ids or catalog.get("phase1_order") or PHASE1_IDS)
    reports_meta = catalog.get("reports") or {}

    result: dict[str, Any] = {
        "ok": False,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "dryRun": bool(dry_run),
        "signOn": None,
        "reports": {},
        "errors": [],
        "requiredFailed": [],
    }

    if ensure_signon and not dry_run:
        try:
            from softdent_signon import ensure_softdent_signed_on, softdent_signon_status

            status = softdent_signon_status()
            assist = ensure_softdent_signed_on(timeout_s=60.0, force_change_login=False)
            result["signOn"] = {
                "user": status.get("user"),
                "passwordConfigured": bool(status.get("passwordConfigured")),
                "signedOn": bool(assist.get("signedOn")),
                "assistOk": bool(assist.get("ok")),
                "steps": assist.get("steps"),
                "error": assist.get("error"),
            }
            if not assist.get("ok") and not softdent_main_running():
                result["errors"].append("signon: SoftDent not signed on / not running")
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"signon:{type(exc).__name__}")
            result["signOn"] = {"ok": False, "error": type(exc).__name__}

    for rid in order:
        meta = reports_meta.get(rid) if isinstance(reports_meta.get(rid), dict) else {}
        required = bool(meta.get("required", rid in PHASE1_IDS))
        entry: dict[str, Any] = {
            "id": rid,
            "required": required,
            "ok": False,
            "path": None,
            "menuKeys": resolve_menu_keys(meta) if meta else None,
            "label": meta.get("label"),
        }
        if dry_run:
            entry["ok"] = True
            entry["dryRun"] = True
            result["reports"][rid] = entry
            continue
        # Print Preview–only (no Excel): skip Excel save automation
        if str(meta.get("outputMode") or "").strip().lower() == "print_preview_only" or (
            meta.get("excelExport") is False and meta.get("visualReadRequired")
        ):
            entry["ok"] = True
            entry["skipped"] = True
            entry["outputMode"] = "print_preview"
            entry["visualReadRequired"] = True
            entry["nextStep"] = (
                "Click Print Preview in Output Options, then Enter. "
                "Go to the LAST page and visually read totals; do not invent dollars. "
                "Prefer Excel when SoftDent offers it for file ingest."
            )
            result["reports"][rid] = entry
            continue
        # Multi-report: clear leftover setup dialogs before each pull.
        try:
            prep = prepare_softdent_for_next_report()
            entry["preflight"] = {
                "ok": bool(prep.get("ok")),
                "staleCancelled": prep.get("staleCancelled"),
                "printerCancelled": prep.get("printerCancelled"),
            }
        except Exception as exc:  # noqa: BLE001
            entry["preflight"] = {"ok": False, "error": type(exc).__name__}
        try:
            if not softdent_main_running():
                raise RuntimeError("SoftDent main window not available")
            path = export_report_by_id(rid, start=start, end=end, menu_map=catalog)
            entry["ok"] = True
            entry["path"] = str(path)
            cancel_printer_dialogs()
        except Exception as exc:  # noqa: BLE001
            msg = f"{rid}:{type(exc).__name__}:{exc}"
            entry["error"] = msg
            result["errors"].append(msg)
            if required:
                result["requiredFailed"].append(rid)
            logger.warning("SoftDent GUI export %s failed: %s", rid, type(exc).__name__)
            # Recover without Escape (Escape prompts SoftDent to close).
            try:
                cancel_printer_dialogs()
                dismiss_softdent_alerts()
            except Exception:
                pass
        finally:
            # Always leave SoftDent ready for the next report in the pack.
            try:
                entry["postflight"] = prepare_softdent_for_next_report()
            except Exception as exc:  # noqa: BLE001
                entry["postflight"] = {"ok": False, "error": type(exc).__name__}
        result["reports"][rid] = entry

    required_ok = all(
        (result["reports"].get(rid) or {}).get("ok")
        for rid in order
        if bool((reports_meta.get(rid) or {}).get("required", rid in PHASE1_IDS))
    )
    any_ok = any(bool(v.get("ok") and v.get("path")) for v in result["reports"].values())
    result["ok"] = bool(required_ok) if not dry_run else True
    if dry_run:
        result["ok"] = True
    elif not required_ok and any_ok:
        # Partial: register alone may still be useful; ok stays False when required failed
        result["partialOk"] = True
    return result


def run_safe_period_exports(
    *,
    start: date | None = None,
    end: date | None = None,
    do_register: bool = True,
    do_collections: bool = True,
    ensure_signon: bool = True,
) -> dict[str, Any]:
    """Backward-compatible Register/Collections-only wrapper."""
    ids: list[str] = []
    if do_register:
        ids.append("register")
    if do_collections:
        ids.append("collections")
    full = run_catalog_exports(
        start=start,
        end=end,
        report_ids=ids or ["register"],
        ensure_signon=ensure_signon,
    )
    return {
        "ok": bool(full.get("ok") or full.get("partialOk")),
        "start": full.get("start"),
        "end": full.get("end"),
        "signOn": full.get("signOn"),
        "registerPath": (full.get("reports") or {}).get("register", {}).get("path"),
        "collectionsPath": (full.get("reports") or {}).get("collections", {}).get("path"),
        "errors": full.get("errors") or [],
    }
