#!/usr/bin/env python3
"""Install luxury building stack on Replit and enable all WR>=60 floors.

Paste on Replit Shell:

  cd /home/runner/workspace
  curl -fsSL -o install_luxury_building.py \\
    https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/install_luxury_building.py
  python3 -u install_luxury_building.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from urllib.request import urlretrieve


ROOT = Path("/home/runner/workspace")
if not (ROOT / "bot").exists():
    ROOT = Path.cwd()
BOT = ROOT / "bot"
BASE = "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch"

FILES = [
    "bot/edge_live_policy.py",
    "bot/edge_whitelist_engine.py",
    "bot/skyscraper_floor_factory.py",
    "bot/skyscraper_stack.py",
    "bot/floor_stack_registry.py",
    "bot/luxury_building_stack.py",
    "bot/legacy_peak_355.py",
    "bot/system_health_audit.py",
    "bot/unlock_signal_flow.py",
    "bot/hotfix_signal_handler.py",
    "bot/hotfix_signal_flow_dampers.py",
    "bot/hotfix_room_noise_filter.py",
    "bot/fallback_signal_sender.py",
    "bot/fallback_result_sender.py",
    "bot/runtime_supervisor.py",
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
    "install_edge_tools.py",
]


def download_files() -> None:
    BOT.mkdir(parents=True, exist_ok=True)
    (BOT / "data").mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"{BASE}/{rel}"
        print(f"download {rel}")
        urlretrieve(url, target)


def patch_via_edge_tools() -> None:
    # Reuse the proven signal_handler EdgePolicy patcher.
    sys.path.insert(0, str(ROOT))
    import install_edge_tools as iet

    iet.ROOT = ROOT
    iet.BOT = BOT
    iet.patch_signal_handler()
    iet.compile_check()


def write_env_snippet(live_floors: list[str]) -> Path:
    path = ROOT / "luxury_building.env"
    body = textwrap.dedent(f"""\
    # Luxury building runtime — source this before starting the bot
    export EDGE_POLICY_MODE=luxury
    export EDGE_LUXURY_FLOOR_GATE=1
    export EDGE_LEGACY_355_WARN=1
    export FALLBACK_SEND_BLOCKED=0
    export LUXURY_LIVE_FLOORS={",".join(live_floors)}
    """)
    path.write_text(body)
    print(f"wrote {path}")
    return path


def enable_floors_best_effort(live_floors: list[str]) -> None:
    """Try to unlock every live floor in common Replit floor trackers / gate configs."""
    # 1) JSON allowlist consumed by our policy + optional floor_tracker forks
    allow_path = BOT / "data" / "luxury_live_floors.json"
    allow_path.write_text(json.dumps({"live_floors": live_floors, "blocked": ["JUN12A", "JUN12B"]}, indent=2) + "\n")
    print(f"wrote {allow_path}")

    # 2) Patch floor_tracker.py if it exposes an allowlist / enabled set
    ft = BOT / "floor_tracker.py"
    if not ft.exists():
        print("floor_tracker.py not found — floors rotate via existing engine only")
        return

    src = ft.read_text(encoding="utf-8", errors="replace")
    marker = "LUXURY_LIVE_FLOORS_PATCH"
    if marker in src:
        print("floor_tracker already has luxury patch")
        return

    # Append a small override that expands enabled floors when present.
    append = textwrap.dedent(f'''

    # --- {marker} ---
    try:
        import json as _lux_json
        from pathlib import Path as _LuxPath
        _lux_p = _LuxPath(__file__).resolve().parent / "data" / "luxury_live_floors.json"
        if _lux_p.exists():
            _lux_data = _lux_json.loads(_lux_p.read_text(encoding="utf-8"))
            _lux_live = [str(x).upper() for x in (_lux_data.get("live_floors") or [])]
            for _name in ("ENABLED_FLOORS", "LIVE_FLOORS", "ACTIVE_FLOORS", "FLOOR_ALLOWLIST"):
                if _name in globals() and isinstance(globals()[_name], (set, list, tuple)):
                    _cur = globals()[_name]
                    if isinstance(_cur, set):
                        globals()[_name] = set(_cur) | set(_lux_live)
                    else:
                        globals()[_name] = list(dict.fromkeys(list(_cur) + _lux_live))
            # Common helper patterns
            if "get_enabled_floors" in globals() and callable(get_enabled_floors):
                _orig_get_enabled = get_enabled_floors
                def get_enabled_floors(*a, **k):
                    try:
                        base = list(_orig_get_enabled(*a, **k) or [])
                    except Exception:
                        base = []
                    return list(dict.fromkeys([str(x).upper() for x in base] + _lux_live))
    except Exception as _lux_exc:
        try:
            print("luxury floor enable skipped:", _lux_exc)
        except Exception:
            pass
    ''')
    ft.write_text(src + append)
    print(f"patched {ft} with luxury live floors ({len(live_floors)})")


def run_reports() -> dict:
    db = BOT / "bacbo.db"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BOT) + os.pathsep + env.get("PYTHONPATH", "")

    cmds = []
    if db.exists():
        cmds.extend([
            [sys.executable, "-u", str(BOT / "floor_stack_registry.py"), "--db", str(db)],
            [sys.executable, "-u", str(BOT / "edge_whitelist_engine.py"), "--db", str(db), "--days", "30"],
            [sys.executable, "-u", str(BOT / "skyscraper_floor_factory.py"), "--db", str(db), "--days", "30"],
            [sys.executable, "-u", str(BOT / "skyscraper_stack.py"), "--db", str(db), "--days", "30"],
        ])
    cmds.append([sys.executable, "-u", str(BOT / "luxury_building_stack.py"), "--db", str(db)])

    for cmd in cmds:
        print("run", " ".join(cmd))
        subprocess.check_call(cmd, cwd=str(BOT), env=env)

    report_path = BOT / "data" / "luxury_building_stack.json"
    with open(report_path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    download_files()
    patch_via_edge_tools()
    report = run_reports()
    live = report.get("live_building_floors") or []
    write_env_snippet(live)
    enable_floors_best_effort(live)

    # Persist mode for current shell / .replit custom env if present
    os.environ["EDGE_POLICY_MODE"] = "luxury"
    os.environ["EDGE_LUXURY_FLOOR_GATE"] = "1"

    print(textwrap.dedent(f"""
    ============================================================
    LUXURY BUILDING INSTALLED
    live_floors={len(live)}
    floors={', '.join(live)}
    blocked={', '.join(report.get('blocked_floors') or [])}
    ============================================================
    NEXT:
      source /home/runner/workspace/luxury_building.env
      # restart bot / supervisor so EDGE_POLICY_MODE=luxury is active
      python3 -u bot/runtime_supervisor.py   # optional
    EXPORTS (paste after upload via YDRAY):
      bash replit_pull_luxury_export.sh
      bash replit_pull_may_jul.sh
    """).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
