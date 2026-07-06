#!/usr/bin/env python3
"""CLI for NR2 workstation — read/send SideNotesIM messages (32-bit Python)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vdb_reader import SideNotesReader, DEFAULT_HISTORY, DEFAULT_SIM_DIR  # noqa: E402


def _norm_station(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _is_broadcast(recipient: str) -> bool:
    return _norm_station(recipient) in ("everyone", "all")


def _message_for_station(note, station: str) -> bool:
    station_key = _norm_station(station)
    if not station_key:
        return True
    sender = _norm_station(note.sender)
    recipient = _norm_station(note.recipient)
    if _is_broadcast(recipient):
        return True
    return station_key in (sender, recipient)


def _iso_at(date: str, time: str) -> str:
    date = str(date or "").strip()
    time = str(time or "").strip()
    if date and time:
        return f"{date}T{time}"
    return datetime.now(timezone.utc).isoformat()


def cmd_read(args: argparse.Namespace) -> int:
    reader = SideNotesReader(history_path=args.history or DEFAULT_HISTORY, sim_dir=args.sim_dir or DEFAULT_SIM_DIR)
    try:
        notes = reader.read_recent(limit=args.limit, include_body=bool(args.include_body))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "messages": []}))
        return 1
    station = str(args.station or "").strip()
    out = []
    for note in notes:
        if station and not _message_for_station(note, station):
            continue
        out.append(
            {
                "id": note.messageId or f"sn-row-{note.rowId}",
                "source": "sidenotes",
                "from": note.sender,
                "target": note.recipient,
                "targets": ["all"] if _is_broadcast(note.recipient) else [note.recipient],
                "text": note.messageBody if args.include_body else "",
                "at": _iso_at(note.date, note.time),
                "unread": note.unread,
                "speak": False,
                "role": "staff",
            }
        )
    print(json.dumps({"ok": True, "messages": out[-args.limit :], "historyPath": reader.history_path}))
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    text = str(args.text or "").strip()
    if not text:
        print(json.dumps({"ok": False, "error": "empty text"}))
        return 1
    from_station = str(args.from_station or args.station or "").strip()
    to_raw = str(args.to or "Everyone").strip()
    if not from_station:
        print(json.dumps({"ok": False, "error": "from station required"}))
        return 1
    try:
        from vdb_writer import SideNotesWriter

        writer = SideNotesWriter(history_path=args.history or DEFAULT_HISTORY, sim_dir=args.sim_dir or DEFAULT_SIM_DIR)
        result = writer.send_message(from_station=from_station, to_station=to_raw, text=text)
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "method": "vdb_writer"}))
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    history = args.history or DEFAULT_HISTORY
    ok = os.path.isfile(history)
    sim_ok = os.path.isdir(args.sim_dir or DEFAULT_SIM_DIR)
    print(
        json.dumps(
            {
                "ok": ok,
                "historyPath": history,
                "historyExists": ok,
                "simDir": args.sim_dir or DEFAULT_SIM_DIR,
                "simDirExists": sim_ok,
            }
        )
    )
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="SideNotesIM bridge CLI")
    parser.add_argument("--history", default="")
    parser.add_argument("--sim-dir", default="")
    sub = parser.add_subparsers(dest="cmd", required=True)

    read_p = sub.add_parser("read")
    read_p.add_argument("--station", default="")
    read_p.add_argument("--limit", type=int, default=48)
    read_p.add_argument("--include-body", action="store_true")
    read_p.set_defaults(func=cmd_read)

    send_p = sub.add_parser("send")
    send_p.add_argument("--from-station", dest="from_station", default="")
    send_p.add_argument("--station", default="")
    send_p.add_argument("--to", default="Everyone")
    send_p.add_argument("--text", required=True)
    send_p.set_defaults(func=cmd_send)

    status_p = sub.add_parser("status")
    status_p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
