"""Tests for page_storyboard_export (hal-10084)."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO

from page_storyboard_export import (
    STAFF_PAGES,
    build_page_storyboard,
    build_storyboard_html,
    collect_page_storyboard,
)


def test_collect_page_storyboard_financial():
    payload = collect_page_storyboard("financial")
    assert payload["pageId"] == "financial"
    assert payload["title"]
    assert "data" in payload


def test_build_storyboard_html_contains_title():
    payload = collect_page_storyboard("taxes")
    html_doc = build_storyboard_html(payload)
    assert "S Corp Tax Planning" in html_doc
    assert "<table>" in html_doc


def test_build_page_storyboard_zip_structure(tmp_path, monkeypatch):
    monkeypatch.setattr("page_storyboard_export.OUTPUT_DIR", tmp_path)
    result = build_page_storyboard(page_id="financial", write_disk=True)
    assert result["ok"] is True
    assert result["filename"].endswith(".zip")
    names = set()
    with zipfile.ZipFile(BytesIO(result["zipBytes"])) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["pageId"] == "financial"
        assert "storyboard.html" in names
        assert archive.read("storyboard.html").decode("utf-8").startswith("<!DOCTYPE html>")
    assert "manifest.json" in names
    assert "data.json" in names


def test_staff_pages_include_core_pages():
    assert "financial" in STAFF_PAGES
    assert "taxes" in STAFF_PAGES
    assert "quickbooks" in STAFF_PAGES
