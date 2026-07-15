"""Read BlueNote Communicator Lights routing metadata from the live UI.

Privacy: never read conversation message bodies. Encrypted .dat stores are not
parsed. We only take light/conversation *routing* hints exposed in UI chrome
(XAML TextBlocks, inbox button counts, popup alert titles).
"""

from __future__ import annotations

import ctypes
import re
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

EnumWindows = user32.EnumWindows
EnumChildWindows = user32.EnumChildWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
GetClassNameW = user32.GetClassNameW
IsWindowVisible = user32.IsWindowVisible
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
SendMessageW = user32.SendMessageW
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

DEFAULT_ROAMING = Path.home() / "AppData" / "Roaming" / "BlueNote Communicator Lights"
ECONVERSATIONS = DEFAULT_ROAMING / "econversations.dat"
CLIENT_CFG = DEFAULT_ROAMING / "client.cfg"

_XAML_TEXT_RE = re.compile(r">([^<>]{1,160})<")
_INBOX_RE = re.compile(r"^Inbox\s*\((\d+)\)\s*$", re.I)
_CONV_TO_RE = re.compile(
    r"New Conversation to\s*[| ]+\s*(.+)$|"
    r"New Conversation to(.+)$|"
    r"Conversation to\s*[| ]+\s*(.+)$",
    re.I,
)
_CONV_FROM_RE = re.compile(
    r"New Conversation from\s*[| ]+\s*(.+)$|"
    r"Message from\s*[| ]+\s*(.+)$|"
    r"Conversation from\s*[| ]+\s*(.+)$",
    re.I,
)


@dataclass(frozen=True)
class BlueNoteEvent:
    id: str
    kind: str  # conversation | light | inbox
    sender: str
    recipient: str
    broadcast: bool
    label: str
    captured_at: str


def _window_text(hwnd: int) -> str:
    n = int(SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0) or 0)
    if n > 0:
        buf = ctypes.create_unicode_buffer(n + 1)
        SendMessageW(hwnd, WM_GETTEXT, n + 1, buf)
        if buf.value:
            return buf.value
    n = int(GetWindowTextLengthW(hwnd) or 0)
    buf = ctypes.create_unicode_buffer(max(n, 1) + 1)
    GetWindowTextW(hwnd, buf, max(n, 1) + 1)
    return buf.value or ""


def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value or ""


def find_bluenote_pids() -> list[int]:
    """PIDs for BlueNoteCL.exe (Toolhelp)."""
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
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap in (0, -1, ctypes.c_void_p(-1).value):
        return []
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    out: list[int] = []
    try:
        if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                name = (pe.szExeFile or "").upper()
                if name.startswith("BLUENOTECL"):
                    out.append(int(pe.th32ProcessID))
                if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return out


def bluenote_running() -> bool:
    return bool(find_bluenote_pids())


def read_panel_name(cfg_path: Path | None = None) -> str:
    path = cfg_path or CLIENT_CFG
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for line in text.splitlines():
        if line.strip().lower().startswith("panelname=") and "location" not in line.lower():
            return line.split("=", 1)[-1].strip()
    return ""


def _xaml_plain(raw: str) -> list[str]:
    parts: list[str] = []
    for m in _XAML_TEXT_RE.finditer(raw or ""):
        s = (m.group(1) or "").strip()
        if not s:
            continue
        if any(
            bad in s
            for bad in (
                "xmlns",
                "StackPanel",
                "WrapPanel",
                "Page ",
                "Padding",
                "Foreground",
                "Background",
                "Copyright",
            )
        ):
            continue
        # Drop pure punctuation / color leftovers
        if len(s) < 2:
            continue
        parts.append(s)
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _iter_bluenote_control_texts(pids: Iterable[int]) -> list[tuple[str, str, bool]]:
    """Return (class, text, visible) for BlueNote windows/controls."""
    wanted = set(int(p) for p in pids)
    rows: list[tuple[str, str, bool]] = []

    def consider(hwnd: int) -> None:
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) not in wanted:
            return
        cls = _class_name(hwnd)
        text = _window_text(hwnd)
        if not text.strip():
            return
        rows.append((cls, text, bool(IsWindowVisible(hwnd))))

    def top(hwnd, _lp):
        consider(hwnd)

        def child(ch, __):
            consider(ch)
            return True

        EnumChildWindows(hwnd, EnumWindowsProc(child), 0)
        return True

    EnumWindows(EnumWindowsProc(top), 0)
    return rows


def _fingerprint(kind: str, sender: str, recipient: str, label: str) -> str:
    base = f"{kind}|{sender}|{recipient}|{label}".strip().lower()
    return re.sub(r"\s+", " ", base)[:180]


