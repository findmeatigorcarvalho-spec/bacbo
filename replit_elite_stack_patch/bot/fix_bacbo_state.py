#!/usr/bin/env python3
"""Fix NameError: name 'state' is not defined in bacbo_royal_complete.py.

Handles several shapes left by prior luxury patches:
  - bare:  state.client = TelegramClient(...)
  - mod:   _lux_state_mod.client = TelegramClient(...)
  - bind block present but missing `state = _lux_state_mod`
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


BIND = '''# --- LUXURY_SESSION_AND_BIND (auto) ---
try:
    import os as _lux_os
    from pathlib import Path as _LuxPath
    _sf = _LuxPath("/home/runner/workspace/.telegram_session_string")
    if _sf.exists():
        _sv = _sf.read_text(errors="ignore").strip()
        if len(_sv) > 50:
            _lux_os.environ["TELEGRAM_SESSION_STRING"] = _sv
            try:
                from telethon.sessions import StringSession as _LuxSS
                _session = _LuxSS(_sv)
            except Exception:
                pass
except Exception as _lux_sess_exc:
    print("[LUXURY] session force skipped:", _lux_sess_exc)

import state as _lux_state_mod
_lux_prev_client = getattr(_lux_state_mod, "client", None)
_lux_state_mod.client = {CTOR}
try:
    if hasattr(_lux_prev_client, "bind"):
        _lux_prev_client.bind(_lux_state_mod.client)
except Exception as _lux_bind_exc:
    print("[LUXURY] proxy bind failed:", _lux_bind_exc)
# Critical: bare `state.*` lines below need this name
state = _lux_state_mod
# --- end LUXURY_SESSION_AND_BIND ---
'''

FORCE = '''# --- LUXURY_STATE_NAME_FORCE (auto) ---
import state as _lux_state_mod
state = _lux_state_mod
# --- end LUXURY_STATE_NAME_FORCE ---
'''


def _find_bacbo(root: Path) -> Path | None:
    for rel in ("bacbo_royal_complete.py", "bacbo.py", "bot/bacbo_royal_complete.py"):
        p = root / rel
        if p.exists():
            return p
    return None


def _dump_context(src: str, around: int = 146, radius: int = 25) -> None:
    try:
        lines = src.splitlines()
        a = max(0, around - radius - 1)
        b = min(len(lines), around + radius)
        print(f"----- bacbo lines {a+1}-{b} -----")
        for i in range(a, b):
            print(f"{i+1}: {lines[i][:160]}")
    except Exception as exc:
        print("[fix_bacbo_state] dump skipped:", repr(exc))


def _find_ctor(src: str) -> tuple[re.Match[str] | None, str]:
    """Return (match, ctor_call) for the TelegramClient assignment."""
    patterns = [
        r"^state\.client\s*=\s*(TelegramClient\([^\n]*\))\s*$",
        r"^_lux_state_mod\.client\s*=\s*(TelegramClient\([^\n]*\))\s*$",
        r"^(?:state|_lux_state_mod)\.client\s*=\s*(TelegramClient\([^\n]*\))\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, src, re.M)
        if m:
            return m, m.group(1)
    # looser: any line with TelegramClient( near client assign in first 400 lines
    lines = src.splitlines()
    for i, ln in enumerate(lines[:400]):
        if "TelegramClient(" in ln and "client" in ln:
            m2 = re.search(r"(TelegramClient\(.+\))", ln)
            if m2:
                # synthesize a match-like span for replacement of whole line
                start = sum(len(x) + 1 for x in lines[:i])
                end = start + len(ln)
                class _M:
                    def start(self_):  # noqa: N805
                        return start

                    def end(self_):  # noqa: N805
                        return end

                return _M(), m2.group(1)
    return None, ""


def apply(root: Path | None = None) -> dict:
    root = root or Path("/home/runner/workspace")
    if not (root / "bacbo_royal_complete.py").exists() and (Path.cwd() / "bacbo_royal_complete.py").exists():
        root = Path.cwd()
    path = _find_bacbo(root)
    if path is None:
        raise SystemExit("bacbo_royal_complete.py not found")

    src = path.read_text(encoding="utf-8", errors="replace")
    original = src
    changed: list[str] = []

    # Ensure bot/state.py exists (import state as _lux_state_mod needs it)
    state_py = root / "bot" / "state.py"
    if not state_py.is_file():
        state_py.parent.mkdir(parents=True, exist_ok=True)
        # Prefer repo template if present next to this fixer
        here = Path(__file__).resolve().parent / "state.py"
        if here.is_file():
            state_py.write_text(here.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            state_py.write_text(
                "client = None\nme = None\nrunning = True\nengine = None\n",
                encoding="utf-8",
            )
        print("[fix_bacbo_state] wrote missing", state_py)
        changed.append("wrote_state_py")

    # Already healthy? Must have bind BEFORE first bare state.client use.
    first_client = None
    for i, ln in enumerate(src.splitlines()):
        if re.search(r"^(state|_lux_state_mod)\.client\s*=\s*TelegramClient\(", ln):
            first_client = i
            break
    bind_ok = False
    if first_client is not None and "state = _lux_state_mod" in src:
        pre = "\n".join(src.splitlines()[:first_client])
        bind_ok = "state = _lux_state_mod" in pre or "LUXURY_SESSION_AND_BIND" in pre

    if (
        bind_ok
        and re.search(r"(state|_lux_state_mod)\.client\s*=\s*TelegramClient\(", src)
        and "LUXURY_SESSION_AND_BIND" in src
    ):
        # Ensure force before state.engine
        if re.search(r"^state\.engine\s*=", src, re.M) and "LUXURY_STATE_NAME_FORCE" not in src:
            src = re.sub(
                r"^(state\.engine\s*=)",
                FORCE + r"\1",
                src,
                count=1,
                flags=re.M,
            )
            changed.append("state_name_force_only")
            ast.parse(src)
            path.write_text(src, encoding="utf-8")
            print("[fix_bacbo_state] force before engine", path)
            return {"path": str(path), "changed": changed, "reason": "force_only"}
        print("[fix_bacbo_state] already OK", path)
        return {"path": str(path), "changed": False, "reason": "already_bound"}

    if first_client is not None and not bind_ok:
        print(
            f"[fix_bacbo_state] state unbound before client assign at line {first_client + 1}"
        )
        _dump_context(src, around=first_client + 1)

    # Extract ctor BEFORE stripping bind block (bind may hold the only TelegramClient line)
    m_pre, ctor = _find_ctor(src)
    if not ctor:
        # try inside existing bind without stripping
        m_in = re.search(
            r"_lux_state_mod\.client\s*=\s*(TelegramClient\([^\n]*\))",
            src,
        )
        if m_in:
            ctor = m_in.group(1)
            m_pre = m_in

    if not ctor:
        print("[fix_bacbo_state] FAIL: no TelegramClient assign found")
        _dump_context(src, around=146)
        # also print every TelegramClient mention in first 250 lines
        print("----- TelegramClient mentions (first 250 lines) -----")
        for i, ln in enumerate(src.splitlines()[:250]):
            if "TelegramClient" in ln or "state.client" in ln or "_lux_state_mod" in ln:
                print(f"{i+1}: {ln[:160]}")
        raise SystemExit("cannot find TelegramClient client assign — paste the dump above")

    # Remove old bind/force, then insert a clean bind at the client assign site
    src2 = re.sub(
        r"\n?# --- LUXURY_SESSION_AND_BIND \(auto\) ---.*?--- end LUXURY_SESSION_AND_BIND ---\n?",
        "\n",
        src,
        flags=re.S,
    )
    src2 = re.sub(
        r"\n?# --- LUXURY_STATE_NAME_FORCE \(auto\) ---.*?--- end LUXURY_STATE_NAME_FORCE ---\n?",
        "\n",
        src2,
        flags=re.S,
    )

    m, ctor2 = _find_ctor(src2)
    if ctor2:
        ctor = ctor2
        m_use = m
    else:
        # stripped the only assign — insert bind near former location / after session load
        m_use = None

    bind = BIND.format(CTOR=ctor)
    if m_use is not None:
        src2 = src2[: m_use.start()] + bind + "\n" + src2[m_use.end() :]
        changed.append("session_and_bind_replace")
    else:
        # insert after "[BOOT] all imports OK" or before first state. usage
        lines = src2.splitlines(True)
        idx = 0
        for i, ln in enumerate(lines):
            if "[BOOT] all imports OK" in ln or "[Session] Loaded" in ln or "StringSession" in ln:
                idx = i + 1
        if idx == 0:
            idx = min(80, len(lines))
        lines.insert(idx, "\n" + bind + "\n")
        src2 = "".join(lines)
        changed.append("session_and_bind_insert")

    if re.search(r"^state\.engine\s*=", src2, re.M):
        if "LUXURY_STATE_NAME_FORCE" not in src2:
            src2 = re.sub(
                r"^(state\.engine\s*=)",
                FORCE + r"\1",
                src2,
                count=1,
                flags=re.M,
            )
            changed.append("state_name_force")

    if not re.search(r"^(import state\b|from state import\b|import state as )", src2, re.M):
        lines = src2.splitlines(True)
        idx = 0
        for i, ln in enumerate(lines):
            if "[BOOT] all imports OK" in ln or "[BOOT] telethon imports OK" in ln:
                idx = i + 1
                break
        lines.insert(idx, "import state  # LUXURY: module must exist before client bind\n")
        src2 = "".join(lines)
        changed.append("import_state")

    try:
        ast.parse(src2)
    except SyntaxError as exc:
        print("[fix_bacbo_state] SYNTAX after patch:", exc)
        _dump_context(src2, around=getattr(exc, "lineno", 146) or 146)
        raise SystemExit("syntax error after state patch") from exc

    if "state = _lux_state_mod" not in src2:
        raise SystemExit("state = _lux_state_mod missing after patch")

    bak = path.with_suffix(path.suffix + ".bak_pre_state_fix")
    if not bak.exists():
        bak.write_text(original, encoding="utf-8")
    if src2 != original:
        path.write_text(src2, encoding="utf-8")

    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "bot"))
    state_file = None
    try:
        if "state" in sys.modules:
            del sys.modules["state"]
        import state as st  # noqa: F401

        state_file = getattr(st, "__file__", "?")
    except Exception as exc:
        print("[fix_bacbo_state] WARN: import state failed:", repr(exc))

    out = {
        "path": str(path),
        "changed": changed,
        "ctor": ctor[:80],
        "bytes": path.stat().st_size,
        "state_module": state_file,
        "has_bind": "LUXURY_SESSION_AND_BIND" in path.read_text(encoding="utf-8", errors="replace"),
    }
    print("[fix_bacbo_state]", out)
    return out


if __name__ == "__main__":
    apply()
