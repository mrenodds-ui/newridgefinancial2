"""Batch Trellis Add Patient + Verify for remaining tomorrow worklist (Playwright).

Much faster than MCP click-by-click. Uses .env.vyne.local credentials.
Writes results to app_data/nr2/vyne_pulls/tomorrow_trellis_verify_results_*.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "app_data" / "nr2" / "vyne_pulls"
ENV_FILE = ROOT / ".env.vyne.local"
REF = Path(r"C:\ProgramData\Sensei Gateway Client\DataSync\0000950863\Reference")
DATE = "2026-07-16"
PENDING = OUT_DIR / f"tomorrow_trellis_pending_batch_{DATE}.json"
RESULTS = OUT_DIR / f"tomorrow_trellis_verify_results_{DATE}.json"
WORKLIST = OUT_DIR / f"tomorrow_trellis_add_worklist_{DATE}.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _trellis_carrier_map import CARRIER_MAP  # noqa: E402


def _load_env() -> None:
    if not ENV_FILE.is_file():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        # Always take file values (setdefault left a stale Emporia4589$ in the shell env).
        os.environ[k.strip()] = v.strip()


def _norm_dob(raw: str) -> str:
    text = str(raw or "").strip().replace("-", "/")
    if not text or text.startswith("0001"):
        return ""
    parts = text.split("T")[0].split(" ")[0].split("/")
    if len(parts) != 3:
        return ""
    a, b, c = parts
    try:
        if len(a) == 4:  # Y/M/D
            y, m, d = a, b, c
        else:  # M/D/Y
            m, d, y = a, b, c
        return f"{int(m):02d}/{int(d):02d}/{int(y):04d}"
    except ValueError:
        return ""


def _load_rp(ref: str) -> dict:
    path = REF / f"person_{ref}.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    info = data.get("Person") or data.get("PERSON") or data
    sex = str(info.get("Sex") or info.get("Gender") or "").strip().upper()
    gender = {"M": "Male", "F": "Female", "MALE": "Male", "FEMALE": "Female"}.get(sex, sex)
    return {
        "first": str(info.get("FirstName") or info.get("Firstname") or "").strip(),
        "last": str(info.get("LastName") or info.get("Lastname") or "").strip(),
        "middle": str(info.get("MiddleName") or info.get("Middlename") or "").strip(),
        "dob": _norm_dob(str(info.get("Birthdate") or info.get("BirthDate") or "")),
        "gender": gender,
    }


def _append_result(rec: dict) -> None:
    d = json.loads(RESULTS.read_text(encoding="utf-8"))
    names = {r.get("patient_name") for r in d["results"]}
    if rec["patient_name"] in names:
        print("already", rec["patient_name"])
        return
    d["results"].append(rec)
    RESULTS.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print("appended", rec["patient_name"], rec["status"], "count", len(d["results"]))


def _remaining() -> list[dict]:
    pending = json.loads(PENDING.read_text(encoding="utf-8"))["patients"]
    done = {r["patient_name"] for r in json.loads(RESULTS.read_text(encoding="utf-8"))["results"]}
    wl = {
        p["patient_name"]: p
        for p in json.loads(WORKLIST.read_text(encoding="utf-8"))["patients"]
    }
    out = []
    for p in pending:
        if p["patient_name"] in done:
            continue
        if not p.get("subscriber_id") or not p.get("softdent_carrier"):
            continue
        carrier = CARRIER_MAP.get(p["softdent_carrier"], p.get("trellis_carrier") or "")
        w = wl.get(p["patient_name"]) or {}
        demo = w.get("demo") or {}
        first = demo.get("first") or p["patient_name"].split(" ", 1)[0]
        last = demo.get("last") or (
            p["patient_name"].split(" ", 1)[1] if " " in p["patient_name"] else ""
        )
        item = {
            **p,
            "first": first,
            "last": last,
            "trellis_carrier": carrier,
        }
        if not item.get("is_self"):
            item["subscriber"] = _load_rp(str(p.get("subscriber_ref") or ""))
        out.append(item)
    # self first
    out.sort(key=lambda x: (0 if x.get("is_self") else 1, x["patient_name"]))
    return out


def _select_ant(page, combobox_locator, option_text: str, type_text: str | None = None) -> None:
    # Ant Design span.ant-select-selection-item intercepts the search input — click wrapper.
    wrapper = combobox_locator.locator("xpath=ancestor::*[contains(@class,'ant-select')][1]")
    if wrapper.count():
        wrapper.first.click(force=True)
    else:
        combobox_locator.click(force=True)
    page.wait_for_timeout(250)
    if type_text is not None:
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(type_text, delay=30)
        page.wait_for_timeout(600)
    # Prefer exact option in open dropdown
    opt = page.locator(
        ".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option-content",
        has_text=re.compile(f"^{re.escape(option_text)}$"),
    )
    if opt.count() == 0:
        opt = page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option-content",
            has_text=option_text,
        )
    if opt.count() == 0:
        opt = page.locator(".ant-select-item-option-content", has_text=re.compile(f"^{re.escape(option_text)}$"))
    if opt.count() == 0:
        # Keep dropdown open and pick first filtered hit via keyboard
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(150)
        page.keyboard.press("Enter")
        page.wait_for_timeout(250)
        return
    opt.first.click(force=True)
    page.wait_for_timeout(250)


def _return_to_eligibility_list(page) -> None:
    for _ in range(6):
        if page.get_by_role("button", name="Add Patient").count():
            return
        clicked = False
        for btn_name in ("close verification", "Back", "Close"):
            btn = page.get_by_role("button", name=re.compile(re.escape(btn_name), re.I))
            if btn.count() and btn.first.is_visible():
                btn.first.click(force=True)
                page.wait_for_timeout(1000)
                clicked = True
                break
        if not clicked:
            page.goto(
                "https://app.vynetrellis.com/Eligibility",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(2500)
    page.wait_for_selector("button:has-text('Add Patient')", timeout=60000)


def _fill_patient(page, rec: dict) -> None:
    _return_to_eligibility_list(page)
    page.get_by_role("button", name="Add Patient").click()
    page.wait_for_timeout(800)
    # Patient section fields (first of each label)
    page.get_by_role("textbox", name="Last Name").first.fill(rec["last"])
    page.get_by_role("textbox", name="First Name").first.fill(rec["first"])
    page.get_by_role("textbox", name="DOB").first.fill(rec["dob"])
    page.get_by_role("textbox", name="Subscriber ID").fill(rec["subscriber_id"])

    gender = rec.get("gender") or "Female"
    _select_ant(page, page.get_by_role("combobox", name="Gender").first, gender)

    if rec.get("is_self"):
        sw = page.get_by_role("switch")
        if sw.get_attribute("aria-checked") != "true":
            sw.click(force=True)
            page.wait_for_timeout(200)
    else:
        sub = rec.get("subscriber") or {}
        if not sub.get("last") or not sub.get("dob"):
            raise RuntimeError(f"missing subscriber demo for {rec['patient_name']}: {sub}")
        # Subscriber section = 2nd set of fields
        page.get_by_role("textbox", name="Last Name").nth(1).fill(sub["last"])
        page.get_by_role("textbox", name="First Name").nth(1).fill(sub["first"])
        page.get_by_role("textbox", name="DOB").nth(1).fill(sub["dob"])
        _select_ant(
            page,
            page.get_by_role("combobox", name="Gender").nth(1),
            sub.get("gender") or "Male",
        )

    carrier = rec["trellis_carrier"]
    _select_ant(
        page,
        page.get_by_role("combobox", name="Carrier"),
        carrier,
        type_text=carrier,
    )

    page.get_by_role("button", name="Verify").click()
    # Wait for status modal / Eligible text
    status = "Unknown"
    for _ in range(60):
        page.wait_for_timeout(500)
        body = page.locator("body").inner_text()
        for label in (
            "Eligible",
            "Not Eligible",
            "Insurance Info Issue",
            "Failed",
            "Info Needed",
            "Unverified",
        ):
            if re.search(rf"\b{re.escape(label)}\b", body):
                # Prefer heading area status
                if page.get_by_text(label, exact=True).count():
                    status = label
                    break
        if status != "Unknown":
            break

    # Try capture carrier id from ClearCoverage if present
    carrier_id = ""
    m = re.search(r"\b(\d{5})\b", page.locator("body").inner_text()[:2500])
    if m:
        carrier_id = m.group(1)

    # Close verification if present
    close_btn = page.get_by_role("button", name="close verification")
    if close_btn.count():
        close_btn.first.click(force=True)
        page.wait_for_timeout(600)
    back_btn = page.get_by_role("button", name="Back")
    if back_btn.count() and back_btn.first.is_visible():
        back_btn.first.click(force=True)
        page.wait_for_timeout(1500)

    _return_to_eligibility_list(page)

    _append_result(
        {
            "patient_name": rec["patient_name"],
            "status": status,
            "carrier_trellis": carrier,
            "carrier_id": carrier_id,
            "softdent_carrier": rec.get("softdent_carrier"),
            "subscriber_id": rec.get("subscriber_id"),
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "notes": "self" if rec.get("is_self") else f"dependent:{rec.get('relationship')}",
            "plan_name": None,
            "effective_date": None,
        }
    )


def main() -> int:
    _load_env()
    user = os.environ["VYNE_AUTOMATION_USERNAME"].strip()
    password = os.environ["VYNE_AUTOMATION_PASSWORD"].strip()
    remaining = _remaining()
    print(f"remaining {len(remaining)}")
    for r in remaining:
        print(
            " -",
            r["patient_name"],
            "SELF" if r.get("is_self") else r.get("relationship"),
            r["trellis_carrier"],
        )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # Bundled Chromium only — system Chrome password manager was injecting Emporia4589$.
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-features=PasswordManagerOnboarding",
                "--disable-save-password-bubble",
            ],
        )
        # Isolated context — no Chrome password-manager autofill (was injecting Emporia4589$).
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            ignore_https_errors=True,
        )
        page = context.new_page()
        try:
            page.goto(
                "https://auth.vynetrellis.com/authenticate?redirect_uri=https%3A%2F%2Fapp.vynetrellis.com&productType=Trellis",
                wait_until="domcontentloaded",
                timeout=90000,
            )
            page.wait_for_timeout(2000)
            # Already authenticated?
            if "app.vynetrellis.com" in page.url and "authenticate" not in page.url:
                print("already in app", page.url)
            else:
                email = page.get_by_label("Email")
                if email.count() == 0:
                    email = page.locator("input[type='email'], input[name='email']").first
                email.click()
                email.fill("")
                email.press_sequentially(user, delay=20)
                pw = page.get_by_label("Password")
                if pw.count() == 0:
                    pw = page.locator("input[type='password']").first
                pw.click()
                # Clear any Chrome autofill (Emporia…) then type Wichita password only.
                pw.fill("")
                page.wait_for_timeout(150)
                pw.press_sequentially(password, delay=25)
                # Sanity: value must be Wichita*, never Emporia*
                typed = pw.input_value()
                if "Emporia" in typed or not typed.startswith("Wichita"):
                    raise RuntimeError(
                        f"password field wrong after type (len={len(typed)} "
                        f"prefix={typed[:7]!r}) — refusing Emporia autofill"
                    )
                print("password_field_ok prefix", typed[:7], "len", len(typed))
                cont = page.get_by_role("button", name="Continue")
                if cont.count() == 0:
                    cont = page.get_by_role("button", name=re.compile("log.?in|sign.?in|continue", re.I))
                cont.first.click()
                page.wait_for_timeout(5000)
                # Org / practice picker (optional) — Wichita org only
                for sel in (
                    page.locator("li").filter(has_text="Michael Christian Reno"),
                    page.get_by_text("Michael Christian Reno DDS PA", exact=False),
                    page.get_by_text("Michael Christian Reno", exact=False),
                ):
                    try:
                        if sel.count() and sel.first.is_visible():
                            sel.first.click(timeout=5000)
                            print("selected org")
                            break
                    except Exception:
                        continue
                page.wait_for_timeout(8000)
                page.screenshot(path=str(OUT_DIR / "batch_login_state.png"))
                # Second Trellis/Vyne Dental login (post org-picker)
                if page.get_by_text("Username (Email)").count() or (
                    page.locator("input[type='password']").count()
                    and "authenticate" in page.url.lower()
                ):
                    print("second login detected")
                    for inp in page.locator("input:visible").all():
                        t = (inp.get_attribute("type") or "").lower()
                        ph = (inp.get_attribute("placeholder") or "").lower()
                        if t == "password":
                            inp.fill("")
                            inp.press_sequentially(password, delay=25)
                        elif "email" in ph or t == "email" or "user" in ph:
                            inp.fill("")
                            inp.press_sequentially(user, delay=20)
                    page.get_by_role(
                        "button", name=re.compile(r"Log In|Continue|Sign In", re.I)
                    ).first.click()
                    page.wait_for_timeout(8000)
            for _ in range(40):
                url = page.url
                if "authenticate" not in url and "app.vynetrellis.com" in url:
                    break
                page.wait_for_timeout(1000)
            for attempt in range(4):
                page.goto(
                    "https://app.vynetrellis.com/Eligibility",
                    wait_until="domcontentloaded",
                    timeout=120000,
                )
                page.wait_for_timeout(2500)
                if page.get_by_role("button", name="Add Patient").count():
                    break
                # Sidebar SPA link used by Trellis
                elig = page.locator("a[href*='Eligibility'], a[href*='eligibility']")
                if elig.count():
                    elig.first.click(timeout=10000)
                    page.wait_for_timeout(2500)
                else:
                    side = page.get_by_role("link", name=re.compile("eligibility-menu-option|Eligibility", re.I))
                    if side.count():
                        side.first.click(timeout=10000)
                        page.wait_for_timeout(2500)
                if page.get_by_role("button", name="Add Patient").count():
                    break
                print(f"eligibility wait attempt {attempt+1} url={page.url}")
                page.screenshot(path=str(OUT_DIR / f"batch_elig_attempt_{attempt+1}.png"))
            page.wait_for_selector("button:has-text('Add Patient')", timeout=90000)
            page.screenshot(path=str(OUT_DIR / "batch_eligibility.png"))
            print("at", page.url)
            # Refuse wrong office if header shows Emporia
            hdr = page.locator("body").inner_text()[:1500]
            if re.search(r"Emporia", hdr, re.I):
                raise RuntimeError("logged into Emporia office — abort; need Wichita")
            if not re.search(r"Michael Christian Reno", hdr, re.I):
                print("WARN: org header not seen in first 1500 chars")

            for rec in remaining:
                print("===", rec["patient_name"])
                try:
                    _fill_patient(page, rec)
                except Exception as exc:  # noqa: BLE001
                    print("FAIL", rec["patient_name"], exc)
                    try:
                        page.screenshot(
                            path=str(OUT_DIR / f"batch_fail_{rec['patient_name'].replace(' ', '_')}.png")
                        )
                    except Exception:
                        pass
                    # Try recover to list
                    try:
                        if page.get_by_role("button", name="Back").count():
                            page.get_by_role("button", name="Back").click()
                            page.wait_for_timeout(1000)
                        else:
                            page.goto(
                                "https://app.vynetrellis.com/Eligibility",
                                wait_until="domcontentloaded",
                                timeout=60000,
                            )
                            page.wait_for_timeout(2000)
                    except Exception:
                        pass
        finally:
            context.close()
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