def scan_events(*, my_panel: str = "") -> dict:
    """Snapshot current BlueNote routing cues (no message bodies)."""
    now = datetime.now(timezone.utc).isoformat()
    pids = find_bluenote_pids()
    events: list[BlueNoteEvent] = []
    inbox_count: int | None = None
    convo_title = ""
    panel = my_panel or read_panel_name() or "This station"

    if not pids:
        return {
            "ok": False,
            "running": False,
            "panelName": panel,
            "inboxCount": None,
            "events": [],
            "error": "BlueNoteCL.exe not running",
            "econversationsMtime": _mtime(ECONVERSATIONS),
        }

    for cls, text, visible in _iter_bluenote_control_texts(pids):
        if text.startswith("Conversations for "):
            convo_title = text
        m_inbox = _INBOX_RE.match(text.strip())
        if m_inbox:
            try:
                inbox_count = int(m_inbox.group(1))
            except ValueError:
                pass

        plains = _xaml_plain(text) if "AfxOle" in cls or "<Page" in text or "<TextBlock" in text else []
        joined = " | ".join(plains) if plains else text.strip()

        # Conversation routing chrome
        for plain in plains or [joined]:
            to_m = _CONV_TO_RE.search(plain.replace("\n", " "))
            from_m = _CONV_FROM_RE.search(plain.replace("\n", " "))
            if to_m:
                recipient = next((g.strip() for g in to_m.groups() if g and g.strip()), "")
                if recipient:
                    label = f"New Conversation to {recipient}"
                    events.append(
                        BlueNoteEvent(
                            id=_fingerprint("conversation", panel, recipient, label),
                            kind="conversation",
                            sender=panel,
                            recipient=recipient,
                            broadcast=recipient.lower() in ("everyone", "all", "all active users"),
                            label=label,
                            captured_at=now,
                        )
                    )
            if from_m:
                sender = next((g.strip() for g in from_m.groups() if g and g.strip()), "")
                if sender:
                    label = f"New Conversation from {sender}"
                    events.append(
                        BlueNoteEvent(
                            id=_fingerprint("conversation", sender, panel, label),
                            kind="conversation",
                            sender=sender,
                            recipient=panel,
                            broadcast=False,
                            label=label,
                            captured_at=now,
                        )
                    )

        # Visible Innovasys popup alerts — extract short light text if present
        if visible and ("InnovasysPopup" in text or cls == "ThunderRT6FormDC" and text == "##InnovasysPopupAlert##"):
            # Popup shell itself has no useful title; children may via XAML in other pass
            pass

        # Direct button titles that look like light/alert labels when newly shown
        if visible and cls == "Button":
            t = text.strip()
            if t and _looks_like_light_label(t):
                events.append(
                    BlueNoteEvent(
                        id=_fingerprint("light", panel, "", t),
                        kind="light",
                        sender=panel,
                        recipient="",
                        broadcast=True,
                        label=t,
                        captured_at=now,
                    )
                )

    # De-dupe by id preserving order
    seen: set[str] = set()
    unique: list[dict] = []
    for ev in events:
        if ev.id in seen:
            continue
        seen.add(ev.id)
        unique.append(
            {
                "id": ev.id,
                "kind": ev.kind,
                "sender": ev.sender,
                "recipient": ev.recipient,
                "broadcast": ev.broadcast,
                "label": ev.label,
                "capturedAt": ev.captured_at,
                "unread": True,
            }
        )

    return {
        "ok": True,
        "running": True,
        "panelName": panel,
        "conversationsTitle": convo_title,
        "inboxCount": inbox_count,
        "pids": pids,
        "events": unique,
        "econversationsMtime": _mtime(ECONVERSATIONS),
        "scannedAt": now,
    }


def _looks_like_light_label(text: str) -> bool:
    t = text.strip()
    if len(t) < 4 or len(t) > 40:
        return False
    if "<" in t or "xmlns" in t.lower() or "TextBlock" in t:
        return False
    deny = (
        "test popup",
        "reset",
        "options",
        "settings",
        "mark all",
        "save message",
        "delete",
        "cancel",
        "create group",
        "search",
        "newest",
        "users",
        "groups",
        "messages",
        "conversations",
        "do not disturb",
        "on top",
        "elapsed",
        "lights activity",
        "clear popups",
        "how to use",
        "support",
        "updated version",
        "popup size",
        "popups clear",
        "show the",
        "show popup",
        "disable popup",
        "disable",
        "open the",
        "alert manager",
        "aging color",
        "light color",
        "light tags",
        "activating a light",
        "clicking on",
        "maximized",
        "reappear",
        "trial",
        "remaining",
    )
    low = t.lower()
    if any(d in low for d in deny):
        return False
    if low.isdigit():
        return False
    # Prefer human office phrases / room labels — short only
    needles = (
        "room",
        "patient",
        "ready",
        "help",
        "phone",
        "emergency",
        "behind",
        "lab",
        "front",
        "clinician",
        "waiting",
        "assist",
        "check in",
        "check-out",
    )
    return any(n in low for n in needles) and len(t.split()) <= 6


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime if path.is_file() else None
    except OSError:
        return None


def sleep_poll(seconds: float) -> None:
    time.sleep(max(0.2, float(seconds)))
