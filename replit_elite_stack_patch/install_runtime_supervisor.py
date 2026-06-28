from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlretrieve


ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"
BASE = "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch"

FILES = [
    "bot/fallback_signal_sender.py",
    "bot/fallback_result_sender.py",
    "bot/runtime_supervisor.py",
]


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, check=check)


def download() -> None:
    BOT.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"{BASE}/{rel}"
        print(f"download {rel}")
        urlretrieve(url, target)


def compile_check() -> None:
    run([sys.executable, "-m", "py_compile", *[str(ROOT / rel) for rel in FILES]])


def stop_old() -> None:
    patterns = [
        "runtime_supervisor.py",
        "fallback_result_sender.py",
        "fallbackèresultèsender.py",
        "fallback_signal_sender.py",
        "bacbo_royal_complete.py",
    ]
    for pattern in patterns:
        subprocess.run(["pkill", "-f", pattern], cwd=ROOT, check=False)


def start_supervisor() -> None:
    log = ROOT / "supervisor.log"
    env = os.environ.copy()
    session_file = ROOT / ".telegram_session_string"
    if session_file.exists():
        env["TELEGRAM_SESSION_STRING"] = session_file.read_text(errors="ignore").strip()
    env["EDGE_POLICY_MODE"] = "volume"
    env["EDGE_LEGACY_355_WARN"] = "1"
    env["FALLBACK_SEND_BLOCKED"] = "1"
    env["FALLBACK_MIN_BLOCKED_SCORE"] = "6.0"
    env["FALLBACK_BLOCKED_LOOKBACK_HOURS"] = "2"
    env["FALLBACK_OPPOSITE_LOCK_SECONDS"] = "90"
    env["PYTHONPATH"] = f"{BOT}:{ROOT}:{env.get('PYTHONPATH', '')}"

    with open(log, "ab", buffering=0) as fh:
        subprocess.Popen(
            [sys.executable, "-u", str(BOT / "runtime_supervisor.py")],
            cwd=ROOT,
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def show_status() -> None:
    time.sleep(8)
    print("\n=== PROCESSES ===")
    subprocess.run(
        "ps aux | grep -E 'runtime_supervisor.py|bacbo_royal_complete.py|fallback_signal_sender.py|fallback_result_sender.py|fallbackèresultèsender.py' | grep -v grep || true",
        cwd=ROOT,
        shell=True,
        check=False,
    )
    for rel in ["supervisor.log", "logs/fallback_sender.log", "logs/fallback_result_sender.log", "logs/bot_live.log"]:
        path = ROOT / rel
        print(f"\n=== {rel} ===")
        if path.exists():
            text = path.read_text(errors="ignore")
            print(text[-2500:])
        else:
            print("missing")


def main() -> int:
    download()
    compile_check()
    stop_old()
    start_supervisor()
    show_status()
    print("\nDONE. Leave supervisor running; it will restart bot/fallback/result sender if they crash.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
