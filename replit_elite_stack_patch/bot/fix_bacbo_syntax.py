"""Repair bacbo_royal_complete.py SyntaxError from botched mid-file injects.

Usage (on Replit):
  python3 -u bot/fix_bacbo_syntax.py
"""
from __future__ import annotations

import ast
import re
import shutil
import time
from pathlib import Path

CANDIDATES = [
    Path("bacbo_royal_complete.py"),
    Path("bot/bacbo_royal_complete.py"),
    Path("/home/runner/workspace/bacbo_royal_complete.py"),
]

EOF_BLOCK = """

# --- lux_re_harden (safe EOF inject; do not move inside try) ---
try:
    import lux_re_harden  # noqa: F401
    print("[LUXURY] re-harden loaded")
except Exception as _lux_reh_exc:
    print("[LUXURY] re-harden skipped:", _lux_reh_exc)
"""


def _find() -> Path:
    for p in CANDIDATES:
        if p.is_file():
            return p
    raise SystemExit("MISSING bacbo_royal_complete.py")


def _parse(text: str) -> SyntaxError | None:
    try:
        ast.parse(text)
        return None
    except SyntaxError as exc:
        return exc


def _show(err: SyntaxError, text: str, radius: int = 20) -> None:
    lines = text.splitlines()
    ln = err.lineno or 1
    lo = max(0, ln - radius)
    hi = min(len(lines), ln + radius)
    print(f"SYNTAX_ERR line={ln} msg={err.msg}")
    for i in range(lo, hi):
        mark = ">>>" if i + 1 == ln else "   "
        print(f"{mark} {i+1:5d}|{lines[i]}")


def _backup_candidates(path: Path) -> list[Path]:
    out: list[Path] = []
    for extra in (
        path.parent / "bacbo_royal_complete.py.bak_pre_state_fix",
        path.parent / "bacbo_SAVE_EVERYTHING_20260803T173541Z" / "bacbo_royal_complete.py",
        Path("bacbo_SAVE_EVERYTHING_20260803T173541Z/bacbo_royal_complete.py"),
    ):
        if extra.is_file():
            out.append(extra)
    out.extend(
        sorted(
            path.parent.glob(path.name + ".bak*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    )
    return out


def _strip_reharden_blocks(text: str) -> str:
    """Remove prior lux_re_harden injects so we can re-append at EOF safely."""
    # Multiline try/import lux_re_harden/except blocks
    pat = re.compile(
        r"\n[ \t]*try:\n"
        r"(?:[ \t]+.+\n)*?"
        r"[ \t]+import lux_re_harden[^\n]*\n"
        r"(?:[ \t]+.+\n)*?"
        r"[ \t]*except Exception as _lux_reh_exc:\n"
        r"(?:[ \t]+.+\n)*?",
        re.M,
    )
    text2 = pat.sub("\n", text)
    # EOF marker comment blocks
    text2 = re.sub(
        r"\n# --- lux_re_harden \(safe EOF inject; do not move inside try\) ---"
        r"[\s\S]*?(?=\n# ---|\Z)",
        "\n",
        text2,
    )
    return text2


def _close_orphan_try(text: str, err: SyntaxError) -> str:
    if "expected 'except' or 'finally'" not in (err.msg or ""):
        return text
    lines = text.splitlines()
    ln = (err.lineno or 1) - 1
    try_i = None
    for i in range(min(ln, len(lines) - 1), max(-1, ln - 60), -1):
        if re.match(r"^[ \t]*try:\s*$", lines[i]):
            try_i = i
            break
    if try_i is None:
        return text
    indent = re.match(r"^([ \t]*)", lines[try_i]).group(1)
    j = try_i + 1
    while j < len(lines):
        raw = lines[j]
        if not raw.strip() or raw.lstrip().startswith("#"):
            j += 1
            continue
        ind = re.match(r"^([ \t]*)", raw).group(1)
        if len(ind) <= len(indent) and not raw.lstrip().startswith(
            ("except", "finally", "else")
        ):
            break
        j += 1
    patch = [
        f"{indent}except Exception as _lux_orphan_try:",
        f"{indent}    pass  # repaired orphan try (bad inject)",
    ]
    print(f"INSERTED_EXCEPT for try at line {try_i + 1} before line {j + 1}")
    return "\n".join(lines[:j] + patch + lines[j:]) + (
        "\n" if text.endswith("\n") else ""
    )


def repair() -> dict:
    path = _find()
    src = path.read_text(encoding="utf-8", errors="ignore")
    bak = path.with_suffix(path.suffix + f".bak_syntax_{int(time.time())}")
    shutil.copy2(path, bak)
    report: dict = {"file": str(path), "backup": str(bak), "actions": []}

    err = _parse(src)
    if err is None:
        report["actions"].append("already_valid")
    else:
        _show(err, src)
        # Prefer restore from known-good backup
        restored = False
        for c in _backup_candidates(path):
            if c.resolve() == bak.resolve():
                continue
            try:
                t = c.read_text(encoding="utf-8", errors="ignore")
                if _parse(t) is not None:
                    continue
            except Exception:
                continue
            path.write_text(t, encoding="utf-8")
            report["actions"].append(f"restored_from:{c}")
            src = t
            restored = True
            break

        if not restored:
            text = _strip_reharden_blocks(src)
            report["actions"].append("stripped_reharden_blocks")
            err2 = _parse(text)
            if err2 is not None:
                text = _close_orphan_try(text, err2)
                report["actions"].append("closed_orphan_try")
            err3 = _parse(text)
            if err3 is not None:
                _show(err3, text)
                raise SystemExit(f"UNREPAIRED:{err3.lineno}:{err3.msg}")
            path.write_text(text, encoding="utf-8")
            src = text
            report["actions"].append("surgical_ok")

    # Ensure safe EOF reharden (and remove mid-file copies first)
    src = path.read_text(encoding="utf-8", errors="ignore")
    src2 = _strip_reharden_blocks(src)
    if "import lux_re_harden" not in src2:
        src2 = src2.rstrip() + EOF_BLOCK
        report["actions"].append("appended_reharden_eof")
    else:
        report["actions"].append("reharden_still_present_after_strip")
    errf = _parse(src2)
    if errf is not None:
        _show(errf, src2)
        raise SystemExit(f"FINAL_PARSE_FAIL:{errf.lineno}:{errf.msg}")
    path.write_text(src2 if src2.endswith("\n") else src2 + "\n", encoding="utf-8")
    report["actions"].append("parse_ok")
    return report


if __name__ == "__main__":
    print(repair())
