"""Move the LoopLag-named synchronous DB miners off the event loop.

[LoopLag] stacks on 2026-10-21 caught the main thread inside:

    perfect_g0_finder.py:292 periodic_mining_task -> mine_perfect_cells()
        rows = c.execute(q_full, ...)          # blocked 54s, then 114s+
    background.py:2343 periodic_signal_health_monitor -> _db.execute(...)

mine_perfect_cells() is a synchronous full-window mine over the big tables;
called bare from an async periodic task it freezes Telegram handlers, sends
and watchdogs for minutes — the same failure that refresh_all_room_dna had.
Running it with asyncio.to_thread keeps the loop responsive (sqlite
connections in this codebase are thread-local, so the worker gets its own).

This installer patches perfect_g0_finder.py (exact call-site anchor, AST
validated). For background.py's health monitor it does NOT guess: it prints
the lines around the first _db.execute in periodic_signal_health_monitor so
the offload patch for it can be written against the real code — paste that
snippet back.

Usage:
    python fix_loop_blockers.py --install   # takes effect on next start
"""
import ast
import re
import sys
from pathlib import Path

_CALL_RE = re.compile(r"^([ \t]*)summary = mine_perfect_cells\(\)[ \t]*$", re.M)


def patch_perfect_g0(text):
    if "await asyncio.to_thread(mine_perfect_cells)" in text:
        return text
    tree = ast.parse(text)
    async_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                        and sub.func.id == "mine_perfect_cells"):
                    async_fn = node.name
    if async_fn is None:
        raise ValueError("mine_perfect_cells() is not called from any async function")
    if not re.search(r"^import asyncio\b", text, re.M):
        raise ValueError("asyncio not imported in perfect_g0_finder.py - not patching blind")
    new, n = _CALL_RE.subn(r"\g<1>summary = await asyncio.to_thread(mine_perfect_cells)", text)
    if n != 1:
        raise ValueError("expected exactly one 'summary = mine_perfect_cells()' call, found %d" % n)
    ast.parse(new)
    return new


def health_monitor_snippet(text, context=18):
    """Lines around the first _db.execute inside periodic_signal_health_monitor."""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if "def periodic_signal_health_monitor" in ln:
            start = i
            break
    if start is None:
        return None
    for j in range(start, min(len(lines), start + 400)):
        if "_db.execute" in lines[j] or ".execute(" in lines[j]:
            lo = max(start, j - 4)
            hi = min(len(lines), j + context)
            return "\n".join("%d: %s" % (k + 1, lines[k]) for k in range(lo, hi))
    return "\n".join("%d: %s" % (k + 1, lines[k]) for k in range(start, min(len(lines), start + 30)))


def install(bot_dir):
    bot_dir = Path(bot_dir)
    out = []
    path = bot_dir / "perfect_g0_finder.py"
    if not path.is_file():
        out.append("perfect_g0_finder.py not found: %s" % path)
    else:
        src = path.read_text(encoding="utf-8")
        try:
            new = patch_perfect_g0(src)
        except ValueError as exc:
            out.append("perfect_g0_finder.py: NOT patched (%s)" % exc)
        else:
            if new == src:
                out.append("perfect_g0_finder.py: already fixed")
            else:
                bak = Path(str(path) + ".bak_loopblock")
                if not bak.exists():
                    bak.write_text(src, encoding="utf-8")
                path.write_text(new, encoding="utf-8")
                out.append("perfect_g0_finder.py: patched - mine_perfect_cells now runs "
                           "in a worker thread (backup %s)" % bak.name)
    bg = bot_dir / "background.py"
    if bg.is_file():
        snippet = health_monitor_snippet(bg.read_text(encoding="utf-8", errors="ignore"))
        if snippet:
            out.append("background.py periodic_signal_health_monitor (for the next patch - paste this back):\n" + snippet)
    return "\n".join(out)


if __name__ == "__main__":
    if "--install" in sys.argv:
        print(install(Path(__file__).resolve().parent))
    else:
        print(__doc__)
