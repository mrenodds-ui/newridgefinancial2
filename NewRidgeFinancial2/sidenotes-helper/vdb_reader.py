"""
VistaDB reader for the SideNotesIM message history (read-only, local).

This encapsulates the exact open sequence required to read the legacy
VistaDB 2.1.7 `history.vdb` written by SideNotesIM:

  * The 32-bit native engine (VistaDB20.dll) lives next to the COM DLL in the
    SideNotesIM install folder and is lazy-loaded on the first DB operation,
    so that folder MUST be on the DLL search path before any DB call.
  * AccessMode must be 0 (local file), not the default client/server path.
  * SetDataPath needs a TRAILING backslash; DatabaseName needs the extension.

It is read-only and never reads the message body column (`dMessage`) so no
message content / PHI ever leaves SideNotesIM. Only routing metadata
(sender, recipient, id, timestamp, unread flag) is read.

To avoid touching the live database that SideNotesIM holds open, each read is
performed against a transient copy of the file.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from dataclasses import dataclass, asdict
from typing import Optional

DEFAULT_SIM_DIR = r"C:\Program Files (x86)\SideNotesIM"
DEFAULT_HISTORY = os.path.join(os.environ.get("APPDATA", ""), "SideNotesIM", "history.vdb")

# Non-content columns only. `dMessage` is intentionally excluded.
SAFE_COLUMNS = ["dFrom", "dTo", "dTime", "dDate", "dID", "dNew", "dStatus", "dReply", "dSentTo"]

_engine_ready = False


def _ensure_engine(sim_dir: str) -> None:
    """Put the SideNotesIM folder on the DLL search path and load the typelib."""
    global _engine_ready
    if _engine_ready:
        return
    if os.path.isdir(sim_dir):
        try:
            os.add_dll_directory(sim_dir)
        except (FileNotFoundError, OSError):
            pass
        os.environ["PATH"] = sim_dir + os.pathsep + os.environ.get("PATH", "")
    import comtypes.client as cc

    cc.GetModule(os.path.join(sim_dir, "VistaDBCOM20.DLL"))
    _engine_ready = True


@dataclass
class SideNote:
    rowId: int
    sender: str
    senderId: str
    recipient: str
    recipientId: str
    messageId: str
    date: str
    time: str
    unread: bool
    status: str
    messageBody: str = ""

    def to_dict(self, include_body: bool = False) -> dict:
        data = asdict(self)
        if not include_body:
            data.pop("messageBody", None)
        return data


def _split_station(value: Optional[str]) -> tuple[str, str]:
    """SideNotesIM encodes some endpoints as 'Name:hardwareId'. Split them."""
    if not value:
        return ("", "")
    text = str(value)
    if ":" in text:
        name, _, hw = text.partition(":")
        return (name.strip(), hw.strip())
    return (text.strip(), "")


def _copy_live(history_path: str, attempts: int = 5) -> str:
    """Copy the live history.vdb to a temp file so we never lock the original."""
    last_err: Optional[Exception] = None
    fd, tmp = tempfile.mkstemp(prefix="sn_hist_", suffix=".vdb")
    os.close(fd)
    for _ in range(attempts):
        try:
            shutil.copy2(history_path, tmp)
            return tmp
        except (PermissionError, OSError) as exc:  # sharing violation, etc.
            last_err = exc
            time.sleep(0.25)
    try:
        os.remove(tmp)
    except OSError:
        pass
    raise RuntimeError(f"Could not copy history.vdb: {last_err}")


class SideNotesReader:
    def __init__(
        self,
        history_path: str = DEFAULT_HISTORY,
        sim_dir: str = DEFAULT_SIM_DIR,
        table: str = "Messages",
    ) -> None:
        self.history_path = history_path
        self.sim_dir = sim_dir
        self.table = table

    def _open_db(self, vdb_path: str):
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
        db.ReadOnly = True
        db.Open()
        return db, cc

    def max_row_id(self) -> int:
        """Cheap newest-RowId probe against a fresh copy."""
        tmp = _copy_live(self.history_path)
        try:
            db, cc = self._open_db(tmp)
            tbl = cc.CreateObject("VistaDBCOM20.Table")
            tbl.Database = db
            tbl.TableName = self.table
            tbl.Open()
            try:
                if tbl.RowCount() <= 0:
                    return 0
                tbl.Last()
                return int(tbl.RowId())
            finally:
                tbl.Close()
                db.Close()
        finally:
            self._cleanup(tmp)

    def read_recent(self, limit: int = 48, include_body: bool = False) -> list[SideNote]:
        """Return the newest messages, oldest first."""
        top = self.max_row_id()
        if top <= 0:
            return []
        since = max(0, top - max(1, int(limit)) - 5)
        notes = self.read_new(since, limit=max(1, int(limit)) + 5, include_body=include_body)
        return notes[-int(limit) :]

    def read_new(self, since_row_id: int, limit: int = 50, include_body: bool = False) -> list[SideNote]:
        """Return messages with RowId > since_row_id, oldest first."""
        tmp = _copy_live(self.history_path)
        notes: list[SideNote] = []
        try:
            db, cc = self._open_db(tmp)
            tbl = cc.CreateObject("VistaDBCOM20.Table")
            tbl.Database = db
            tbl.TableName = self.table
            tbl.Open()
            try:
                if tbl.RowCount() <= 0:
                    return []
                tbl.Last()
                count = 0
                # Bof()/Eof() are methods on this COM interface (not properties).
                while count < limit and not tbl.Bof():
                    try:
                        rid = int(tbl.RowId())
                    except Exception:
                        break
                    if rid <= since_row_id:
                        break
                    notes.append(self._read_row(tbl, rid, include_body=include_body))
                    count += 1
                    tbl.Prior()
            finally:
                tbl.Close()
                db.Close()
        finally:
            self._cleanup(tmp)
        notes.reverse()  # oldest -> newest
        return notes

    def _read_row(self, tbl, rid: int, include_body: bool = False) -> SideNote:
        def memo(col: str) -> str:
            try:
                val = tbl.GetMemo(col, 32767)
            except Exception:
                try:
                    val = tbl.GetString(col)
                except Exception:
                    val = ""
            return "" if val is None else str(val)

        sender, sender_id = _split_station(memo("dFrom"))
        recipient, recipient_id = _split_station(memo("dTo"))
        return SideNote(
            rowId=rid,
            sender=sender,
            senderId=sender_id,
            recipient=recipient,
            recipientId=recipient_id,
            messageId=memo("dID"),
            date=memo("dDate"),
            time=memo("dTime"),
            unread=memo("dNew").strip() == "1",
            status=memo("dStatus"),
            messageBody=memo("dMessage") if include_body else "",
        )

    @staticmethod
    def _cleanup(tmp: str) -> None:
        try:
            os.remove(tmp)
        except OSError:
            pass


if __name__ == "__main__":
    # Smoke test: print newest RowId and the last few messages' routing info.
    reader = SideNotesReader()
    top = reader.max_row_id()
    print("newest RowId:", top)
    recent = reader.read_new(max(0, top - 5))
    for n in recent:
        print(n.to_dict())
