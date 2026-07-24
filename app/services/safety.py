from __future__ import annotations

import re


INJECTION_PATTERNS = {
    "prompt_injection_attempt": [
        r"ignore (all|any|the) previous",
        r"reveal (the )?(system|developer) prompt",
        r"show (your )?(hidden|private) reasoning",
        r"bypass (the )?(rules|policy|safety)",
        r"pretend (the )?weather api returned",
        r"fabricate (a )?forecast",
    ],
    "forced_guessing_attempt": [
        r"do not ask (me )?(questions|follow[- ]?ups)",
        r"just guess",
        r"make up (the )?(missing|weather|numbers)",
        r"assume everything",
    ],
}


def detect_safety_flags(text: str) -> list[str]:
    lowered = text.lower()
    flags: list[str] = []
    for flag, patterns in INJECTION_PATTERNS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            flags.append(flag)
    return flags
