"""Read-only grep across NR2 program source (site bundle + core Python)."""

from __future__ import annotations

import re
from pathlib import Path

ALLOWED_EXT = {".js", ".py", ".json", ".html", ".css", ".mjs", ".md"}
SKIP_PARTS = {
    ".venv",
    ".venv-py313",
    "node_modules",
    "app_data",
    "__pycache__",
    "miranda_reference",
    ".git",
}


def _allowed_path(path: Path, roots: list[Path]) -> bool:
    if path.suffix.lower() not in ALLOWED_EXT:
        return False
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    try:
        path.relative_to(roots[0])
        return True
    except ValueError:
        pass
    if len(roots) > 1:
        try:
            path.relative_to(roots[1])
            return True
        except ValueError:
            return False
    return False


def grep_program_source(repo_root: Path, site_dir: Path, query: str, limit: int = 24) -> dict:
    term = " ".join(str(query or "").split()).strip()
    if len(term) < 2:
        return {"hits": [], "count": 0, "text": "Search term must be at least 2 characters."}

    repo_root = repo_root.resolve()
    site_dir = site_dir.resolve()
    nr2_dir = repo_root / "NewRidgeFinancial2"
    roots = [p for p in (site_dir, nr2_dir) if p.is_dir()]
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    hits: list[dict] = []

    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or not _allowed_path(path, roots):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, 1):
                if not pattern.search(line):
                    continue
                try:
                    rel = path.relative_to(repo_root).as_posix()
                except ValueError:
                    rel = path.name
                hits.append({"file": rel, "line": line_no, "text": line.strip()[:220]})
                if len(hits) >= max(1, min(int(limit or 24), 40)):
                    break
            if len(hits) >= max(1, min(int(limit or 24), 40)):
                break
        if len(hits) >= max(1, min(int(limit or 24), 40)):
            break

    if not hits:
        return {
            "hits": [],
            "count": 0,
            "text": f'No program source matches for "{term}". Try widget names, route intents, or file stems like hal-agent.',
        }

    text = "\n".join(f"{h['file']}:{h['line']}: {h['text']}" for h in hits)
    return {"hits": hits, "count": len(hits), "text": text, "query": term}


def _resolve_roots(repo_root: Path, site_dir: Path) -> tuple[Path, Path, list[Path]]:
    repo_root = repo_root.resolve()
    site_dir = site_dir.resolve()
    nr2_dir = repo_root / "NewRidgeFinancial2"
    roots = [p for p in (site_dir, nr2_dir) if p.is_dir()]
    return repo_root, site_dir, roots


def _resolve_allowed_file(repo_root: Path, roots: list[Path], rel_path: str) -> Path | None:
    rel = str(rel_path or "").replace("\\", "/").strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    candidates = [
        repo_root / rel,
        repo_root / "NewRidgeFinancial2" / rel,
        repo_root / "NewRidgeFinancial2" / "site" / rel,
    ]
    for path in candidates:
        if not path.is_file():
            continue
        if not _allowed_path(path, roots):
            continue
        return path
    return None


def read_program_file(repo_root: Path, site_dir: Path, rel_path: str, max_chars: int = 12000) -> dict:
    repo_root, _, roots = _resolve_roots(repo_root, site_dir)
    path = _resolve_allowed_file(repo_root, roots, rel_path)
    if not path:
        return {"ok": False, "text": f"File not found or not allowed: {rel_path}"}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return {"ok": False, "text": str(exc)}
    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        rel = path.name
    cap = max(500, min(int(max_chars or 12000), 20000))
    clipped = text[:cap]
    suffix = "\n… (truncated)" if len(text) > cap else ""
    return {"ok": True, "file": rel, "chars": len(text), "text": clipped + suffix}


def list_program_files(repo_root: Path, site_dir: Path, subdir: str = "site", limit: int = 80) -> dict:
    repo_root, site_dir, roots = _resolve_roots(repo_root, site_dir)
    sub = str(subdir or "site").replace("\\", "/").strip().lstrip("/")
    if ".." in sub.split("/"):
        return {"ok": False, "files": [], "text": "Invalid subdirectory."}
    base = site_dir if sub in ("site", ".", "") else repo_root / "NewRidgeFinancial2" / sub
    if not base.is_dir():
        return {"ok": False, "files": [], "text": f"Directory not found: {sub}"}
    files: list[str] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or not _allowed_path(path, roots):
            continue
        try:
            files.append(path.relative_to(repo_root).as_posix())
        except ValueError:
            files.append(path.name)
        if len(files) >= max(10, min(int(limit or 80), 120)):
            break
    text = "\n".join(files) if files else "No listable program files."
    return {"ok": True, "files": files, "count": len(files), "text": text}


