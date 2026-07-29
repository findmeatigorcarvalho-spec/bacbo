#!/usr/bin/env python3
"""Fix NameError: name 'state' is not defined in bacbo_royal_complete.py.

A prior luxury patch left bare `state.client = TelegramClient(...)` without binding
the module name `state`. Rewrite that assign to import state as module + alias.
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


def apply(root: Path | None = None) -> dict:
    root = root or Path("/home/runner/workspace")
    if not (root / "bacbo_royal_complete.py").exists() and (Path.cwd() / "bacbo_royal_complete.py").exists():
        root = Path.cwd()
    path = _find_bacbo(root)
    if path is None:
        raise SystemExit("bacbo_royal_complete.py not found")

    src = path.read_text(encoding="utf-8", errors="replace")
    original = src
    changed = []

    # Strip old bind / force blocks so we can re-insert cleanly
    src = re.sub(
        r"\n?# --- LUXURY_SESSION_AND_BIND \(auto\) ---.*?--- end LUXURY_SESSION_AND_BIND ---\n?",
        "\n",
        src,
        flags=re.S,
    )
    src = re.sub(
        r"\n?# --- LUXURY_STATE_NAME_FORCE \(auto\) ---.*?--- end LUXURY_STATE_NAME_FORCE ---\n?",
        "\n",
        src,
        flags=re.S,
    )
    # Also strip the broken bare assign left by FIX_HARD strip
    m = re.search(
        r"^state\.client\s*=\s*(TelegramClient\([^\n]*\))\s*$",
        src,
        re.M,
    )
    if not m:
        # maybe already using _lux_state_mod.client =
        if "state = _lux_state_mod" in src and "_lux_state_mod.client = TelegramClient" in src:
            ast.parse(src)
            print("[fix_bacbo_state] already OK", path)
            return {"path": str(path), "changed": False, "reason": "already_bound"}
        raise SystemExit(
            "cannot find state.client = TelegramClient(...) — inspect bacbo around line 146"
        )

    ctor = m.group(1)
    bind = BIND.format(CTOR=ctor)
    src = src[: m.start()] + bind + "\n" + src[m.end() :]
    changed.append("session_and_bind")

    # Belt+suspenders before first state.engine =
    if re.search(r"^state\.engine\s*=", src, re.M):
        src = re.sub(
            r"^(state\.engine\s*=)",
            FORCE + r"\1",
            src,
            count=1,
            flags=re.M,
        )
        changed.append("state_name_force")

    # Ensure `import state` exists early (module must exist as bot/state.py or state.py)
    if not re.search(r"^(import state\b|from state import\b)", src, re.M):
        # insert after imports OK boot marker or near top
        lines = src.splitlines(True)
        idx = 0
        for i, ln in enumerate(lines):
            if "[BOOT] all imports OK" in ln or "[BOOT] telethon imports OK" in ln:
                idx = i + 1
                break
        lines.insert(idx, "import state  # LUXURY: module must exist before client bind\n")
        src = "".join(lines)
        changed.append("import_state")

    ast.parse(src)
    if "state = _lux_state_mod" not in src:
        raise SystemExit("state = _lux_state_mod missing after patch")

    bak = path.with_suffix(path.suffix + ".bak_pre_state_fix")
    if not bak.exists():
        bak.write_text(original, encoding="utf-8")
    if src != original:
        path.write_text(src, encoding="utf-8")

    # Verify state module importable
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "bot"))
    try:
        if "state" in sys.modules:
            del sys.modules["state"]
        import state as st  # noqa: F401

        state_file = getattr(st, "__file__", "?")
    except Exception as exc:
        print("[fix_bacbo_state] WARN: import state failed:", repr(exc))
        state_file = None

    out = {
        "path": str(path),
        "changed": changed,
        "bytes": path.stat().st_size,
        "state_module": state_file,
        "has_bind": "LUXURY_SESSION_AND_BIND" in path.read_text(encoding="utf-8", errors="replace"),
    }
    print("[fix_bacbo_state]", out)
    return out


if __name__ == "__main__":
    apply()
