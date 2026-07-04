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


def default_search_index_path(repo_root: Path) -> Path:
    return repo_root.resolve() / "app_data" / "nr2" / "program_search_index.json"


def _extract_symbols_and_snippets(lines: list[str], limit: int = 10) -> tuple[list[str], list[dict]]:
    symbols: list[str] = []
    snippets: list[dict] = []
    sym_re = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)",
    )
    def_re = re.compile(r"^\s*def\s+([A-Za-z_][\w]*)")
    for line_no, line in enumerate(lines, 1):
        for rx in (sym_re, def_re):
            m = rx.match(line)
            if m:
                name = m.group(1)
                if name not in symbols:
                    symbols.append(name)
                if len(snippets) < limit:
                    snippets.append({"line": line_no, "text": line.strip()[:200], "kind": "def"})
                break
    return symbols[:80], snippets


def build_program_search_index(repo_root: Path, site_dir: Path, index_path: Path | None = None) -> dict:
    import json
    from datetime import datetime, timezone

    repo_root, _, roots = _resolve_roots(repo_root, site_dir)
    out_path = index_path or default_search_index_path(repo_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    files: list[dict] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or not _allowed_path(path, roots):
                continue
            try:
                stat = path.stat()
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            try:
                rel = path.relative_to(repo_root).as_posix()
            except ValueError:
                rel = path.name
            symbols, snippets = _extract_symbols_and_snippets(lines)
            files.append(
                {
                    "file": rel,
                    "mtime": int(stat.st_mtime),
                    "size": int(stat.st_size),
                    "symbols": symbols,
                    "snippets": snippets,
                }
            )
    payload = {
        "version": 1,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "fileCount": len(files),
        "files": files,
    }
    out_path.write_text(json.dumps(payload, indent=0)[:2_000_000], encoding="utf-8")
    return {"ok": True, "path": str(out_path), "fileCount": len(files), "text": f"Built search index with {len(files)} files."}


def load_program_search_index(index_path: Path, max_age_hours: int = 36) -> dict | None:
    import json
    from datetime import datetime, timezone

    if not index_path.is_file():
        return None
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        return None
    built = data.get("builtAt")
    if built:
        try:
            ts = datetime.fromisoformat(str(built).replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 3600.0
            if age_h > max(1, int(max_age_hours or 36)):
                return None
        except ValueError:
            return None
    return data


def _score_index_entries(index: dict, terms: list[str], limit: int = 120) -> list[tuple[int, str, str, int]]:
    scored: list[tuple[int, str, str, int]] = []
    for entry in index.get("files") or []:
        rel = str(entry.get("file") or "")
        if not rel:
            continue
        path_boost = _path_score(rel, terms)
        sym_blob = " ".join(entry.get("symbols") or []).lower()
        sym_hits = sum(1 for t in terms if t in sym_blob or any(t in s.lower() for s in (entry.get("symbols") or [])))
        score = path_boost + sym_hits * 12
        best_line = 1
        best_text = ""
        for snip in entry.get("snippets") or []:
            text = str(snip.get("text") or "")
            low = text.lower()
            hits = sum(1 for t in terms if t in low)
            if hits <= 0:
                continue
            line_score = hits * 6 + _line_definition_boost(text, terms) + path_boost
            if line_score > score:
                score = line_score
                best_line = int(snip.get("line") or 1)
                best_text = text
        if sym_hits > 0 and not best_text:
            best_text = f"symbols: {', '.join((entry.get('symbols') or [])[:6])}"
        if score > 0:
            scored.append((score, rel, best_text[:200], best_line))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[: max(10, min(int(limit or 120), 200))]


def ensure_program_search_index(repo_root: Path, site_dir: Path, index_path: Path | None = None) -> dict:
    path = index_path or default_search_index_path(repo_root)
    loaded = load_program_search_index(path)
    if loaded:
        return loaded
    built = build_program_search_index(repo_root, site_dir, path)
    if not built.get("ok"):
        return {"files": []}
    return load_program_search_index(path) or {"files": []}


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


def _query_search_terms(query: str) -> list[str]:
    raw = str(query or "")
    terms: set[str] = set()
    for t in re.findall(r"[a-z0-9_]{3,}", raw.lower()):
        terms.add(t)
    for chunk in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", raw):
        if len(chunk) >= 3:
            terms.add(chunk.lower())
    for chunk in re.findall(r"[a-z]+(?:_[a-z]+)+", raw.lower()):
        terms.update(p for p in chunk.split("_") if len(p) >= 3)
    stop = {
        "the",
        "and",
        "for",
        "how",
        "what",
        "does",
        "with",
        "where",
        "when",
        "why",
        "this",
        "that",
        "from",
        "into",
        "handled",
        "handle",
        "work",
        "works",
        "code",
        "source",
        "program",
    }
    out = [t for t in terms if t not in stop]
    return out[:12]


def _path_score(rel: str, terms: list[str]) -> int:
    low = rel.lower()
    score = 0
    if "/site/hal-" in low or low.endswith(("hal-agent.js", "hal-core.js", "app.js")):
        score += 10
    if "program_source_grep.py" in low or "desktop_app.py" in low:
        score += 6
    for t in terms:
        if t in low:
            score += 14
    return score


def _line_definition_boost(line: str, terms: list[str]) -> int:
    low = line.lower()
    boost = 0
    for t in terms[:6]:
        if re.search(rf"\b(function|def|const|class|async\s+function)\s+[\w]*{re.escape(t)}", low):
            boost += 18
        elif re.search(rf"\b{re.escape(t)}\s*[=(:]", low):
            boost += 8
    return boost


def _cosine_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    return max(0.0, min(1.0, dot))


def _char_ngram_vector(text: str, n: int = 3) -> dict[str, float]:
    import math

    low = re.sub(r"\s+", " ", str(text or "").lower())
    vec: dict[str, float] = {}
    for i in range(max(0, len(low) - n + 1)):
        gram = low[i : i + n]
        if gram.strip():
            vec[gram] = vec.get(gram, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def _ollama_embedding(
    text: str,
    model: str = "nomic-embed-text",
    endpoint: str = "http://127.0.0.1:11434/api/embeddings",
) -> list[float] | None:
    import json
    import urllib.error
    import urllib.request

    try:
        payload = json.dumps({"model": model, "prompt": str(text or "")[:2000]}).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        emb = data.get("embedding")
        if isinstance(emb, list) and emb:
            return [float(x) for x in emb]
    except (OSError, urllib.error.URLError, ValueError, TypeError, TimeoutError):
        return None
    return None


def _cosine_dense(a: list[float], b: list[float]) -> float:
    import math

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))


def _embedding_rerank(query: str, candidates: list[tuple[int, str, str, int]], limit: int) -> tuple[list[tuple[int, str, str, int]], str]:
    if not candidates:
        return [], "lexical"
    q_text = str(query or "").strip()
    q_vec = _char_ngram_vector(q_text)
    q_emb = _ollama_embedding(q_text)
    mode = "ollama-embed" if q_emb else "ngram-embed"
    reranked: list[tuple[float, int, str, str, int]] = []
    seen_files: set[str] = set()
    for lex_score, rel, snip, line_no in candidates[:80]:
        if rel in seen_files and len(reranked) > limit * 2:
            continue
        seen_files.add(rel)
        embed_score = _cosine_sparse(q_vec, _char_ngram_vector(snip))
        if q_emb:
            line_emb = _ollama_embedding(snip)
            if line_emb:
                embed_score = max(embed_score, _cosine_dense(q_emb, line_emb))
        combined = lex_score * 0.45 + embed_score * 400.0
        reranked.append((combined, lex_score, rel, snip, line_no))
    reranked.sort(key=lambda x: x[0], reverse=True)
    top = [(int(ls), rel, snip, ln) for _, ls, rel, snip, ln in reranked[:limit]]
    return top, mode


def semantic_search_program(repo_root: Path, site_dir: Path, query: str, limit: int = 15) -> dict:
    """Hybrid lexical + embedding-lite search across program source."""
    repo_root, site_dir, roots = _resolve_roots(repo_root, site_dir)
    terms = _query_search_terms(query)
    if not terms:
        return {"hits": [], "count": 0, "text": "Query too short for semantic search."}

    exact = " ".join(str(query or "").split()).strip()
    grep_hits: list[dict] = []
    if len(exact) >= 4:
        grep_out = grep_program_source(repo_root, site_dir, exact, limit=6)
        grep_hits = list(grep_out.get("hits") or [])

    scored: list[tuple[int, str, str, int]] = []
    seen: set[tuple[str, int]] = set()
    for hit in grep_hits:
        key = (hit.get("file", ""), int(hit.get("line") or 1))
        if key in seen:
            continue
        seen.add(key)
        scored.append((500 + _path_score(hit.get("file", ""), terms), hit.get("file", ""), hit.get("text", ""), key[1]))

    cap = max(1, min(int(limit or 15), 25))
    index = ensure_program_search_index(repo_root, site_dir)
    index_hits = _score_index_entries(index, terms, limit=80)
    for score, rel, snip, line_no in index_hits:
        key = (rel, line_no)
        if key in seen:
            continue
        seen.add(key)
        scored.append((score + 40, rel, snip, line_no))

    if len(scored) < cap:
        for root in roots:
            for path in root.rglob("*"):
                if not path.is_file() or not _allowed_path(path, roots):
                    continue
                if len(scored) >= cap * 4:
                    break
                try:
                    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
                except OSError:
                    continue
                try:
                    rel = path.relative_to(repo_root).as_posix()
                except ValueError:
                    rel = path.name
                path_boost = _path_score(rel, terms)
                for line_no, line in enumerate(lines, 1):
                    low = line.lower()
                    term_hits = sum(1 for t in terms if t in low)
                    if term_hits <= 0:
                        continue
                    score = term_hits * 4 + path_boost + _line_definition_boost(line, terms)
                    if score <= 0:
                        continue
                    key = (rel, line_no)
                    if key in seen:
                        continue
                    seen.add(key)
                    scored.append((score, rel, line.strip()[:200], line_no))
            if len(scored) >= cap * 4:
                break

    scored.sort(key=lambda x: x[0], reverse=True)
    top, mode = _embedding_rerank(str(query or ""), scored, cap)
    if not top:
        return {"hits": [], "count": 0, "text": f'No semantic matches for "{" ".join(terms[:6])}".'}
    hits = [{"file": rel, "line": ln, "score": sc, "text": snip} for sc, rel, snip, ln in top]
    text = "\n".join(f"{h['file']}:{h['line']} (score {h['score']} · {mode}): {h['text']}" for h in hits)
    return {"hits": hits, "count": len(hits), "text": text, "query": " ".join(terms), "mode": mode, "indexed": bool((index.get("files") or []))}


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


def run_allowlisted_command(repo_root: Path, command_id: str) -> dict:
    """Run a fixed allowlist of repo-scoped commands (no arbitrary shell)."""
    import subprocess

    repo_root = repo_root.resolve()
    nr2 = repo_root / "NewRidgeFinancial2"
    if not nr2.is_dir():
        nr2 = repo_root
    cmd_id = str(command_id or "validate-hal").strip().lower().replace("_", "-")
    allowed: dict[str, tuple[list[str], str, int]] = {
        "validate-hal": (["node", "validate-hal.mjs"], str(nr2), 120),
        "node-check-core": (["node", "--check", "site/hal-core.js"], str(nr2), 30),
        "node-check-agent": (["node", "--check", "site/hal-agent.js"], str(nr2), 30),
        "node-check-app": (["node", "--check", "site/app.js"], str(nr2), 30),
        "node-check-loop": (["node", "--check", "site/hal-agent-loop.js"], str(nr2), 30),
        "node-check-all": (
            ["node", "--check", "site/hal-core.js"],
            str(nr2),
            30,
        ),
        "git-status": (["git", "status", "--short"], str(repo_root), 30),
        "git-diff-stat": (["git", "diff", "--stat"], str(repo_root), 30),
        "git-diff-names": (["git", "diff", "--name-only"], str(repo_root), 30),
        "git-log": (["git", "log", "-5", "--oneline"], str(repo_root), 30),
    }
    if cmd_id == "rebuild-search-index":
        site = nr2 / "site"
        return build_program_search_index(repo_root, site if site.is_dir() else nr2)
    if cmd_id == "node-check-all":
        files = [
            "site/hal-core.js",
            "site/hal-agent.js",
            "site/hal-agent-loop.js",
            "site/app.js",
        ]
        results = []
        all_ok = True
        for rel in files:
            try:
                proc = subprocess.run(
                    ["node", "--check", rel],
                    cwd=str(nr2),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                ok = proc.returncode == 0
                all_ok = all_ok and ok
                err = ((proc.stderr or proc.stdout or "").strip())[:300]
                results.append(f"{'PASS' if ok else 'FAIL'} {rel}" + (f": {err}" if err and not ok else ""))
            except OSError as exc:
                all_ok = False
                results.append(f"FAIL {rel}: {exc}")
        text = "\n".join(results)
        return {"ok": all_ok, "command": cmd_id, "text": text, "exitCode": 0 if all_ok else 1}
    if cmd_id not in allowed:
        keys = ", ".join(sorted(allowed.keys()))
        return {"ok": False, "text": f"Command not allowed: {cmd_id}. Use: {keys}."}
    argv, cwd, timeout = allowed[cmd_id]
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "text": f"Command timed out: {cmd_id}."}
    except OSError as exc:
        return {"ok": False, "text": str(exc)}
    out = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
    ok = proc.returncode == 0
    return {
        "ok": ok,
        "command": cmd_id,
        "text": out[-5000:] if out else "(empty)",
        "exitCode": proc.returncode,
    }


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