def apply_program_patch(
    repo_root: Path,
    site_dir: Path,
    rel_path: str,
    old_string: str,
    new_string: str,
    *,
    dry_run: bool = False,
) -> dict:
    repo_root, _, roots = _resolve_roots(repo_root, site_dir)
    path = _resolve_allowed_file(repo_root, roots, rel_path)
    if not path:
        return {"ok": False, "text": f"File not found or not allowed: {rel_path}"}
    old = str(old_string if old_string is not None else "")
    new = str(new_string if new_string is not None else "")
    if not old:
        return {"ok": False, "text": "old_string is required."}
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return {"ok": False, "text": str(exc)}
    count = content.count(old)
    if count == 0:
        return {"ok": False, "text": "old_string not found in file."}
    if count > 1:
        return {"ok": False, "text": f"old_string must be unique (found {count} times)."}
    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        rel = path.name
    if dry_run:
        return {
            "ok": True,
            "dryRun": True,
            "file": rel,
            "text": f"Dry run: would patch {rel} ({len(old)} -> {len(new)} chars).",
        }
    backup_root = repo_root / ".local_logs" / "patch_backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_root / f"{path.name}.{stamp}.bak"
    try:
        backup_path.write_text(content, encoding="utf-8")
        path.write_text(content.replace(old, new, 1), encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "text": str(exc)}
    return {
        "ok": True,
        "file": rel,
        "backup": backup_path.relative_to(repo_root).as_posix(),
        "text": f"Patched {rel}. Backup: {backup_path.name}.",
    }


def run_hal_validation(repo_root: Path, timeout_sec: int = 120) -> dict:
    import os
    import subprocess

    nr2 = repo_root / "NewRidgeFinancial2"
    script = nr2 / "validate-hal.mjs"
    if not script.is_file():
        return {"ok": False, "text": "validate-hal.mjs not found.", "exitCode": -1}
    env = {**os.environ, "NR2_LOAD_IMPORTS": "1"}
    try:
        proc = subprocess.run(
            ["node", str(script)],
            cwd=str(nr2),
            capture_output=True,
            text=True,
            timeout=max(30, min(int(timeout_sec or 120), 180)),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "text": "HAL validation timed out.", "exitCode": -2}
    except OSError as exc:
        return {"ok": False, "text": str(exc), "exitCode": -3}
    combined = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
    tail = combined[-6000:] if len(combined) > 6000 else combined
    ok = proc.returncode == 0
    summary = "HAL validation passed." if ok else "HAL validation failed."
    if tail:
        summary += "\n" + tail
    return {"ok": ok, "exitCode": proc.returncode, "text": summary}


def run_node_syntax_check(repo_root: Path, site_dir: Path, rel_paths: list[str]) -> dict:
    import subprocess

    repo_root, _, roots = _resolve_roots(repo_root, site_dir)
    paths: list[Path] = []
    for rel in rel_paths[:10]:
        p = _resolve_allowed_file(repo_root, roots, str(rel or ""))
        if p and p.suffix.lower() in {".js", ".mjs"}:
            paths.append(p)
    if not paths:
        return {"ok": False, "results": [], "text": "No checkable JS files."}
    results: list[dict] = []
    for path in paths:
        try:
            rel = path.relative_to(repo_root).as_posix()
        except ValueError:
            rel = path.name
        try:
            proc = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True,
                text=True,
                timeout=20,
            )
            ok = proc.returncode == 0
            err = (proc.stderr or proc.stdout or "").strip()
            results.append({"file": rel, "ok": ok, "error": err[:400] if not ok else ""})
        except subprocess.TimeoutExpired:
            results.append({"file": rel, "ok": False, "error": "timeout"})
        except OSError as exc:
            results.append({"file": rel, "ok": False, "error": str(exc)})
    all_ok = all(r["ok"] for r in results)
    lines = [f"{'PASS' if r['ok'] else 'FAIL'} {r['file']}" + (f": {r['error']}" if r.get("error") else "") for r in results]
    return {"ok": all_ok, "results": results, "text": "\n".join(lines)}


