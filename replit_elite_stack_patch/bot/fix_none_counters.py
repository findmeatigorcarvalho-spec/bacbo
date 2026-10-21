"""Stop session counters being None forever.

state.py initialises the session counters to None, and main.py restores them
with ``_brain.get("session_wins", 0)``. That default only applies when the key
is missing; the brain state saved to the DB contains explicit nulls, so every
boot restores None, arithmetic/comparisons on the counters raise TypeError,
and shutdown saves the nulls back again.

This patch makes the defaults 0 in state.py and coerces restored values with
``or 0`` in main.py, which breaks the cycle. Card logic is untouched.

Usage:
    python fix_none_counters.py --install
"""
import ast
import re
import sys
from pathlib import Path

COUNTERS = ("wins", "losses", "ties", "g0_wins", "g1_wins", "g2_wins")
BRAIN_KEYS = ("session_wins", "session_losses", "session_ties",
              "session_g0", "session_g1", "session_g2")

_STATE_NONE_RE = re.compile(
    r"^(_session_(?:wins|losses|ties|g0_wins|g1_wins|g2_wins)[ \t]*=[ \t]*)None[ \t]*$",
    re.M,
)


def patch_state(text):
    return _STATE_NONE_RE.sub(r"\g<1>0", text)


def patch_main(text):
    for key in BRAIN_KEYS:
        text = re.sub(
            r"""_brain\.get\((['"])""" + key + r"""\1[ \t]*,[ \t]*0\)""",
            '(_brain.get("%s") or 0)' % key,
            text,
        )
    return text


def _apply(path, patcher, label):
    if not path.is_file():
        return "%s not found: %s" % (label, path)
    src = path.read_text(encoding="utf-8")
    new = patcher(src)
    if new == src:
        return "%s: already fixed" % label
    ast.parse(new)
    bak = Path(str(path) + ".bak_none_counters")
    if not bak.exists():
        bak.write_text(src, encoding="utf-8")
    path.write_text(new, encoding="utf-8")
    return "%s: patched (backup %s)" % (label, bak.name)


def install(bot_dir):
    bot_dir = Path(bot_dir)
    return [
        _apply(bot_dir / "state.py", patch_state, "state.py"),
        _apply(bot_dir / "main.py", patch_main, "main.py"),
    ]


if __name__ == "__main__":
    if "--install" in sys.argv:
        for line in install(Path(__file__).resolve().parent):
            print(line)
    else:
        print(__doc__)
