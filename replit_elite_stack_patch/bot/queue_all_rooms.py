"""Queue every room in the DB for safe, no-block adding.

Two kinds of "adding" exist and they must not be confused:

  * Rooms the account already joined resolve from the session/dialog cache
    (nocache_peer) with ZERO username lookups — those come back instantly at
    boot and never risk a FloodWait.
  * Rooms the account has NOT joined need a real join, which is exactly what
    Telegram rate-limits (ResolveUsernameRequest was flood-blocked for
    7456s on 2026-10-20). Those must trickle through slow_join: one lookup,
    25-45 min gaps, <=6/day, hard stop on any FloodWait.

This tool only does the bookkeeping: it reads every room handle from the
rooms table in bacbo.db and merges the missing ones into
data/slow_join_targets.txt, which the already-running slow_join loop picks
up on its next cycle. It makes no Telegram requests and needs no restart.

Usage:
    python queue_all_rooms.py
"""
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "bacbo.db"
TARGETS = HERE / "data" / "slow_join_targets.txt"

_HANDLE_COLS = ("handle", "username", "user_name", "name", "room", "channel", "room_handle")


def _norm(h):
    h = str(h or "").strip().lstrip("@").lower()
    return h or None


def db_handles(db_path=DB):
    conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        if "rooms" not in tables:
            raise SystemExit("rooms table not found in %s" % db_path)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(rooms)")]
        col = next((c for c in _HANDLE_COLS if c in cols), None)
        if col is None:
            raise SystemExit("no handle-like column in rooms: %s" % cols)
        rows = conn.execute('SELECT DISTINCT "%s" FROM rooms' % col).fetchall()
    finally:
        conn.close()
    return sorted({h for h in (_norm(r[0]) for r in rows) if h})


def existing_targets(path=TARGETS):
    try:
        lines = Path(path).read_text().splitlines()
    except Exception:
        return []
    out = []
    for ln in lines:
        h = _norm(ln)
        if h and not ln.strip().startswith("#") and h not in out:
            out.append(h)
    return out


def queue(db_path=DB, targets_path=TARGETS):
    handles = db_handles(db_path)
    queued = existing_targets(targets_path)
    missing = [h for h in handles if h not in queued]
    if missing:
        targets_path = Path(targets_path)
        targets_path.parent.mkdir(parents=True, exist_ok=True)
        with targets_path.open("a", encoding="utf-8") as f:
            for h in missing:
                f.write(h + "\n")
    return {"db_rooms": len(handles), "already_queued": len(queued), "added": len(missing)}


if __name__ == "__main__":
    r = queue()
    print("DB rooms: %d | already queued: %d | newly queued: %d"
          % (r["db_rooms"], r["already_queued"], r["added"]))
    print("slow_join will work through them at <=6/day, 25-45 min gaps,")
    print("stopping instantly on any FloodWait. Already-joined rooms need")
    print("no join at all - they resolve from the session cache at boot.")
