"""fire_gap_diagnosis.py - explain every silent stretch between fires.

Run from the bot directory (where bot.log and bacbo.db live):

    python3 fire_gap_diagnosis.py [--hours 24] [--gap-min 8]

For each gap between consecutive fires it reports which of these was happening
inside the gap, using only bot.log and the consensus_signals table:

  DOWN/STALLED  bot.log had no lines for a long stretch (process dead, frozen
                connection, or the Replit workspace was asleep)
  RESTARTED     the bot booted again inside the gap (rooms banner)
  FLOODWAIT     Telegram rate limit hit inside the gap
  RECONNECT     freeze watchdog / reconnect fired inside the gap
  QUIET MARKET  bot was alive and logging; no qualifying setup appeared

Read-only. Never touches Telegram or the bot process.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
ROOMS_RE = re.compile(r"✅ (\d+) rooms")
FLOOD_RE = re.compile(r"FloodWait|A wait of \d+ seconds", re.I)
RECONNECT_RE = re.compile(r"ConnFreeze|Watchdog|sem mensagens|Reconectando|soft reconnect", re.I)
CRASH_RE = re.compile(r"Traceback|Bus error|disk I/O error|database is locked|Killed", re.I)
FMT = "%Y-%m-%d %H:%M:%S"
SILENCE_S = 180


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts[:19], FMT).replace(tzinfo=timezone.utc)


def read_log(path: Path, since: datetime) -> list[tuple[datetime, str]]:
    rows: list[tuple[datetime, str]] = []
    with path.open(errors="ignore") as fh:
        for line in fh:
            m = TS_RE.match(line)
            if not m:
                continue
            t = _parse(m.group(1))
            if t >= since:
                rows.append((t, line))
    return rows


def read_fires(db: Path, since: datetime) -> list[tuple[datetime, str]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = con.execute(
            "select fired_at, coalesce(signal_kind,'?') from consensus_signals "
            "where fired_at >= ? order by fired_at",
            (since.strftime(FMT),),
        )
        return [(_parse(a), k) for a, k in cur if a]
    finally:
        con.close()


def classify(log, start: datetime, end: datetime):
    inside = [(t, ln) for t, ln in log if start <= t <= end]
    counts: Counter[str] = Counter()
    for _, ln in inside:
        if ROOMS_RE.search(ln):
            counts["restart"] += 1
        if FLOOD_RE.search(ln):
            counts["flood"] += 1
        if RECONNECT_RE.search(ln):
            counts["reconnect"] += 1
        if CRASH_RE.search(ln):
            counts["crash"] += 1
    marks = [start] + [t for t, _ in inside] + [end]
    silence = max(((b - a).total_seconds() for a, b in zip(marks, marks[1:])), default=0.0)
    return counts, silence


def verdict(counts: Counter, silence: float, span: float) -> str:
    if silence >= max(SILENCE_S, span * 0.5):
        return f"DOWN/STALLED (log silent {int(silence // 60)}m{int(silence % 60):02d}s)"
    if counts["restart"]:
        return f"RESTARTED x{counts['restart']}"
    if counts["flood"]:
        return f"FLOODWAIT x{counts['flood']}"
    if counts["reconnect"]:
        return f"RECONNECT x{counts['reconnect']}"
    if counts["crash"]:
        return f"ERRORS x{counts['crash']}"
    return "QUIET MARKET (bot alive and logging, no setup qualified)"


def process_info() -> list[str]:
    out = []
    dep = os.environ.get("REPLIT_DEPLOYMENT") or os.environ.get("REPL_DEPLOYMENT")
    out.append(
        "host: Replit DEPLOYMENT (stays up)" if dep
        else "host: Replit WORKSPACE shell (process dies when the workspace sleeps)"
    )
    try:
        ps = os.popen("ps -eo pid=,etime=,args=").read().splitlines()
    except Exception as exc:
        return out + [f"process check failed: {exc}"]
    me = str(os.getpid())
    rows = [r.split(None, 2) for r in ps if len(r.split(None, 2)) == 3 and r.split(None, 1)[0] != me]
    mains = [r for r in rows if r[2].startswith("python") and "main.py" in r[2] and "-u" in r[2]]
    for pid, et, _ in mains:
        out.append(f"main.py pid={pid} uptime={et}")
    if not mains:
        out.append("main.py: NOT RUNNING")
    sup = [r for r in rows if re.search(r"watchdog_external|runtime_supervisor", r[2])
           and "ps -eo" not in r[2] and "fire_gap_diagnosis" not in r[2]]
    out.append("supervisor: " + (sup[0][2][:80] if sup else "NONE running"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--gap-min", type=float, default=8)
    ap.add_argument("--log", default="bot.log")
    ap.add_argument("--db", default="bacbo.db")
    a = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=a.hours)
    log_p, db_p = Path(a.log), Path(a.db)
    if not log_p.exists() or not db_p.exists():
        print(f"need {log_p} and {db_p} in the current directory")
        return 2

    log = read_log(log_p, since)
    if log and log[0][0] > since:
        since = log[0][0]
    fires = read_fires(db_p, since)
    print(f"window: last {a.hours:g}h | fires: {len(fires)} | log lines: {len(log)}")
    kinds = Counter(k for _, k in fires)
    print("fires by kind:", dict(kinds) or "none")
    print("restarts in window:", sum(1 for _, ln in log if ROOMS_RE.search(ln)))
    print("floodwait lines   :", sum(1 for _, ln in log if FLOOD_RE.search(ln)))
    print("reconnect lines   :", sum(1 for _, ln in log if RECONNECT_RE.search(ln)))

    points = [(since, "window start")] + fires + [(now, "now")]
    last_gap_idx = len(points) - 2
    totals: Counter[str] = Counter()
    print(f"\ngaps >= {a.gap_min:g} min between fires (UTC):")
    shown = 0
    for i, ((t0, _), (t1, _)) in enumerate(zip(points, points[1:])):
        span = (t1 - t0).total_seconds()
        if span < a.gap_min * 60:
            continue
        counts, silence = classify(log, t0, t1)
        v = verdict(counts, silence, span)
        totals[v.split(" ")[0]] += span
        shown += 1
        tail = "  (still open, since last fire)" if i == last_gap_idx else ""
        print(f"  {t0:%m-%d %H:%M} -> {t1:%H:%M}  {int(span // 60):4d} min  {v}{tail}")
    if not shown:
        print("  none")
    else:
        tot = sum(totals.values()) or 1
        print("\nsilent time by cause:")
        for k, s in totals.most_common():
            print(f"  {k:<12} {s / 3600:5.1f} h  ({100 * s / tot:3.0f}%)")

    print("\n" + "\n".join(process_info()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
