"""
runtime_supervisor.py - keep the Replit bot and fallback sender alive.

Starts and monitors:
  - bacbo_royal_complete.py
  - bot/fallback_signal_sender.py
  - bot/fallback_result_sender.py

It guarantees required environment variables/PYTHONPATH and restarts either
process if it exits. Run from /home/runner/workspace:

  python3 -u bot/runtime_supervisor.py
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"
LOG_DIR = ROOT / "logs"

# luxury_building.env must win over Replit Secrets / inherited shell values.
_LUXURY_FORCE_KEYS = {
    "EDGE_POLICY_MODE",
    "EDGE_LUXURY_FLOOR_GATE",
    "EDGE_LEGACY_355_WARN",
    "FALLBACK_SEND_BLOCKED",
    "FALLBACKS_ENABLED",
    "LUXURY_NO_HOUR_BLOCKS",
    "LUXURY_LIVE_FLOORS",
    "TELEGRAM_TARGET_PEER",
}


def _load_dotenv_file(
    path: Path,
    env: dict[str, str],
    *,
    force_keys: set[str] | None = None,
) -> None:
    if not path.exists():
        return
    force_keys = force_keys or set()
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in force_keys:
            env[key] = value
        else:
            env.setdefault(key, value)


def _env() -> dict[str, str]:
    env = os.environ.copy()
    # Defaults first; luxury_building.env overwrites policy keys (fixes Secret=shadow).
    _load_dotenv_file(ROOT / ".env", env)
    _load_dotenv_file(ROOT / "luxury_building.env", env, force_keys=_LUXURY_FORCE_KEYS)
    session_path = ROOT / ".telegram_session_string"
    if session_path.exists():
        _sv = session_path.read_text(errors="ignore").strip()
        if len(_sv) > 50:
            env["TELEGRAM_SESSION_STRING"] = _sv
        elif len((env.get("TELEGRAM_SESSION_STRING") or "").strip()) <= 50:
            env.pop("TELEGRAM_SESSION_STRING", None)
    if len((env.get("TELEGRAM_SESSION_STRING") or "").strip()) <= 50:
        env.pop("TELEGRAM_SESSION_STRING", None)
    # Prefer luxury when luxury_building.env is present; otherwise keep caller/shadow.
    if (ROOT / "luxury_building.env").exists():
        mode = (env.get("EDGE_POLICY_MODE") or "luxury").strip().lower()
        if mode not in {"luxury", "precision", "volume"}:
            # Never stay observe-only shadow when luxury building is installed.
            mode = "luxury"
        env["EDGE_POLICY_MODE"] = mode
        env.setdefault("EDGE_LUXURY_FLOOR_GATE", "1")
        env.setdefault("FALLBACK_SEND_BLOCKED", "0")
        env.setdefault("FALLBACKS_ENABLED", "1")
    else:
        env.setdefault("EDGE_POLICY_MODE", "shadow")
    env.setdefault("EDGE_LEGACY_355_WARN", "1")
    env.setdefault("BOT_TZ", "America/Sao_Paulo")
    env["PYTHONPATH"] = f"{BOT}:{ROOT}:{env.get('PYTHONPATH', '')}"
    print(
        f"[Supervisor] EDGE_POLICY_MODE={env.get('EDGE_POLICY_MODE')} "
        f"FLOOR_GATE={env.get('EDGE_LUXURY_FLOOR_GATE')} "
        f"FALLBACKS={env.get('FALLBACKS_ENABLED')}"
    )
    return env


def _start(name: str, cmd: list[str], env: dict[str, str]) -> subprocess.Popen:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    fh = open(log_path, "ab", buffering=0)
    fh.write(f"\n--- supervisor starting {name} at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode())
    return subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _stop(proc: subprocess.Popen | None) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def main() -> int:
    env = _env()
    # Delay fallbacks so bacbo can take WAL ownership / finish boot before readers attach.
    # FALLBACKS_ENABLED=1 (default) delivers consensus/result cards to Telegram TARGET.
    fallbacks_enabled = env.get("FALLBACKS_ENABLED", "1").strip() not in ("0", "false", "False", "no")
    fallback_delay = float(env.get("FALLBACK_START_DELAY_SECS", "20"))
    boot_t0 = time.time()
    processes: dict[str, tuple[list[str], subprocess.Popen | None, float]] = {
        "bot_live": ([sys.executable, "-u", str(ROOT / "bacbo_royal_complete.py")], None, 0.0),
    }
    if fallbacks_enabled:
        processes["fallback_sender"] = (
            [sys.executable, "-u", str(BOT / "fallback_signal_sender.py")],
            None,
            0.0,
        )
        processes["fallback_result_sender"] = (
            [sys.executable, "-u", str(BOT / "fallback_result_sender.py")],
            None,
            0.0,
        )
    env["FALLBACK_SEND_BLOCKED"] = env.get("FALLBACK_SEND_BLOCKED", "0")
    env["FALLBACK_MIN_BLOCKED_SCORE"] = env.get("FALLBACK_MIN_BLOCKED_SCORE", "6.0")

    print("[Supervisor] starting. Logs in /home/runner/workspace/logs/")
    print(f"[Supervisor] fallbacks_enabled={fallbacks_enabled} fallback_start_delay_secs={fallback_delay}")
    try:
        while True:
            for name, (cmd, proc, last_start) in list(processes.items()):
                if proc is None or proc.poll() is not None:
                    if name.startswith("fallback") and (time.time() - boot_t0) < fallback_delay:
                        continue
                    if time.time() - last_start < 10:
                        time.sleep(10 - (time.time() - last_start))
                    print(f"[Supervisor] starting/restarting {name}")
                    proc = _start(name, cmd, env)
                    processes[name] = (cmd, proc, time.time())
            time.sleep(5)
    except KeyboardInterrupt:
        print("[Supervisor] stopping")
        for _, proc, _ in processes.values():
            _stop(proc)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
