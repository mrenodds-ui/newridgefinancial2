from __future__ import annotations

import subprocess

from scripts import frontend_toolchain_check


def test_check_frontend_toolchain_reports_missing_npm(monkeypatch):
    monkeypatch.setattr(frontend_toolchain_check.shutil, "which", lambda _: None)

    result = frontend_toolchain_check.check_frontend_toolchain()

    assert result.available is False
    assert result.npm_path is None
    assert result.npm_version is None
    assert result.message == "npm is not available on PATH."


def test_check_frontend_toolchain_reports_version(monkeypatch):
    monkeypatch.setattr(frontend_toolchain_check.shutil, "which", lambda _: "C:/Program Files/nodejs/npm.CMD")

    def fake_run(command, capture_output, text, check, timeout):
        assert command == ["C:/Program Files/nodejs/npm.CMD", "--version"]
        assert capture_output is True
        assert text is True
        assert check is False
        assert timeout == 15
        return subprocess.CompletedProcess(command, 0, stdout="11.13.0\n", stderr="")

    monkeypatch.setattr(frontend_toolchain_check.subprocess, "run", fake_run)

    result = frontend_toolchain_check.check_frontend_toolchain()

    assert result.available is True
    assert result.npm_path == "C:/Program Files/nodejs/npm.CMD"
    assert result.npm_version == "11.13.0"
    assert result.message == "npm is available at C:/Program Files/nodejs/npm.CMD."


def test_check_frontend_toolchain_reports_probe_failure(monkeypatch):
    monkeypatch.setattr(frontend_toolchain_check.shutil, "which", lambda _: "C:/Program Files/nodejs/npm.CMD")

    def fake_run(command, capture_output, text, check, timeout):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="permission denied")

    monkeypatch.setattr(frontend_toolchain_check.subprocess, "run", fake_run)

    result = frontend_toolchain_check.check_frontend_toolchain()

    assert result.available is False
    assert result.npm_path == "C:/Program Files/nodejs/npm.CMD"
    assert result.npm_version is None
    assert "permission denied" in result.message