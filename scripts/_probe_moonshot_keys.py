"""Probe Moonshot/OpenRouter keys from process env and Windows user registry."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import winreg


def load_user_env(name: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value or "").strip()
    except OSError:
        return ""


def probe(label: str, url: str, key: str, model: str) -> bool:
    if not key:
        print(f"{label}: (empty key)")
        return False
    payload = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "MOONSHOT_OK"}], "max_tokens": 10}
    ).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://github.com/NewRidgeFamilyFinancial",
        "X-Title": "NR2 key probe",
    }
    req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read())
            text = str((body.get("choices") or [{}])[0].get("message", {}).get("content") or "")
            print(f"{label}: OK -> {text[:80]}")
            return True
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        print(f"{label}: HTTP {exc.code} -> {detail}")
        return False
    except Exception as exc:
        print(f"{label}: ERR -> {exc}")
        return False


def main() -> int:
    names = ("OPENROUTER_API_KEY", "MOONSHOT_API_KEY", "KIMI_K2_API_KEY")
    for name in names:
        proc = os.environ.get(name, "").strip()
        user = load_user_env(name)
        print(f"\n{name}:")
        print(f"  process  len={len(proc)} prefix={(proc[:15] + '...') if proc else 'none'}")
        print(f"  registry len={len(user)} prefix={(user[:15] + '...') if user else 'none'}")
        print(f"  same={proc == user}")

    endpoints = [
        ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "moonshotai/kimi-k2"),
        ("moonshot", "https://api.moonshot.ai/v1/chat/completions", "kimi-k2.6"),
    ]
    keys_to_try: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in names:
        for src, val in (("process", os.environ.get(name, "").strip()), ("registry", load_user_env(name))):
            if val and val not in seen:
                seen.add(val)
                keys_to_try.append((f"{name}/{src}", val))

    print("\n--- Probes ---")
    ok = False
    for key_label, key_val in keys_to_try:
        for ep_label, url, model in endpoints:
            if probe(f"{key_label} @ {ep_label}", url, key_val, model):
                ok = True
                print(f"\nWORKING: {key_label} @ {ep_label}")
                return 0
    return 1 if not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
