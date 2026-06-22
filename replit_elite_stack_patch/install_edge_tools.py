from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from urllib.request import urlretrieve


ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"
BASE = "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch"

FILES = [
    "bot/edge_live_policy.py",
    "bot/edge_whitelist_engine.py",
    "bot/tri_brain_score.py",
    "bot/g0_offset_oracle.py",
    "bot/volume_frontier.py",
    "bot/early_source_audit.py",
    "bot/result_lag_miner.py",
    "bot/omni_score.py",
    "bot/room_cleaner.py",
    "bot/early_result_audit.py",
    "bot/martingale_audit.py",
    "bot/truth_verifier.py",
]


def download_files() -> None:
    BOT.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"{BASE}/{rel}"
        print(f"download {rel}")
        urlretrieve(url, target)


def patch_signal_handler() -> None:
    p = BOT / "signal_handler.py"
    if not p.exists():
        raise SystemExit("bot/signal_handler.py is missing. Restore it from full_replit_app.zip first.")

    s = p.read_text()
    if "[EdgePolicy]" in s and "from edge_live_policy import evaluate" in s:
        print("EdgePolicy already installed in signal_handler.py")
        return

    needle = "  if _cross_color_blocked(w_color):\n"
    insert = """  # ── Edge Live Policy (SNIPER / WATCH / LOSS-RISK) ─────────────────────────
  # EDGE_POLICY_MODE:
  #   shadow    = observe only; never blocks
  #   precision = SNIPER/ELITE cells fire; non-whitelist and loss-risk block
  #   volume    = SNIPER/ELITE + WATCH cells fire; loss-risk blocks
  try:
      from edge_live_policy import evaluate as _edge_policy_eval
      try:
          from floor_tracker import get_floor as _edge_get_floor
          _edge_floor = _edge_get_floor()
      except Exception:
          _edge_floor = getattr(state, "_current_source_floor", "LIVE") or "LIVE"

      _edge_v = _edge_policy_eval(
          kind=kind,
          color=w_color,
          agreeing_rooms=agreeing,
          source_floor=_edge_floor,
          hour_utc=_utc_hour_global,
      )
      _edge_action = _edge_v.get("action")
      _edge_reason = _edge_v.get("reason", "")

      if _edge_action == "BLOCK":
          log.info(f"⛔ [EdgePolicy] {kind}/{w_color} BLOCKED — {_edge_reason} | rooms={agreeing}")
          _record_gate_block(kind, w_color, agreeing, total, "edge_policy")
          state.engine.reset()
          return
      elif _edge_action in ("ALLOW", "SHADOW_ALLOW", "SHADOW_BLOCK"):
          log.info(f"✅ [EdgePolicy] {kind}/{w_color} {_edge_action} — {_edge_reason} | rooms={agreeing}")
  except Exception as _edge_exc:
      log.warning(f"[EdgePolicy] skipped due to error: {_edge_exc}")

"""
    if needle not in s:
        raise SystemExit(
            "Could not find patch location in signal_handler.py "
            "(missing line: if _cross_color_blocked(w_color):)"
        )
    p.write_text(s.replace(needle, insert + needle))
    print("EdgePolicy installed in signal_handler.py")


def compile_check() -> None:
    files = [str(ROOT / rel) for rel in FILES if (ROOT / rel).exists()]
    files.append(str(BOT / "signal_handler.py"))
    subprocess.check_call([sys.executable, "-m", "py_compile", *files])
    print("compile ok")


def run_fast_reports() -> None:
    db = BOT / "bacbo.db"
    if not db.exists():
        print("skip reports: bot/bacbo.db missing")
        return
    commands = [
        ["volume_frontier.py", "--db", str(db), "--report", str(BOT / "data/volume_frontier_report.json")],
        ["g0_offset_oracle.py", "--db", str(db), "--days", "9999", "--max-offset", "6", "--report", str(BOT / "data/g0_offset_oracle_report.json")],
        ["tri_brain_score.py", "--db", str(db), "--train-days", "9999", "--score-days", "7", "--limit", "500", "--report", str(BOT / "data/tri_brain_report.json")],
        ["edge_whitelist_engine.py", "--db", str(db), "--days", "30", "--report", str(BOT / "data/edge_whitelist_engine.json")],
    ]
    for cmd in commands:
        print("run", " ".join(cmd))
        subprocess.check_call([sys.executable, "-u", str(BOT / cmd[0]), *cmd[1:]])


def main() -> int:
    download_files()
    patch_signal_handler()
    compile_check()
    os.environ.setdefault("EDGE_POLICY_MODE", "shadow")
    run_fast_reports()
    print(textwrap.dedent("""
    DONE.
    EdgePolicy is installed. Start with:
      export EDGE_POLICY_MODE=shadow
    Then restart the bot and watch logs for EdgePolicy.
    """).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
