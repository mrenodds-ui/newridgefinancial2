"""Analyze legal Miranda reference audio and emit TTS calibration JSON."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from statistics import median
from typing import Any

import imageio_ffmpeg
import librosa
import numpy as np
from mutagen.mp3 import MP3

ROOT = Path(__file__).resolve().parents[1]
REF_DIR = ROOT / "NewRidgeFinancial2" / "data" / "miranda_reference"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Legal NPR sources with embedded film SOUNDBITE excerpts.
SOURCES: list[dict[str, Any]] = [
    {
        "file": "npr_prada_nichols.mp3",
        "url": "https://www.npr.org/2006/07/08/5543033/streeps-prada-performance-a-bit-of-nichols",
        "film_window": (38, 58),
        "reference_text": (
            "My flight has been cancelled. There's some absurd weather problem. "
            "I need to get home tonight. The twins have a recital tomorrow morning at school."
        ),
    },
    {
        "file": "npr_prada_review.mp3",
        "url": "https://www.npr.org/2006/06/30/5525317/the-devil-wears-prada-wears-thin",
        "film_window": (42, 52),
        "reference_text": "I don't understand why it's so difficult to confirm an appointment.",
    },
]

CLIP_CAFE_HINTS = {
    "thats_all": {"line": "That's all.", "words": 2, "duration_sec": 1.2},
    "couldnt_be_clearer": {"line": "I couldn't have been clearer.", "words": 5, "duration_sec": 6.0},
    "coffee_isnt_here": {"line": "Is there some reason that my coffee isn't here?", "words": 11, "duration_sec": 10.0},
    "glacial_pace": {"line": "By all means, move at a glacial pace.", "words": 8, "duration_sec": 5.5},
}

BASELINE_WPM = 180  # Edge neural conversational baseline for SSML rate math.

# Never speak faster than glacial v1 — measured NPR windows can include host bleed.
V1_BROWSER_MAX_RATE = {
    "leanIn": 0.4,
    "setup": 0.42,
    "stress": 0.3,
    "cutting": 0.36,
    "train": 0.44,
    "dismissal": 0.26,
}
V1_NEURAL_RATE_CAP = {
    "leanIn": "-44%",
    "setup": "-44%",
    "stress": "-68%",
    "cutting": "-54%",
    "train": "-40%",
    "dismissal": "-74%",
}


def ffmpeg_to_wav(src: Path, dst: Path) -> None:
    subprocess.run(
        [FFMPEG, "-y", "-i", str(src), "-ar", "22050", "-ac", "1", str(dst)],
        check=True,
        capture_output=True,
    )


def segment_speech(y: np.ndarray, sr: int, top_db: float = 28) -> list[dict[str, Any]]:
    intervals = librosa.effects.split(y, top_db=top_db)
    segments: list[dict[str, Any]] = []
    for start, end in intervals:
        chunk = y[start:end]
        dur = (end - start) / sr
        if dur < 0.12:
            continue
        rms = float(np.sqrt(np.mean(chunk**2)))
        pitch_hz = median_pitch(chunk, sr)
        segments.append(
            {
                "start_sec": round(start / sr, 2),
                "end_sec": round(end / sr, 2),
                "duration_sec": round(dur, 2),
                "rms": round(rms, 4),
                "pitch_hz": pitch_hz,
            }
        )
    return segments


def median_pitch(chunk: np.ndarray, sr: int) -> float | None:
    if len(chunk) < sr * 0.18:
        return None
    f0 = librosa.yin(chunk, fmin=120, fmax=380, sr=sr)
    voiced = f0[(f0 > 0) & np.isfinite(f0)]
    if len(voiced) < 3:
        return None
    return round(float(np.median(voiced)), 1)


def pause_stats(segments: list[dict[str, Any]]) -> dict[str, float]:
    speech = sum(s["duration_sec"] for s in segments)
    pause = 0.0
    gaps: list[float] = []
    for a, b in zip(segments, segments[1:]):
        gap = b["start_sec"] - a["end_sec"]
        if gap > 0.05:
            pause += gap
            gaps.append(round(gap * 1000))
    return {
        "speech_sec": round(speech, 2),
        "pause_sec": round(pause, 2),
        "pause_ratio": round(pause / max(speech, 0.01), 2),
        "gap_ms_median": round(median(gaps), 0) if gaps else 0.0,
        "gap_ms_p75": round(float(np.percentile(gaps, 75)), 0) if gaps else 0.0,
    }


def estimate_wpm(text: str, speech_sec: float) -> float | None:
    words = len(re.findall(r"\w+", text))
    if speech_sec <= 0 or words == 0:
        return None
    return round(words / (speech_sec / 60.0), 1)


def wpm_to_ssml_rate(target_wpm: float) -> str:
    factor = max(0.18, min(0.95, target_wpm / BASELINE_WPM))
    pct = int(round((factor - 1.0) * 100))
    return f"{pct}%"


def wpm_to_browser_rate(target_wpm: float) -> float:
    factor = max(0.18, min(0.95, target_wpm / BASELINE_WPM))
    return round(factor, 2)


def ssml_rate_num(rate: str) -> int:
    return int(str(rate).strip().rstrip("%"))


def clamp_ssml_slower(computed: str, cap: str) -> str:
    """Cap SSML rate — never faster (closer to zero) than v1 glacial."""
    return f"{min(ssml_rate_num(computed), ssml_rate_num(cap))}%"


def clamp_browser_slower(computed: float, cap: float) -> float:
    return round(min(computed, cap), 2)


def clip_cafe_wpm() -> dict[str, float]:
    out: dict[str, float] = {}
    for key, hint in CLIP_CAFE_HINTS.items():
        dur = float(hint["duration_sec"])
        wpm = estimate_wpm(str(hint["line"]), dur)
        if wpm is not None:
            out[key] = wpm
    return out


def analyze_source(src: dict[str, Any]) -> dict[str, Any]:
    path = REF_DIR / str(src["file"])
    if not path.exists():
        raise FileNotFoundError(f"Missing {path} — download with yt-dlp from {src['url']}")

    meta = MP3(path)
    wav = path.with_suffix(".wav")
    ffmpeg_to_wav(path, wav)
    y, sr = librosa.load(wav, sr=22050, mono=True)

    win_start, win_end = src["film_window"]
    all_segments = segment_speech(y, sr)
    window_segments = [s for s in all_segments if win_start <= s["start_sec"] <= win_end]

    # Prefer female-register segments (Miranda) inside the annotated film window.
    female_segments = [
        s for s in window_segments if s.get("pitch_hz") and float(s["pitch_hz"]) >= 155
    ]
    film_segments = female_segments if len(female_segments) >= 3 else window_segments
    stats = pause_stats(film_segments)
    wpm = estimate_wpm(str(src["reference_text"]), stats["speech_sec"])

    return {
        "file": path.name,
        "source_url": src["url"],
        "film_window_sec": [win_start, win_end],
        "reference_text": src["reference_text"],
        "segments_used": len(film_segments),
        "wpm": wpm,
        **stats,
        "median_pitch_hz": round(
            float(np.median([s["pitch_hz"] for s in film_segments if s.get("pitch_hz")])),
            1,
        )
        if any(s.get("pitch_hz") for s in film_segments)
        else None,
    }


def build_calibration(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    cafe = clip_cafe_wpm()
    # Drop host-bleed measurements (>105 WPM); lean on Clip.Cafe line timing.
    valid_wpms = [a["wpm"] for a in analyses if a.get("wpm") and a["wpm"] <= 105]
    wpms = valid_wpms + [v for k, v in cafe.items() if k != "thats_all"]
    pause_ratios = [
        a["pause_ratio"]
        for a in analyses
        if a.get("pause_ratio") and a["wpm"] and a["wpm"] <= 105
    ]
    gap_medians = [
        a["gap_ms_median"]
        for a in analyses
        if a.get("gap_ms_median") and a["wpm"] and a["wpm"] <= 105
    ]

    film_wpm = float(median(wpms)) if wpms else 72.0
    dismissal_wpm = cafe.get("couldnt_be_clearer", film_wpm * 0.88)
    stress_wpm = cafe.get("glacial_pace", film_wpm * 0.95)
    setup_wpm = cafe.get("coffee_isnt_here", film_wpm * 0.92)
    cutting_wpm = film_wpm * 0.9
    lean_wpm = film_wpm

    sentence_break = int(round(median(gap_medians) if gap_medians else 1200))
    sentence_break = int(max(1100, min(2100, sentence_break)))
    bridge_default = int(round(sentence_break * 0.92))
    pause_after_stress = int(round(max(2600, sentence_break * 2.2)))
    pause_after_dismissal = int(round(max(3000, sentence_break * 2.5)))

    raw_neural = {
        "leanIn": (wpm_to_ssml_rate(lean_wpm), "-5%", "soft"),
        "setup": (wpm_to_ssml_rate(setup_wpm), "-6%", "x-soft"),
        "stress": (wpm_to_ssml_rate(stress_wpm), "-8%", "soft"),
        "cutting": (wpm_to_ssml_rate(cutting_wpm), "+1%", "soft"),
        "train": (wpm_to_ssml_rate(lean_wpm * 1.04), "-4%", "soft"),
        "dismissal": (wpm_to_ssml_rate(dismissal_wpm), "-12%", "x-soft"),
    }
    neural = {
        kind: (
            clamp_ssml_slower(vals[0], V1_NEURAL_RATE_CAP[kind]),
            vals[1],
            vals[2],
        )
        for kind, vals in raw_neural.items()
    }

    raw_browser = {
        kind: wpm_to_browser_rate(
            {
                "leanIn": lean_wpm,
                "setup": setup_wpm,
                "stress": stress_wpm,
                "cutting": cutting_wpm,
                "train": lean_wpm * 1.04,
                "dismissal": dismissal_wpm,
            }[kind]
        )
        for kind in V1_BROWSER_MAX_RATE
    }
    browser = {
        kind: {
            "rate": clamp_browser_slower(raw_browser[kind], V1_BROWSER_MAX_RATE[kind]),
            "pitch": {"leanIn": 0.76, "setup": 0.77, "stress": 0.73, "cutting": 0.84, "train": 0.77, "dismissal": 0.68}[kind],
            "volume": {"leanIn": 0.7, "setup": 0.66, "stress": 0.72, "cutting": 0.7, "train": 0.71, "dismissal": 0.58}[kind],
        }
        for kind in V1_BROWSER_MAX_RATE
    }

    return {
        "profile": "miranda-glacial-v2-ref",
        "baseline_wpm": BASELINE_WPM,
        "generated_from": [a["file"] for a in analyses],
        "metrics": {
            "film_wpm_median": round(float(film_wpm), 1),
            "pause_ratio_median": round(float(median(pause_ratios)), 2) if pause_ratios else None,
            "sentence_gap_ms_median": sentence_break,
            "clip_cafe_wpm": cafe,
        },
        "timing": {
            "sentence_break_ms": sentence_break,
            "bridge_default_ms": bridge_default,
            "pause_after_stress_ms": pause_after_stress,
            "pause_after_dismissal_ms": pause_after_dismissal,
            "chunk_pause_ms": sentence_break,
            "stress_bridge_ms": bridge_default,
            "line_pause_ms": pause_after_stress,
            "dismissal_pause_ms": int(round(pause_after_dismissal * 0.68)),
        },
        "neural_prosody": {
            kind: {"rate": vals[0], "pitch": vals[1], "volume": vals[2]}
            for kind, vals in neural.items()
        },
        "browser_delivery": browser,
        "sources": analyses,
        "calibration_notes": [
            "Derived from legal NPR film SOUNDBITE excerpts + Clip.Cafe line timing.",
            f"Target film cadence ~{round(float(film_wpm))} WPM (vs ~{BASELINE_WPM} conversational).",
            "Neural SSML rates auto-mapped from measured WPM; browser rates mirror same factors.",
        ],
    }


def main() -> int:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    analyses = [analyze_source(src) for src in SOURCES]
    calibration = build_calibration(analyses)

    analysis_out = REF_DIR / "miranda_audio_analysis.json"
    calibration_out = REF_DIR / "miranda_tts_calibration.json"

    analysis_out.write_text(
        json.dumps({"sources": analyses, "clip_cafe_hints": CLIP_CAFE_HINTS}, indent=2),
        encoding="utf-8",
    )
    calibration_out.write_text(json.dumps(calibration, indent=2), encoding="utf-8")

    print(json.dumps(calibration, indent=2))
    print(f"\nWrote {analysis_out}")
    print(f"Wrote {calibration_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
