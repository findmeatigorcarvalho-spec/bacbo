"""Wire lux_no_hour_blocks into main.py so hour/DOW blocks stay dead 24/7.

main.py currently relies on the boot-time HourAdvisory, which empties the
hour/DOW constants once at startup. lux_no_hour_blocks does that too, but
also: no-ops the auditors that re-learn bad hours, empties the persisted
JSON (accuracy_blocks.json blocked_hours etc.), and re-sweeps every 20s
for the life of the process. Importing it once near the top of main.py
(after the regular imports, before the _gates_* floors load) is enough -
its import hook sweeps gate modules as they are imported later.

Idempotent. Takes effect on next bot start.

Usage:
    python fix_wire_hour_blocks.py --install
"""
import ast
import sys
from pathlib import Path

HOOK = (
    "try:\n"
    "    import lux_no_hour_blocks  # noqa: F401  (24/7: hour/DOW blocks stay empty)\n"
    "except Exception:\n"
    "    pass\n"
)


def patch_main(text):
    if "lux_no_hour_blocks" in text:
        return text
    lines = text.splitlines(keepends=True)
    last_import = -1
    for i, ln in enumerate(lines[:200]):
        s = ln.strip()
        if s.startswith("import ") or s.startswith("from "):
            last_import = i
    if last_import < 0:
        raise ValueError("no import lines found in first 200 lines of main.py")
    lines.insert(last_import + 1, HOOK)
    return "".join(lines)


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
    ast.parse(new)
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