def semantic_search_program(repo_root: Path, site_dir: Path, query: str, limit: int = 15) -> dict:
    """Lightweight token-overlap search (no embeddings) across program source."""
    repo_root, site_dir, roots = _resolve_roots(repo_root, site_dir)
    terms = [t for t in re.findall(r"[a-z0-9_]{3,}", str(query or "").lower()) if t not in {"the", "and", "for", "how", "what", "does", "with"}]
    if not terms:
        return {"hits": [], "count": 0, "text": "Query too short for semantic search."}
    scored: list[tuple[int, str, str, int]] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or not _allowed_path(path, roots):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            blob = "\n".join(lines).lower()
            name = path.name.lower()
            score = sum(blob.count(t) * 2 + name.count(t) * 5 for t in terms)
            if score <= 0:
                continue
            snippet_line = 1
            snippet = ""
            for line_no, line in enumerate(lines, 1):
                low = line.lower()
                if any(t in low for t in terms):
                    snippet_line = line_no
                    snippet = line.strip()[:200]
                    break
            try:
                rel = path.relative_to(repo_root).as_posix()
            except ValueError:
                rel = path.name
            scored.append((score, rel, snippet, snippet_line))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: max(1, min(int(limit or 15), 25))]
    if not top:
        return {"hits": [], "count": 0, "text": f'No semantic matches for "{" ".join(terms[:6])}".'}
    hits = [{"file": rel, "line": ln, "score": sc, "text": snip} for sc, rel, snip, ln in top]
    text = "\n".join(f"{h['file']}:{h['line']} (score {h['score']}): {h['text']}" for h in hits)
    return {"hits": hits, "count": len(hits), "text": text, "query": " ".join(terms)}


def run_git_readonly(repo_root: Path, command: str) -> dict:
    import subprocess

    repo_root = repo_root.resolve()
    cmd = str(command or "status").strip().lower()
    allowed = {
        "status": ["git", "status", "--short"],
        "diff-stat": ["git", "diff", "--stat"],
        "diff-names": ["git", "diff", "--name-only"],
        "log": ["git", "log", "-5", "--oneline"],
    }
    if cmd not in allowed:
        return {"ok": False, "text": f"Git command not allowed: {cmd}. Use status, diff-stat, diff-names, or log."}
    try:
        proc = subprocess.run(
            allowed[cmd],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "text": "Git command timed out."}
    except OSError as exc:
        return {"ok": False, "text": str(exc)}
    out = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
    ok = proc.returncode == 0
    return {"ok": ok, "command": cmd, "text": out[-5000:] if out else "(empty)", "exitCode": proc.returncode}


def parse_all_patches(text: str) -> list[dict]:
    patches: list[dict] = []
    for block in re.finditer(r"<<<patch\s+([\s\S]*?)>>>", str(text or ""), re.IGNORECASE):
        body = block.group(1)
        file_match = re.search(r"^\s*file:\s*(.+)$", body, re.IGNORECASE | re.MULTILINE)
        old_match = re.search(r"^\s*old:\s*\n([\s\S]*?)(?=^\s*new:\s*\n)", body, re.IGNORECASE | re.MULTILINE)
        new_match = re.search(r"^\s*new:\s*\n([\s\S]*)$", body, re.IGNORECASE | re.MULTILINE)
        if file_match and old_match and new_match:
            patches.append(
                {
                    "file": file_match.group(1).strip(),
                    "old": old_match.group(1).replace("\r\n", "\n"),
                    "new": new_match.group(1).replace("\r\n", "\n"),
                }
            )
    return patches


def apply_program_patches(repo_root: Path, site_dir: Path, patches: list[dict], *, dry_run: bool = False) -> dict:
    results = []
    for spec in patches or []:
        res = apply_program_patch(
            repo_root,
            site_dir,
            spec.get("file", ""),
            spec.get("old", ""),
            spec.get("new", ""),
            dry_run=dry_run,
        )
        results.append(res)
    ok = all(r.get("ok") for r in results) if results else False
    text = "\n".join(r.get("text", "") for r in results) or "No patches applied."
    return {"ok": ok, "count": len(results), "results": results, "text": text}
