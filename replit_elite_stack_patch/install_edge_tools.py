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
    "bot/skyscraper_floor_factory.py",
    "bot/skyscraper_stack.py",
    "bot/floor_stack_registry.py",
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
    if "EdgePolicy/SHADOW" in s:
        if patch_existing_edge_policy_legacy(p, s):
            print("EdgePolicy shadow already installed; legacy warning path verified/upgraded")
        else:
            print("EdgePolicy shadow already installed in signal_handler.py")
        return

    if "EdgePolicy" in s and "edge_live_policy" in s:
        if patch_existing_edge_policy_legacy(p, s):
            print("EdgePolicy already installed; legacy warning path verified/upgraded")
        else:
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
      _edge_warning = _edge_v.get("legacy_warning")
      if _edge_warning:
          log.info(f"[Legacy355] {_edge_warning}")
          if isinstance(locals().get("msg"), str) and "LEGACY_355_PAWTUCKET" not in msg:
              msg = msg + "\\n\\nWARNING LEGACY_355_PAWTUCKET\\n" + str(_edge_warning)

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
    if needle in s:
        p.write_text(s.replace(needle, insert + needle))
        print("EdgePolicy installed in signal_handler.py")
        return

    installed = patch_signal_handler_shadow(p, s)
    if installed <= 0:
        raise SystemExit(
            "Could not find a safe EdgePolicy patch location in signal_handler.py. "
            "Run the diagnostic scanner and send the await send(...) snippets."
        )
    print(f"EdgePolicy shadow installed in signal_handler.py at {installed} send point(s)")


def patch_existing_edge_policy_legacy(path: Path, source: str) -> bool:
    """Upgrade an older EdgePolicy install so it appends legacy warnings."""
    if "LEGACY_355_PAWTUCKET" in source:
        return True

    full_needle = '      _edge_reason = _edge_v.get("reason", "")\n\n      if _edge_action == "BLOCK":'
    full_insert = '''      _edge_reason = _edge_v.get("reason", "")
      _edge_warning = _edge_v.get("legacy_warning")
      if _edge_warning:
          log.info(f"[Legacy355] {_edge_warning}")
          if isinstance(locals().get("msg"), str) and "LEGACY_355_PAWTUCKET" not in msg:
              msg = msg + "\\n\\nWARNING LEGACY_355_PAWTUCKET\\n" + str(_edge_warning)

      if _edge_action == "BLOCK":'''
    if full_needle in source:
        path.write_text(source.replace(full_needle, full_insert))
        return True

    lines = source.splitlines()
    out: list[str] = []
    installed = 0
    pending_shadow_warning = False
    for line in lines:
        stripped = line.strip()
        out.append(line)
        if stripped.startswith("_edge_v = _edge_policy_eval("):
            pending_shadow_warning = True
        if pending_shadow_warning and stripped == "log.info(":
            indent = line[:len(line) - len(line.lstrip())]
            out.pop()
            out.extend([
                f'{indent}_edge_warning = _edge_v.get("legacy_warning")',
                f'{indent}if _edge_warning:',
                f'{indent}    log.info(f"[Legacy355] {{_edge_warning}}")',
                f'{indent}    if isinstance(locals().get("msg"), str) and "LEGACY_355_PAWTUCKET" not in msg:',
                f'{indent}        msg = msg + "\\n\\nWARNING LEGACY_355_PAWTUCKET\\n" + str(_edge_warning)',
                line,
            ])
            installed += 1
            pending_shadow_warning = False

    if installed:
        path.write_text("\n".join(out) + "\n")
        return True
    return False


