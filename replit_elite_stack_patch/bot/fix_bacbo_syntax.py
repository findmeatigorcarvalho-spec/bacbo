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

EOF_SCB = """

# --- LUXURY_SEND_CONFIG_BIND (auto) ---
try:
    import lux_send_config_bind  # noqa: F401
    print("[LUXURY] send-config-bind loaded")
except Exception as _lux_scb_exc:
    print("[LUXURY] send-config-bind skipped:", _lux_scb_exc)
# --- end LUXURY_SEND_CONFIG_BIND ---
"""

EOF_REHARDEN = """

# --- lux_re_harden (safe EOF inject; do not move inside try) ---
try:
    import lux_re_harden  # noqa: F401
    print("[LUXURY] re-harden loaded")
except Exception as _lux_reh_exc:
    print("[LUXURY] re-harden skipped:", _lux_reh_exc)
# --- end lux_re_harden ---
"""

# Back-compat alias
EOF_BLOCK = EOF_REHARDEN


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


def _fix_nested_reharden_inside_scb(text: str) -> tuple[str, bool]:
    """Fix reharden injected inside send-config-bind try (user paste ~725).

    Line-based (tolerant of blank lines / CRLF) — regex kept missing this.
    """
    # Normalize newlines for matching; restore \n on write.
    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.splitlines(keepends=True)

    def _strip(i: int) -> str:
        return lines[i].strip()

    start = None
    for i, ln in enumerate(lines):
        if "LUXURY_SEND_CONFIG_BIND (auto)" in ln:
            start = i
            break
    if start is None:
        return text, False

    # Expect: start, try:, import lux_send..., print loaded, [blanks], try: reharden...
    i = start + 1
    while i < len(lines) and not _strip(i):
        i += 1
    if i >= len(lines) or _strip(i) != "try:":
        return text, False
    try_scb = i
    i += 1
    # collect body until a nested bare `try:` (reharden) or except
    body_idxs: list[int] = []
    reharden_try = None
    while i < len(lines):
        s = _strip(i)
        if s == "try:" and any(
            "lux_re_harden" in _strip(j)
            for j in range(i + 1, min(i + 4, len(lines)))
        ):
            reharden_try = i
            break
        if s.startswith("except Exception as _lux_scb_exc"):
            # already correct structure
            return text, False
        if s.startswith("# --- end LUXURY_SEND_CONFIG_BIND"):
            return text, False
        body_idxs.append(i)
        i += 1
    if reharden_try is None:
        return text, False

    # Walk reharden try/except block
    i = reharden_try + 1
    while i < len(lines) and (
        not _strip(i)
        or _strip(i).startswith("import lux_re_harden")
        or "re-harden loaded" in _strip(i)
        or _strip(i).startswith("except Exception as _lux_reh_exc")
        or "re-harden skipped" in _strip(i)
    ):
        i += 1
        # stop when we hit scb except
        if i < len(lines) and _strip(i).startswith("except Exception as _lux_scb_exc"):
            break
    if i >= len(lines) or not _strip(i).startswith("except Exception as _lux_scb_exc"):
        # maybe reharden except then scb except — advance past reharden except body
        while i < len(lines) and not _strip(i).startswith("except Exception as _lux_scb_exc"):
            i += 1
    if i >= len(lines) or not _strip(i).startswith("except Exception as _lux_scb_exc"):
        return text, False
    scb_except_start = i
    i += 1
    while i < len(lines):
        s = _strip(i)
        if s.startswith("# --- end LUXURY_SEND_CONFIG_BIND"):
            break
        if s.startswith("# ---") and "LUXURY" in s:
            break
        i += 1
    if i >= len(lines) or "end LUXURY_SEND_CONFIG_BIND" not in _strip(i):
        return text, False
    end_idx = i

    # Rebuild: scb try + body + scb except + end, then reharden block after
    out: list[str] = []
    out.extend(lines[: start + 1])  # through marker
    # keep blank lines between marker and try if any
    out.extend(lines[start + 1 : try_scb])
    out.append(lines[try_scb])  # try:
    for bi in body_idxs:
        # skip blank-only lines that were between body and nested try? keep non-empty body
        if _strip(bi) or True:
            # drop trailing blanks from body (they sat before nested try)
            pass
    # body without trailing blank lines
    body_lines = [lines[bi] for bi in body_idxs]
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    out.extend(body_lines)
    out.extend(lines[scb_except_start:end_idx + 1])
    out.append("\n")
    out.append("# --- lux_re_harden (moved out of send-config-bind try) ---\n")
    out.append("try:\n")
    out.append("    import lux_re_harden  # noqa: F401\n")
    out.append('    print("[LUXURY] re-harden loaded")\n')
    out.append("except Exception as _lux_reh_exc:\n")
    out.append('    print("[LUXURY] re-harden skipped:", _lux_reh_exc)\n')
    out.append("# --- end lux_re_harden ---\n")
    out.extend(lines[end_idx + 1 :])
    new = "".join(out)
    if _parse(new) is not None:
        return text, False
    return new, True


