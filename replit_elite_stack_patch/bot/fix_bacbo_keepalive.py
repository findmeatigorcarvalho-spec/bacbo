#!/usr/bin/env python3
"""Disable KeepAlive in bacbo_royal_complete.py (Replit PORT steal → SIGKILL -9)."""
from __future__ import annotations

import ast
import re
import shutil
import time
from pathlib import Path

MARK = "LUX_KEEPALIVE_OFF_V1"


def _candidates() -> list[Path]:
    roots = [
        Path("/home/runner/workspace"),
        Path.cwd(),
        Path(__file__).resolve().parents[1],
        Path(__file__).resolve().parents[2],
    ]
    out: list[Path] = []
    for r in roots:
        for p in (r / "bacbo_royal_complete.py", r / "bot" / "bacbo_royal_complete.py"):
            if p.is_file() and p not in out:
                out.append(p)
    return out


def patch(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if MARK in raw and "return  # LUX_KEEPALIVE_OFF_V1" in raw:
        return "ALREADY"
    shutil.copy2(path, path.with_suffix(path.suffix + f".bak_ka_{int(time.time())}"))
    text = raw
    n_def = 0
    n_call = 0

    def _inject_return(m: re.Match[str]) -> str:
        nonlocal n_def
        n_def += 1
        return (
            m.group(1)
            + f"    return  # {MARK} — Replit PORT bind → SIGKILL -9\n"
        )

    text, _ = re.subn(
        r"(^def\s+(keep_alive|start_keepalive|keepalive|_keep_alive)\s*\([^)]*\)\s*:\s*\n)",
        _inject_return,
        text,
        flags=re.M | re.I,
    )

    text, n_call = re.subn(
        r"(?m)^([ \t]*)keep_alive\s*\(\s*\)\s*$",
        rf"\1pass  # {MARK} keep_alive()",
        text,
    )

    # Also neutralize threaded targets: Thread(target=keep_alive)
    text2, n_th = re.subn(
        r"target\s*=\s*keep_alive\b",
        f"target=lambda: None  # {MARK}",
        text,
    )
    text = text2

    if MARK not in text:
        stub = (
            f"\n# --- {MARK} ---\n"
            f"def keep_alive(*_a, **_k):\n"
            f"    print('[KEEPALIVE-OFF] megafile stub')\n"
            f"    return  # {MARK}\n"
            f"# --- end {MARK} ---\n"
        )
        idx = text.find("asyncio.run(main")
        if idx < 0:
            idx = text.find("if __name__")
        if idx >= 0:
            text = text[:idx] + stub + text[idx:]
        else:
            text = text + stub

    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    ast.parse(path.read_text(encoding="utf-8"))
    return f"PATCHED n_def={n_def} n_call={n_call} n_thread={n_th}"


def main() -> int:
    paths = _candidates()
    if not paths:
        print("NO_BACBO_FILE")
        return 2
    for p in paths:
        try:
            print(p, patch(p))
        except Exception as exc:
            print(p, "FAIL", repr(exc))
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
