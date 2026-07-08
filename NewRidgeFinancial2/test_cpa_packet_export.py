"""Tests for cpa_packet_export (hal-10074)."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO

from cpa_packet_export import WIDGET_KEYS, build_cpa_packet, collect_cpa_payloads


def test_collect_cpa_payloads_has_all_widgets():
    payloads = collect_cpa_payloads()
    widgets = payloads.get("widgets") or {}
    for key in WIDGET_KEYS:
        assert key in widgets, f"missing widget payload {key}"
        assert widgets[key].get("widgetKey") == key


def test_build_cpa_packet_zip_structure(tmp_path, monkeypatch):
    monkeypatch.setattr("cpa_packet_export.OUTPUT_DIR", tmp_path)
    result = build_cpa_packet(write_disk=True)
    assert result.get("ok") is True
    path = result.get("path")
    assert path and __import__("pathlib").Path(path).is_file()
    with zipfile.ZipFile(path, "r") as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        for key in WIDGET_KEYS:
            assert f"{key}.json" in names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest.get("widgetKeys") == list(WIDGET_KEYS)


def test_zip_bytes_roundtrip():
    result = build_cpa_packet(write_disk=False)
    raw = bytes(result["zipBytes"])
    assert len(raw) > 0
    with zipfile.ZipFile(BytesIO(raw), "r") as archive:
        assert len(archive.namelist()) >= len(WIDGET_KEYS) + 1