def _strip_reharden_blocks(text: str) -> str:
    """Remove prior lux_re_harden injects so we can re-append at EOF safely."""
    text2, fixed = _fix_nested_reharden_inside_scb(text)
    if fixed:
        return text2
    # Multiline try/import lux_re_harden/except blocks (standalone)
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
    text2 = re.sub(
        r"\n# --- lux_re_harden[^\n]*---\n"
        r"[\s\S]*?"
        r"# --- end lux_re_harden ---\n?",
        "\n",
        text2,
    )
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
        # Fast path: do NOT regex-strip the 2.5MB megafile (hangs Replit).
        # Only ensure pre-main ESTUDO gate + missing EOF binds.
        src2 = src
        if "import lux_send_config_bind" not in src2:
            src2 = src2.rstrip() + EOF_SCB
            report["actions"].append("appended_send_config_bind_eof")
        if "import lux_re_harden" not in src2:
            src2 = src2.rstrip() + EOF_REHARDEN
            report["actions"].append("appended_reharden_eof")
        src3 = _ensure_scb_before_main(src2, report)
        if src3 != src:
            errm = _parse(src3)
            if errm is not None:
                _show(errm, src3)
                raise SystemExit(f"PREMAIN_PARSE_FAIL:{errm.lineno}:{errm.msg}")
            path.write_text(src3 if src3.endswith("\n") else src3 + "\n", encoding="utf-8")
        report["actions"].append("parse_ok")
        print("[fix_bacbo_syntax]", report)
        return report

    _show(err, src)
    # 1) Exact known damage: reharden nested inside send-config-bind try
    text, nested_fixed = _fix_nested_reharden_inside_scb(src)
    if nested_fixed and _parse(text) is None:
        path.write_text(text, encoding="utf-8")
        src = text
        report["actions"].append("fixed_nested_reharden_in_scb")
    else:
        # 2) Prefer restore from known-good backup
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

    # Broken-file path: strip + ensure EOF binds (strip only when needed)
    src = path.read_text(encoding="utf-8", errors="ignore")
    src2 = _strip_reharden_blocks(src)
    if "import lux_send_config_bind" not in src2:
        src2 = src2.rstrip() + EOF_SCB
        report["actions"].append("appended_send_config_bind_eof")
    else:
        report["actions"].append("send_config_bind_present")
    if "import lux_re_harden" not in src2:
        src2 = src2.rstrip() + EOF_REHARDEN
        report["actions"].append("appended_reharden_eof")
    else:
        report["actions"].append("reharden_still_present_after_strip")
    errf = _parse(src2)
    if errf is not None:
        _show(errf, src2)
        raise SystemExit(f"FINAL_PARSE_FAIL:{errf.lineno}:{errf.msg}")
    path.write_text(src2 if src2.endswith("\n") else src2 + "\n", encoding="utf-8")
    src3 = _ensure_scb_before_main(
        path.read_text(encoding="utf-8", errors="ignore"), report
    )
    errm = _parse(src3)
    if errm is not None:
        _show(errm, src3)
        raise SystemExit(f"PREMAIN_PARSE_FAIL:{errm.lineno}:{errm.msg}")
    path.write_text(src3 if src3.endswith("\n") else src3 + "\n", encoding="utf-8")
    report["actions"].append("parse_ok")
    print("[fix_bacbo_syntax]", report)
    return report


def _ensure_scb_before_main(src: str, report: dict) -> str:
    """Duplicate ESTUDO gate import before blocking if __name__ / asyncio.run."""
    lines = src.splitlines(keepends=True)
    main_i = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("if __name__") and "__main__" in s:
            main_i = i
            break
    if main_i is None:
        for i, ln in enumerate(lines):
            if ln.startswith("asyncio.run(") or ln.startswith(
                "asyncio.get_event_loop().run_until_complete"
            ):
                main_i = i
        if main_i is None:
            report.setdefault("actions", []).append("no_main_block_found")
            return src
    pre = "".join(lines[:main_i])
    if "import lux_estudo_kill" in pre or "send-config-bind loaded (pre-main)" in pre:
        report.setdefault("actions", []).append("scb_already_before_main")
        return src
    early = """
# --- LUXURY_SEND_CONFIG_BIND (pre-main; must run before asyncio.run) ---
try:
    import lux_estudo_kill  # noqa: F401
    import lux_send_config_bind  # noqa: F401
    print("[LUXURY] send-config-bind loaded (pre-main)")
except Exception as _lux_scb_exc:
    print("[LUXURY] send-config-bind skipped:", _lux_scb_exc)
# --- end LUXURY_SEND_CONFIG_BIND pre-main ---

"""
    lines.insert(main_i, early)
    report.setdefault("actions", []).append("scb_injected_before_main")
    return "".join(lines)


if __name__ == "__main__":
    print(repair())
