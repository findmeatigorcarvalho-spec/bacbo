"""
system_health_audit.py - whole-app health checklist for the Replit bot.

This is intentionally read-only. It checks the pieces that usually break:
Telegram auth, start files, signal hook, reports, DB freshness, website/API
patches, schedule/watchdog hints, and autonomous learning outputs.

Output:
  bot/data/system_health_audit.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = HERE / "bacbo.db"
REPORT_PATH = HERE / "data" / "system_health_audit.json"


@dataclass
class Check:
    area: str
    name: str
    status: str
    detail: str
    fix: str = ""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_env_file() -> dict[str, str]:
    out: dict[str, str] = {}
    env_path = ROOT / ".env"
    if not env_path.exists():
        return out
    for raw in env_path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _env_value(key: str, env_file: dict[str, str]) -> str:
    return os.environ.get(key) or env_file.get(key, "")


def _status(ok: bool, warn: bool = False) -> str:
    if ok:
        return "OK"
    return "WARN" if warn else "FAIL"


def _file_age_minutes(path: Path) -> float | None:
    try:
        return round((_utc_now().timestamp() - path.stat().st_mtime) / 60.0, 1)
    except OSError:
        return None


def _json_ok(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        json.loads(path.read_text(errors="ignore"))
        age = _file_age_minutes(path)
        return True, f"valid json, age={age}m"
    except Exception as exc:
        return False, f"invalid json: {exc}"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return row[0]


def check_runtime(env_file: dict[str, str]) -> list[Check]:
    checks: list[Check] = []
    session = _env_value("TELEGRAM_SESSION_STRING", env_file)
    session_file = ROOT / ".telegram_session_string"
    file_session_len = len(session_file.read_text(errors="ignore").strip()) if session_file.exists() else 0
    session_len = max(len(session.strip()), file_session_len)
    checks.append(Check(
        "runtime",
        "telegram_session",
        _status(session_len > 50),
        f"session length={session_len}",
        "Generate a new Telethon StringSession and export TELEGRAM_SESSION_STRING." if session_len <= 50 else "",
    ))

    api_id = _env_value("TELEGRAM_API_ID", env_file)
    api_hash = _env_value("TELEGRAM_API_HASH", env_file)
    checks.append(Check(
        "runtime",
        "telegram_api_keys",
        _status(bool(api_id and api_hash)),
        f"api_id={'set' if api_id else 'missing'}, api_hash={'set' if api_hash else 'missing'}",
        "Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env/Replit Secrets." if not (api_id and api_hash) else "",
    ))

    bot_enabled = _env_value("BOT_ENABLED", env_file) or "unset"
    checks.append(Check(
        "runtime",
        "bot_enabled",
        _status(str(bot_enabled).lower() == "true", warn=True),
        f"BOT_ENABLED={bot_enabled}",
        "Set BOT_ENABLED=true if you expect live tracking." if str(bot_enabled).lower() != "true" else "",
    ))

    py_path = os.environ.get("PYTHONPATH", "")
    checks.append(Check(
        "runtime",
        "pythonpath",
        _status("bot" in py_path or (ROOT / "tz_utils.py").exists(), warn=True),
        f"PYTHONPATH has bot={'bot' in py_path}",
        "Start with PYTHONPATH=/home/runner/workspace/bot:/home/runner/workspace:$PYTHONPATH if imports fail.",
    ))
    return checks


def check_files() -> list[Check]:
    checks: list[Check] = []
    required = [
        ("startup", "bacbo_royal_complete.py", ROOT / "bacbo_royal_complete.py"),
        ("startup", "bot_signal_handler", HERE / "signal_handler.py"),
        ("edge", "edge_live_policy", HERE / "edge_live_policy.py"),
        ("edge", "legacy_peak_355", HERE / "legacy_peak_355.py"),
        ("edge", "skyscraper_factory", HERE / "skyscraper_floor_factory.py"),
        ("website", "api_routes_patch", ROOT / "artifacts/api-server/src/routes/bot.ts"),
        ("website", "engine_tab_patch", ROOT / "artifacts/dashboard/src/components/tabs/EngineTab.tsx"),
    ]
    for area, name, path in required:
        checks.append(Check(
            area,
            name,
            _status(path.exists(), warn=area == "website"),
            str(path.relative_to(ROOT)) if path.exists() else f"missing {path.relative_to(ROOT)}",
            "Re-run install_edge_tools.py or unzip latest patch." if not path.exists() else "",
        ))

    handler = HERE / "signal_handler.py"
    if handler.exists():
        text = handler.read_text(errors="ignore")
        checks.append(Check(
            "signals",
            "edge_policy_hook",
            _status("edge_live_policy" in text and "EdgePolicy" in text),
            f"EdgePolicy={'yes' if 'EdgePolicy' in text else 'no'}, import={'yes' if 'edge_live_policy' in text else 'no'}",
            "Run python3 -u install_edge_tools.py to patch signal_handler.py." if "edge_live_policy" not in text else "",
        ))
        checks.append(Check(
            "signals",
            "legacy_warning_hook",
            _status("LEGACY_355_PAWTUCKET" in text, warn=True),
            f"legacy warning append={'yes' if 'LEGACY_355_PAWTUCKET' in text else 'no'}",
            "Re-run latest install_edge_tools.py to upgrade existing EdgePolicy hook." if "LEGACY_355_PAWTUCKET" not in text else "",
        ))
    return checks


def check_reports() -> list[Check]:
    checks: list[Check] = []
    data_dir = HERE / "data"
    reports = [
        "volume_frontier_report.json",
        "g0_offset_oracle_report.json",
        "legacy_peak_355_report.json",
        "tri_brain_report.json",
        "edge_whitelist_engine.json",
        "floor_stack_registry_report.json",
        "skyscraper_floor_factory_report.json",
        "skyscraper_stack_report.json",
        "martingale_audit.json",
        "truth_verification_report.json",
    ]
    for name in reports:
        path = data_dir / name
        ok, detail = _json_ok(path)
        age = _file_age_minutes(path)
        stale = age is not None and age > 180
        checks.append(Check(
            "reports",
            name,
            "WARN" if ok and stale else _status(ok),
            detail + ("; stale" if stale else ""),
            "Run python3 -u install_edge_tools.py or refresh the individual report." if (not ok or stale) else "",
        ))
    return checks


def check_database(db_path: Path = DB_PATH) -> tuple[list[Check], dict[str, Any]]:
    checks: list[Check] = []
    metrics: dict[str, Any] = {}
    if not db_path.exists():
        return [Check("database", "bacbo_db", "FAIL", "bot/bacbo.db missing", "Restore bot/bacbo.db.")], metrics

    size_mb = round(db_path.stat().st_size / 1024 / 1024, 1)
    checks.append(Check("database", "bacbo_db", "OK", f"exists, size={size_mb}MB"))
    try:
        with _connect(db_path) as conn:
            tables = ["consensus_signals", "blocked_signals", "room_memory", "channel_messages"]
            for table in tables:
                exists = _table_exists(conn, table)
                checks.append(Check(
                    "database",
                    f"table_{table}",
                    _status(exists, warn=table != "consensus_signals"),
                    "exists" if exists else "missing",
                ))

            if _table_exists(conn, "consensus_signals"):
                metrics["signals_total"] = _scalar(conn, "SELECT COUNT(*) FROM consensus_signals") or 0
                metrics["signals_recent_24h"] = _scalar(
                    conn,
                    "SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-1 day')",
                ) or 0
                metrics["pending_stale"] = _scalar(
                    conn,
                    """
                    SELECT COUNT(*) FROM consensus_signals
                    WHERE outcome IS NULL AND fired_at < datetime('now','-30 minutes')
                    """,
                ) or 0
                checks.append(Check(
                    "signals",
                    "recent_signal_activity",
                    _status(metrics["signals_recent_24h"] > 0, warn=True),
                    f"{metrics['signals_recent_24h']} signals in last 24h",
                    "If zero while Telegram is connected, inspect gates and signal_handler send path.",
                ))
                checks.append(Check(
                    "signals",
                    "stale_pending_signals",
                    _status(metrics["pending_stale"] == 0, warn=True),
                    f"{metrics['pending_stale']} stale pending signals",
                    "Run startup cleanup or inspect unresolved signals." if metrics["pending_stale"] else "",
                ))

            if _table_exists(conn, "channel_messages"):
                metrics["messages_recent_1h"] = _scalar(
                    conn,
                    "SELECT COUNT(*) FROM channel_messages WHERE created_at >= datetime('now','-1 hour')",
                ) or 0
                checks.append(Check(
                    "telegram",
                    "recent_channel_messages",
                    _status(metrics["messages_recent_1h"] > 0, warn=True),
                    f"{metrics['messages_recent_1h']} messages in last hour",
                    "If zero, Telegram tracking may be disconnected or room subscriptions failed.",
                ))
    except Exception as exc:
        checks.append(Check("database", "db_read", "FAIL", str(exc), "Check SQLite file integrity/locks."))
    return checks, metrics


def check_schedule_autonomy() -> list[Check]:
    checks: list[Check] = []
    replit = ROOT / ".replit"
    replit_text = replit.read_text(errors="ignore") if replit.exists() else ""
    checks.append(Check(
        "schedule",
        "replit_config",
        _status(replit.exists(), warn=True),
        "present" if replit.exists() else "missing",
        "Create/restore .replit run config for one-click startup." if not replit.exists() else "",
    ))
    checks.append(Check(
        "schedule",
        "run_button_config",
        _status("run" in replit_text.lower() or "runButton" in replit_text, warn=True),
        next((line.strip() for line in replit_text.splitlines() if "run" in line.lower()), "no run line"),
        "Set .replit run command to start bacbo_royal_complete.py with required env vars." if replit.exists() else "",
    ))

    checks.append(Check(
        "autonomous",
        "watchdog_module",
        _status((HERE / "watchdog.py").exists(), warn=True),
        "present" if (HERE / "watchdog.py").exists() else "missing",
        "Keep Replit Always On/Deployment enabled or add a process watchdog." if not (HERE / "watchdog.py").exists() else "",
    ))
    checks.append(Check(
        "autonomous",
        "keep_alive",
        _status((ROOT / "keep_alive.py").exists() or (HERE / "keep_alive.py").exists(), warn=True),
        "present" if ((ROOT / "keep_alive.py").exists() or (HERE / "keep_alive.py").exists()) else "missing",
        "Restore keep_alive.py if Replit web ping endpoint is required.",
    ))
    return checks


def summarize(checks: list[Check]) -> dict[str, Any]:
    counts: dict[str, int] = {"OK": 0, "WARN": 0, "FAIL": 0}
    areas: dict[str, dict[str, int]] = {}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
        area_counts = areas.setdefault(check.area, {"OK": 0, "WARN": 0, "FAIL": 0})
        area_counts[check.status] = area_counts.get(check.status, 0) + 1
    if counts["FAIL"]:
        verdict = "FIX_REQUIRED"
    elif counts["WARN"]:
        verdict = "WATCH"
    else:
        verdict = "OK"
    return {"verdict": verdict, "counts": counts, "areas": areas}


def build_report(db_path: str = str(DB_PATH)) -> dict[str, Any]:
    env_file = _load_env_file()
    checks: list[Check] = []
    checks += check_runtime(env_file)
    checks += check_files()
    checks += check_reports()
    db_checks, metrics = check_database(Path(db_path))
    checks += db_checks
    checks += check_schedule_autonomy()

    priority = [
        asdict(c)
        for c in checks
        if c.status in {"FAIL", "WARN"}
    ][:40]
    return {
        "generated_at": _utc_now().isoformat(),
        "summary": summarize(checks),
        "metrics": metrics,
        "priority_fixes": priority,
        "checks": [asdict(c) for c in checks],
        "next_commands": [
            "export TELEGRAM_SESSION_STRING=\"$(cat .telegram_session_string)\"",
            "export EDGE_POLICY_MODE=shadow",
            "export EDGE_LEGACY_355_WARN=1",
            "export PYTHONPATH=/home/runner/workspace/bot:/home/runner/workspace:$PYTHONPATH",
            "python3 -u bacbo_royal_complete.py",
        ],
    }


def save_report(db_path: str = str(DB_PATH), path: str = str(REPORT_PATH)) -> dict[str, Any]:
    report = build_report(db_path)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(out)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run whole-app system health audit")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--report", default=str(REPORT_PATH))
    args = parser.parse_args()
    report = save_report(args.db, args.report)
    print(json.dumps({
        "generated_at": report["generated_at"],
        "summary": report["summary"],
        "metrics": report["metrics"],
        "priority_fixes": report["priority_fixes"][:20],
    }, indent=2, ensure_ascii=False))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
