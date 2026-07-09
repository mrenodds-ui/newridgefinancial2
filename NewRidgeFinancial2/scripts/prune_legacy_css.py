#!/usr/bin/env python3
"""Remove legacy page-vocabulary CSS from styles.css; move workstation hp-* base to bridge."""
from __future__ import annotations

from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
STYLES = SITE / "styles.css"
BRIDGE = SITE / "workstation-moonshot-bridge.css"

# 1-based inclusive line ranges to keep in styles.css
KEEP_RANGES = [
    (1, 261),
    (337, 341),  # .app-ico
    (491, 534),  # .main / .stage / .page-frame
    (742, 753),  # boot helpers + .pv-spinner
    (5192, 7724),  # @media print + workstation + nr2-* utilities
]

# 1-based inclusive — workstation hp markup still emitted by workstation-page.js
WS_HP_RANGES = [
    (1734, 1763),
    (1855, 1958),
    (1996, 1996),
    (2511, 2513),
    (2682, 2694),
    (2741, 2835),
]


def lines_in_ranges(ranges: list[tuple[int, int]], all_lines: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[int] = set()
    for start, end in ranges:
        for i in range(start, end + 1):
            if i in seen:
                continue
            seen.add(i)
            out.append(all_lines[i - 1])
    return out


def main() -> None:
    text = STYLES.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    keep_nums = set()
    for start, end in KEEP_RANGES:
        keep_nums.update(range(start, end + 1))

    ws_hp = lines_in_ranges(WS_HP_RANGES, lines)
    bridge_text = BRIDGE.read_text(encoding="utf-8")
    if "Workstation hp-* base" not in bridge_text:
        BRIDGE.write_text(
            bridge_text.rstrip()
            + "\n\n/* Workstation hp-* base (legacy class names; financial app uses ms-* only) */\n"
            + "".join(ws_hp)
            + "\n",
            encoding="utf-8",
        )

    pruned = [line for i, line in enumerate(lines, 1) if i in keep_nums]
    header = "/* NR2 base shell + workstation — moonshot staff pages use nr2-moonshot-*.css */\n"
    STYLES.write_text(header + "".join(pruned), encoding="utf-8")
    print(f"styles.css: {len(lines)} -> {len(pruned)} lines")
    print(f"workstation bridge: +{len(ws_hp)} hp lines")


if __name__ == "__main__":
    main()
