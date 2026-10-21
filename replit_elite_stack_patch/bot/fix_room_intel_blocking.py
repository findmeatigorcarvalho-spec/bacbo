"""Stop the RoomIntel DNA sweep freezing the event loop.

periodic_room_intelligence_task() is async but calls the synchronous
refresh_all_room_dna() directly, so every ~20 min the whole bot (Telegram
handlers, sends, watchdogs) blocks while it mines channel_messages
(6.5M rows) room by room. py-spy showed MainThread inside that sweep's
sqlite execute in 3/3 samples.

Fix, in room_intelligence.py only:
  1. Run the sweep with asyncio.to_thread so the event loop stays
     responsive (database.get_conn() is thread-local, so the worker
     thread gets its own connection).
  2. Create composite indexes on channel_messages(sent_at, handle) and
     (handle, sent_at) before the sweep queries, inside the worker
     thread, so the GROUP BY and per-room lookups stop full-scanning.

No thresholds, card or routing logic is touched.

Usage:
    python fix_room_intel_blocking.py --install   # takes effect on next start
"""
import ast
import re
import sys
from pathlib import Path

_CALL_RE = re.compile(r"^([ \t]*)summary = refresh_all_room_dna\(\)[ \t]*$", re.M)
_ANCHOR = """    conn = database.get_conn()
    try:
        rows = conn.execute(\"\"\"
            SELECT handle, COUNT(*) AS n
"""
_INDEX_BLOCK = """    conn = database.get_conn()
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cm_sent_handle ON channel_messages(sent_at, handle)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cm_handle_sent ON channel_messages(handle, sent_at)")
        rows = conn.execute(\"\"\"
            SELECT handle, COUNT(*) AS n
"""


def patch_room_intelligence(text):
    if "await asyncio.to_thread(refresh_all_room_dna)" not in text:
        text, n = _CALL_RE.subn(r"\g<1>summary = await asyncio.to_thread(refresh_all_room_dna)", text)
        if n != 1:
            raise ValueError("expected exactly one 'summary = refresh_all_room_dna()' call, found %d" % n)
    if "idx_cm_handle_sent" not in text:
        if _ANCHOR not in text:
            raise ValueError("sweep query anchor not found in refresh_all_room_dna")
        text = text.replace(_ANCHOR, _INDEX_BLOCK, 1)
    return text


def install(bot_dir):
    path = Path(bot_dir) / "room_intelligence.py"
    if not path.is_file():
        return "room_intelligence.py not found: %s" % path
    src = path.read_text(encoding="utf-8")
    try:
        new = patch_room_intelligence(src)
    except ValueError as exc:
        return "room_intelligence.py: NOT patched (%s)" % exc
    if new == src:
        return "room_intelligence.py: already fixed"
    ast.parse(new)
    bak = Path(str(path) + ".bak_room_intel")
    if not bak.exists():
        bak.write_text(src, encoding="utf-8")
    path.write_text(new, encoding="utf-8")
    return "room_intelligence.py: patched (backup %s)" % bak.name


if __name__ == "__main__":
    if "--install" in sys.argv:
        print(install(Path(__file__).resolve().parent))
    else:
        print(__doc__)
