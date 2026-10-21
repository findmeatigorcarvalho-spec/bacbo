"""Wire lux_no_hour_blocks into main.py so hour/DOW blocks stay dead 24/7.

v2: the v1 installer inserted the hook after the last import line in the
first 200 lines, which could land inside a function/try block and corrupt
main.py ('return' outside function - ast.parse does not catch that, only
compile() does). v2 inserts at a top-level anchor instead: immediately
before the Hour-advisory layer block (all gate modules are already
imported by then, so the sweep sees them), and validates with compile().

If v1 already corrupted main.py, restore the backup first:
    cp main.py.bak_hourwire main.py

Idempotent. Takes effect on next bot start.

Usage:
    python fix_wire_hour_blocks.py --install
"""
import sys
from pathlib import Path

HOOK = (
    "try:\n"
    "    import lux_no_hour_blocks  # noqa: F401  (24/7: hour/DOW blocks stay empty)\n"
    "except Exception:\n"
    "    pass\n"
    "\n"
)

_ANCHORS = ("Hour-advisory layer", "Background task imports")


def patch_main(text):
    if "lux_no_hour_blocks" in text:
        return text
    lines = text.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if any(a in ln for a in _ANCHORS):
            lines.insert(i, HOOK)
            return "".join(lines)
    raise ValueError("no top-level anchor found (Hour-advisory / Background task imports)")


def install(bot_dir):
    path = Path(bot_dir) / "main.py"
    if not path.is_file():
        return "main.py not found: %s" % path
    src = path.read_text(encoding="utf-8")
    try:
        new = patch_main(src)
    except ValueError as exc:
        return "main.py: NOT patched (%s)" % exc
    if new == src:
        return "main.py: already wired"
    try:
        compile(new, str(path), "exec")
    except SyntaxError as exc:
        return "main.py: NOT patched (would not compile: %s)" % exc
    bak = Path(str(path) + ".bak_hourwire")
    if not bak.exists():
        bak.write_text(src, encoding="utf-8")
    path.write_text(new, encoding="utf-8")
    return "main.py: wired (backup %s)" % bak.name


if __name__ == "__main__":
    if "--install" in sys.argv:
        print(install(Path(__file__).resolve().parent))
    else:
        print(__doc__)
