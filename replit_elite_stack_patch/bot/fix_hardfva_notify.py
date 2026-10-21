"""Fix [HardFVANotify] '>' not supported between 'NoneType' and 'int'.

background.py periodic_hard_fva_notify() reads state._hard_fva_blocked_wall,
which is None until the first HardFVA block happens, then compares it with
``> 0`` — raising TypeError every 15s cycle (caught, logged, retried forever).

The patch coerces the value to 0.0 at read time. It also makes the
[SelfHealer] loop-error log include a traceback so the remaining
'<' not supported between 'NoneType' and 'int' error names its exact line
instead of hiding it.

Usage:
    python fix_hardfva_notify.py --install   # takes effect on next bot start
"""
import ast
import re
import sys
from pathlib import Path

_BG_OLD_RE = re.compile(r"(_block_wall[ \t]*=[ \t]*state\._hard_fva_blocked_wall)(?![ \t]+or\b)")
_SH_OLD = 'log.error(f"[SelfHealer] Loop error (continuing): {exc}")'
_SH_NEW = 'log.error(f"[SelfHealer] Loop error (continuing): {exc}", exc_info=True)'


def patch_background(text):
    return _BG_OLD_RE.sub(r"\g<1> or 0.0", text)


def patch_self_healer(text):
    return text.replace(_SH_OLD, _SH_NEW)


def _apply(path, patcher, label):
    if not path.is_file():
        return "%s not found: %s" % (label, path)
    src = path.read_text(encoding="utf-8")
    new = patcher(src)
    if new == src:
        return "%s: already fixed" % label
    ast.parse(new)
    bak = Path(str(path) + ".bak_hardfva")
    if not bak.exists():
        bak.write_text(src, encoding="utf-8")
    path.write_text(new, encoding="utf-8")
    return "%s: patched (backup %s)" % (label, bak.name)


def install(bot_dir):
    bot_dir = Path(bot_dir)
    return [
        _apply(bot_dir / "background.py", patch_background, "background.py"),
        _apply(bot_dir / "self_healer.py", patch_self_healer, "self_healer.py"),
    ]


if __name__ == "__main__":
    if "--install" in sys.argv:
        for line in install(Path(__file__).resolve().parent):
            print(line)
    else:
        print(__doc__)
