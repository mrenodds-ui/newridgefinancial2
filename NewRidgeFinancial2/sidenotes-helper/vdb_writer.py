"""
Attempt to append a SideNotesIM message via VistaDB COM (local history.vdb).

SideNotesIM must be installed. Delivery to other stations still depends on
SideNotesIM's own network sync when the app is running.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime

from vdb_reader import SideNotesReader, DEFAULT_HISTORY, DEFAULT_SIM_DIR, _ensure_engine, _split_station


def _station_field(name: str, hardware_id: str = "") -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    if hardware_id:
        return f"{text}:{hardware_id}"
    return text


class SideNotesWriter(SideNotesReader):
    def _open_db_rw(self, vdb_path: str):
        import comtypes.client as cc

        _ensure_engine(self.sim_dir)
        directory = os.path.dirname(vdb_path)
        filename = os.path.basename(vdb_path)
        db = cc.CreateObject("VistaDBCOM20.Database")
        db.AccessMode = 0
        try:
            db.HideErrors = False
        except Exception:
            pass
        db.SetDataPath(directory + os.sep)
        db.DatabaseName = filename
        db.ReadOnly = False
        db.Open()
        return db, cc

    def send_message(self, from_station: str, to_station: str, text: str) -> dict:
        if not os.path.isfile(self.history_path):
            return {"ok": False, "error": "history.vdb not found", "method": "vdb_writer"}
        to_clean = str(to_station or "Everyone").strip()
        if to_clean.lower() in ("all", "everyone"):
            to_field = "Everyone"
        else:
            to_field = to_clean
        now = datetime.now()
        msg_id = uuid.uuid4().hex[:12].upper()
        date_str = now.strftime("%m/%d/%Y")
        time_str = now.strftime("%I:%M:%S %p")
        try:
            db, cc = self._open_db_rw(self.history_path)
            tbl = cc.CreateObject("VistaDBCOM20.Table")
            tbl.Database = db
            tbl.TableName = self.table
            try:
                tbl.ReadOnly = False
            except Exception:
                pass
            tbl.Open()
            try:
                tbl.AddNew()
                tbl.SetString("dFrom", _station_field(from_station))
                tbl.SetString("dTo", _station_field(to_field))
                tbl.SetMemo("dMessage", str(text))
                tbl.SetString("dID", msg_id)
                tbl.SetString("dDate", date_str)
                tbl.SetString("dTime", time_str)
                tbl.SetString("dNew", "1")
                tbl.SetString("dStatus", "")
                tbl.Post()
            finally:
                tbl.Close()
                db.Close()
            return {
                "ok": True,
                "method": "vdb_writer",
                "message": {
                    "id": f"sn-{msg_id}",
                    "source": "sidenotes",
                    "from": from_station,
                    "target": to_field,
                    "text": text,
                    "at": now.isoformat(),
                },
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "method": "vdb_writer"}
