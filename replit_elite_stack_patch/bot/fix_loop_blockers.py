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

This installer patches perfect_g0_finder.py: every mine_perfect_cells() call
site that sits inside an async function is rewritten, by line, to
await asyncio.to_thread(...) (AST-located, compile-validated; call sites in
sync functions are left untouched and reported). For background.py's health
monitor it does NOT guess: it prints the whole periodic_signal_health_monitor
function so the offload patch for it can be written against the real code —
paste that back.

Usage:
    python fix_loop_blockers.py --install   # takes effect on next start
"""
import ast
import re
import sys
from pathlib import Path

_CALL = "mine_perfect_cells()"


def _call_sites(text):
    """(async_lines, sync_lines): 1-based lines calling mine_perfect_cells()."""
    tree = ast.parse(text)
    async_lines, sync_lines = set(), set()

    def visit(node, in_async):
        for child in ast.iter_child_nodes(node):
            now_async = in_async or isinstance(child, ast.AsyncFunctionDef)
            if (isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                    and child.func.id == "mine_perfect_cells"):
                (async_lines if now_async else sync_lines).add(child.lineno)
            visit(child, now_async)

    visit(tree, False)
    return sorted(async_lines), sorted(sync_lines)


def patch_perfect_g0(text):
    if not re.search(r"^import asyncio\b", text, re.M):
        raise ValueError("asyncio not imported in perfect_g0_finder.py - not patching blind")
    async_lines, sync_lines = _call_sites(text)
    if not async_lines and not sync_lines:
        if "asyncio.to_thread(mine_perfect_cells)" in text:
            return text  # already patched
        raise ValueError("no mine_perfect_cells() call sites found")
    lines = text.splitlines(keepends=True)
    patched = 0
    for lineno in async_lines:
        line = lines[lineno - 1]
        if "asyncio.to_thread(mine_perfect_cells)" in line:
            continue
        if _CALL not in line:
            raise ValueError("call site line %d does not contain %r - layout changed" % (lineno, _CALL))
        lines[lineno - 1] = line.replace(
            _CALL, "await asyncio.to_thread(mine_perfect_cells)", 1)
        patched += 1
    new = "".join(lines)
    ast.parse(new)
    if sync_lines:
        print("note: left %d sync-context call site(s) untouched at line(s) %s"
              % (len(sync_lines), sync_lines))
    if patched == 0 and "asyncio.to_thread(mine_perfect_cells)" not in new:
        raise ValueError("nothing patched (async sites: %s, sync sites: %s)" % (async_lines, sync_lines))
    return new


def health_monitor_snippet(text, max_lines=220):
    """The full periodic_signal_health_monitor function, numbered."""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if "def periodic_signal_health_monitor" in ln:
            start = i
            break
    if start is None:
        return None
    end = min(len(lines), start + max_lines)
    for j in range(start + 1, end):
        if re.match(r"^(async def|def|class)\s", lines[j]):
            end = j
            break
    return "\n".join("%d: %s" % (k + 1, lines[k]) for k in range(start, end))


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