def patch_signal_handler_shadow(path: Path, source: str) -> int:
    """Install observe-only logging for older handlers with different gate layout."""
    if "EdgePolicy/SHADOW" in source:
        patch_existing_edge_policy_legacy(path, source)
        print("EdgePolicy shadow already installed in signal_handler.py")
        return 1

    send_needles = {
        "_sent_id = await send(msg, pin=(not _round_passed), buttons=make_outcome_buttons(cid))",
        "_sent_id = await send(msg, pin=False, buttons=make_outcome_buttons(cid))",
        "_sent_id = await send(msg, pin=True, buttons=make_outcome_buttons(cid))",
    }

    lines = source.splitlines()
    out: list[str] = []
    installed = 0

    for line in lines:
        stripped = line.strip()
        is_outcome_send = stripped in send_needles
        # Older Replit handlers sometimes use bare await send(msg) for signal cards.
        # Keep this observe-only and guard on local signal variables to avoid noisy logs.
        is_bare_signal_send = stripped.startswith("await send(msg") and "make_outcome_buttons" not in stripped
        if is_outcome_send or is_bare_signal_send:
            indent = line[:len(line) - len(line.lstrip())]
            snippet = f'''{indent}try:
{indent}    _edge_kind = locals().get("kind")
{indent}    _edge_color = locals().get("w_color") or locals().get("color")
{indent}    if _edge_kind and _edge_color:
{indent}        from edge_live_policy import evaluate as _edge_policy_eval
{indent}        try:
{indent}            from floor_tracker import get_floor as _edge_get_floor
{indent}            _edge_floor = _edge_get_floor()
{indent}        except Exception:
{indent}            _edge_state = locals().get("state") or globals().get("state")
{indent}            _edge_floor = getattr(_edge_state, "_current_source_floor", "LIVE") if _edge_state else "LIVE"
{indent}        _edge_hour = locals().get("_utc_hour_global", globals().get("_utc_hour_global"))
{indent}        _edge_rooms = locals().get("agreeing") or locals().get("rooms_agreed") or []
{indent}        _edge_v = _edge_policy_eval(
{indent}            kind=_edge_kind,
{indent}            color=_edge_color,
{indent}            agreeing_rooms=_edge_rooms,
{indent}            source_floor=_edge_floor,
{indent}            hour_utc=_edge_hour,
{indent}        )
{indent}        _edge_warning = _edge_v.get("legacy_warning")
{indent}        if _edge_warning:
{indent}            log.info(f"[Legacy355] {{_edge_warning}}")
{indent}            if isinstance(locals().get("msg"), str) and "LEGACY_355_PAWTUCKET" not in msg:
{indent}                msg = msg + "\\n\\nWARNING LEGACY_355_PAWTUCKET\\n" + str(_edge_warning)
{indent}        log.info(
{indent}            f"✅ [EdgePolicy/SHADOW] {{_edge_kind}}/{{_edge_color}} "
{indent}            f"{{_edge_v.get('action')}} — {{_edge_v.get('reason')}} | rooms={{_edge_rooms}}"
{indent}        )
{indent}except Exception as _edge_exc:
{indent}    try:
{indent}        log.debug(f"[EdgePolicy/SHADOW] skipped due to error: {{_edge_exc}}")
{indent}    except Exception:
{indent}        pass'''
            out.append(snippet)
            installed += 1
        out.append(line)

    if installed:
        path.write_text("\n".join(out) + "\n")
    return installed


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
        ["legacy_peak_355.py", "--db", str(db), "--report", str(BOT / "data/legacy_peak_355_report.json")],
        ["tri_brain_score.py", "--db", str(db), "--train-days", "9999", "--score-days", "7", "--limit", "500", "--report", str(BOT / "data/tri_brain_report.json")],
        ["edge_whitelist_engine.py", "--db", str(db), "--days", "30", "--report", str(BOT / "data/edge_whitelist_engine.json")],
        ["floor_stack_registry.py", "--db", str(db), "--report", str(BOT / "data/floor_stack_registry_report.json")],
        ["skyscraper_floor_factory.py", "--db", str(db), "--days", "30", "--report", str(BOT / "data/skyscraper_floor_factory_report.json")],
        ["skyscraper_stack.py", "--db", str(db), "--days", "30", "--report", str(BOT / "data/skyscraper_stack_report.json")],
        ["system_health_audit.py", "--db", str(db), "--report", str(BOT / "data/system_health_audit.json")],
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
