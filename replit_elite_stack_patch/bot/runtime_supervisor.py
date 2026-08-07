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
LOCK_PATH = BOT / "data" / "runtime_supervisor.lock"
_SOCKET_NAME = "\0bacbo_luxury_supervisor_v1"  # abstract Unix socket (Linux)


def _acquire_supervisor_lock():
    """Singleton: abstract Unix socket (reliable) + flock (belt). Second process exits."""
    import fcntl
    import socket

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(_SOCKET_NAME)
    except OSError:
        print("[Supervisor] EXIT — singleton socket busy (another supervisor is running)")
        try:
            sock.close()
        except Exception:
            pass
        raise SystemExit(0)

    fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[Supervisor] EXIT — flock busy (another supervisor holds the lock)")
        try:
            sock.close()
        except Exception:
            pass
        os.close(fd)
        raise SystemExit(0)
    try:
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
    except Exception:
        pass
    # Keep sock alive for process lifetime (GC would release the bind).
    return {"fd": fd, "sock": sock}

# luxury_building.env must win over Replit Secrets / inherited shell values.
_LUXURY_FORCE_KEYS = {
    "EDGE_POLICY_MODE",
    "EDGE_LUXURY_FLOOR_GATE",
    "EDGE_LEGACY_355_WARN",
    "FALLBACK_SEND_BLOCKED",
    "FALLBACKS_ENABLED",
    "TELEGRAM_SINGLE_OUTBOX",
    "LUXURY_NO_HOUR_BLOCKS",
    "LUXURY_LIVE_FLOORS",
    "TELEGRAM_TARGET_PEER",
    "TELEGRAM_COUNTDOWN_PEER",
    "GUNIQUE_PEER",
    "PROFIT_SKYSCRAPER",
    "HUB_MONEY_FIRST",
    "HUB_GUNIQUE_FIRST",
    "TELEGRAM_TRASH_BLOCK",
    "TELEGRAM_SKIN_GATE",
    "TELEGRAM_SHELF_OVERFLOW_PEERS",
}

_SKYSCRAPER_FORCE_KEYS = {
    "PROFIT_SKYSCRAPER",
    "HUB_MONEY_FIRST",
    "HUB_GUNIQUE_FIRST",
    "HUB_G1_APEX_FIRST",
    "PROFIT_CHAT_BUNDLE",
    "BUNDLE_ORGANIZER",
    "RESULT_ESSENCE_ENGINE",
    "PROFIT_FAMILY_AI",
    "RESULT_ATTACH_IMMEDIATE",
    "FIRE_RESULT_LAW",
    "HUB_OUTBOX_RESULT_CARDS",
    "TELEGRAM_TRASH_BLOCK",
    "TELEGRAM_SKIN_GATE",
    "TELEGRAM_SHELF_OVERFLOW_PEERS",
    "TELEGRAM_TARGET_PEER",
    "TELEGRAM_PRIMARY_PEER",
    "TELEGRAM_PRIMARY_PEER_ID",
    "TELEGRAM_EXCLUDE_PEERS",
    "TELEGRAM_COUNTDOWN_PEER",
    "ROUND_SYNC",
    "ROUND_INTERVAL_SECS",
    "TTB_IDEAL_SECS",
    "TTB_RELEASE_MAX_SECS",
    "TTB_RELEASE_MIN_SECS",
    "PREP_INVEST_MAX_SECS",
    "ROUND_SYNC_RESULT_ALIGN",
    "PACKER_REAL_COUNTDOWN_MAX",
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
    # Profit Chat Bundle: UNIQUE_g1 APEX #1; Mr_iv4 excluded; never-delay spill.
    _load_dotenv_file(
        BOT / "data" / "profit_skyscraper.env",
        env,
        force_keys=_SKYSCRAPER_FORCE_KEYS,
    )
    _load_dotenv_file(
        ROOT / "profit_skyscraper.env",
        env,
        force_keys=_SKYSCRAPER_FORCE_KEYS,
    )
    session_path = ROOT / ".telegram_session_string"
    if session_path.exists():
        _sv = session_path.read_text(errors="ignore").strip()
        if len(_sv) > 50:
            env["TELEGRAM_SESSION_STRING"] = _sv
        elif len((env.get("TELEGRAM_SESSION_STRING") or "").strip()) <= 50:
            env.pop("TELEGRAM_SESSION_STRING", None)
    # Materialize file from env/secret so bacbo forks that only read the file can boot
    _sess = (env.get("TELEGRAM_SESSION_STRING") or "").strip()
    if len(_sess) > 50 and (
        not session_path.exists()
        or len(session_path.read_text(errors="ignore").strip()) <= 50
    ):
        try:
            session_path.write_text(_sess + "\n", encoding="utf-8")
            print(f"[Supervisor] wrote {session_path} from TELEGRAM_SESSION_STRING")
        except Exception as exc:
            print("[Supervisor] session file write skip:", repr(exc))
    if len((env.get("TELEGRAM_SESSION_STRING") or "").strip()) <= 50:
        env.pop("TELEGRAM_SESSION_STRING", None)
        print(
            "[Supervisor] WARN: no Telegram session "
            "(set Secret TELEGRAM_SESSION_STRING or .telegram_session_string) "
            "— bacbo will crash-loop"
        )
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
        env.setdefault("TELEGRAM_SINGLE_OUTBOX", "1")
        env.setdefault("TELEGRAM_COUNTDOWN_PEER", "UNIQUE_g1")
        env.setdefault("GUNIQUE_PEER", "UNIQUE_g1")
    else:
        env.setdefault("EDGE_POLICY_MODE", "shadow")
    env.setdefault("EDGE_LEGACY_355_WARN", "1")
    env.setdefault("BOT_TZ", "America/Sao_Paulo")
    env.setdefault("TELEGRAM_COUNTDOWN_PEER", "UNIQUE_g1")
    env.setdefault("GUNIQUE_PEER", "UNIQUE_g1")
    env["PYTHONPATH"] = f"{BOT}:{ROOT}:{env.get('PYTHONPATH', '')}"
    print(
        f"[Supervisor] EDGE_POLICY_MODE={env.get('EDGE_POLICY_MODE')} "
        f"FLOOR_GATE={env.get('EDGE_LUXURY_FLOOR_GATE')} "
        f"FALLBACKS={env.get('FALLBACKS_ENABLED')} "
        f"OUTBOX={env.get('TELEGRAM_SINGLE_OUTBOX')} "
        f"CD_PEER={env.get('TELEGRAM_COUNTDOWN_PEER')}"
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
    if getattr(proc, "_lux_adopted", False):
        return  # never kill an adopted pre-existing bacbo
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


class _AdoptedProc:
    """Track a pre-existing bacbo PID without owning its process group."""

    def __init__(self, pid: int):
        self.pid = pid
        self._lux_adopted = True

    def poll(self) -> int | None:
        try:
            os.kill(self.pid, 0)
            return None
        except OSError:
            return 1


def _cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except Exception:
        return ""
    return raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()


def _python_pids_with(needle: str) -> list[int]:
    """List python PIDs whose /proc cmdline contains needle. Never use pgrep -f (self-match)."""
    me = os.getpid()
    found: list[int] = []
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid == me:
                continue
            cmd = _cmdline(pid)
            if not cmd or needle not in cmd:
                continue
            if "python" not in cmd.lower():
                continue
            if any(x in cmd for x in ("pgrep", "pkill", "REPLIT_ONE_STACK", "ONE.sh")):
                continue
            found.append(pid)
    except Exception:
        return []
    return sorted(found)


def _find_bacbo_pids() -> list[int]:
    return _python_pids_with("bacbo_royal_complete.py")


def _find_bacbo_pid() -> int | None:
    pids = _find_bacbo_pids()
    return pids[0] if pids else None


def _kill_pat(pat: str) -> None:
    for pid in _python_pids_with(pat):
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass


def _reap_duplicates(*, single_outbox: bool) -> None:
    """Keep oldest bacbo/outbox; always kill legacy dual-fallback stealers."""
    bacbos = _find_bacbo_pids()
    if len(bacbos) > 1:
        keep = min(bacbos)
        for pid in bacbos:
            if pid == keep:
                continue
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"[Supervisor] killed extra bacbo pid={pid} keep={keep}")
            except Exception:
                pass
    if single_outbox:
        _kill_pat("fallback_signal_sender.py")
        _kill_pat("fallback_result_sender.py")
        opids = _python_pids_with("telegram_outbox.py")
        if len(opids) > 1:
            for pid in opids[1:]:
                try:
                    os.kill(pid, signal.SIGKILL)
                    print(f"[Supervisor] killed extra outbox pid={pid}")
                except Exception:
                    pass


def main() -> int:
    lock = _acquire_supervisor_lock()
    lock_fd = lock["fd"]
    _singleton_sock = lock["sock"]  # noqa: F841 — must stay referenced
    env = _env()
    # Force single outbox whenever luxury building is installed.
    if (ROOT / "luxury_building.env").exists():
        env["TELEGRAM_SINGLE_OUTBOX"] = "1"
    # Delay fallbacks so bacbo can take WAL ownership / finish boot before readers attach.
    fallbacks_enabled = env.get("FALLBACKS_ENABLED", "1").strip() not in ("0", "false", "False", "no")
    single_outbox = env.get("TELEGRAM_SINGLE_OUTBOX", "1").strip() not in ("0", "false", "False", "no")
    fallback_delay = float(env.get("FALLBACK_START_DELAY_SECS", "20"))
    boot_t0 = time.time()
    processes: dict[str, tuple[list[str], subprocess.Popen | _AdoptedProc | None, float]] = {
        "bot_live": ([sys.executable, "-u", str(ROOT / "bacbo_royal_complete.py")], None, 0.0),
    }
    existing_pids = _find_bacbo_pids()
    if existing_pids:
        keep = min(existing_pids)
        print(f"[Supervisor] adopting existing bacbo pid={keep} (seen={existing_pids})")
        processes["bot_live"] = (processes["bot_live"][0], _AdoptedProc(keep), time.time())
        # Kill extras immediately
        for pid in existing_pids:
            if pid != keep:
                try:
                    os.kill(pid, signal.SIGKILL)
                    print(f"[Supervisor] killed extra bacbo at boot pid={pid}")
                except Exception:
                    pass

    if fallbacks_enabled:
        if single_outbox and (BOT / "telegram_outbox.py").exists():
            processes["telegram_outbox"] = (
                [sys.executable, "-u", str(BOT / "telegram_outbox.py")],
                None,
                0.0,
            )
        else:
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
    env["TELEGRAM_SINGLE_OUTBOX"] = "1" if single_outbox else "0"

    print("[Supervisor] starting. Logs in /home/runner/workspace/logs/")
    print(
        f"[Supervisor] pid={os.getpid()} lock={LOCK_PATH} "
        f"fallbacks_enabled={fallbacks_enabled} "
        f"single_outbox={single_outbox} fallback_start_delay_secs={fallback_delay}"
    )
    if single_outbox:
        _kill_pat("fallback_signal_sender.py")
        _kill_pat("fallback_result_sender.py")
        _kill_pat("telegram_outbox.py")

    def _is_delayed_sender(name: str) -> bool:
        return name.startswith("fallback") or name == "telegram_outbox"

    def _bacbo_alive_secs() -> float:
        """How long the current bacbo process has been up (0 if none)."""
        pid = _find_bacbo_pid()
        if not pid:
            return 0.0
        try:
            # /proc/<pid>/stat field 22 = starttime (clock ticks); use mtime of /proc/pid
            st = Path(f"/proc/{pid}").stat()
            return max(0.0, time.time() - st.st_ctime)
        except Exception:
            return 0.1  # exists but age unknown — treat as alive

    def _dump_bot_live_tail(reason: str) -> None:
        try:
            logp = LOG_DIR / "bot_live.log"
            if not logp.is_file():
                print(f"[Supervisor] {reason}: no bot_live.log yet")
                return
            lines = logp.read_text(encoding="utf-8", errors="ignore").splitlines()
            # Prefer lines after the newest supervisor start marker
            last = -1
            for i, ln in enumerate(lines):
                if "supervisor starting bot_live" in ln:
                    last = i
            chunk = lines[last + 1 :] if last >= 0 else lines[-40:]
            print(f"[Supervisor] {reason}: bot_live tail ({len(chunk)} lines)")
            for ln in chunk[-40:]:
                print(ln)
        except Exception as exc:
            print(f"[Supervisor] {reason}: log dump fail {exc!r}")

    bacbo_ready_secs = float(env.get("BACBO_READY_SECS", "45") or "45")
    bot_live_fails = 0

    try:
        tick = 0
        while True:
            for name, (cmd, proc, last_start) in list(processes.items()):
                if proc is None or proc.poll() is not None:
                    # Outbox/fallbacks: wait boot delay AND bacbo healthy (session owner).
                    if _is_delayed_sender(name):
                        if (time.time() - boot_t0) < fallback_delay:
                            continue
                        alive = _bacbo_alive_secs()
                        if alive < bacbo_ready_secs:
                            if tick % 2 == 0:
                                print(
                                    f"[Supervisor] hold {name}: bacbo_alive={alive:.0f}s "
                                    f"< ready={bacbo_ready_secs:.0f}s"
                                )
                            continue
                    if name == "bot_live":
                        existing = _find_bacbo_pid()
                        if existing:
                            print(f"[Supervisor] re-adopting bacbo pid={existing}")
                            processes[name] = (cmd, _AdoptedProc(existing), time.time())
                            bot_live_fails = 0
                            continue
                        if proc is not None and proc.poll() is not None:
                            bot_live_fails += 1
                            _dump_bot_live_tail(f"bot_live exited (fail#{bot_live_fails})")
                    # Back off harder when bacbo keeps dying
                    min_gap = 10.0 if name != "bot_live" else min(60.0, 10.0 + 5.0 * bot_live_fails)
                    if time.time() - last_start < min_gap:
                        time.sleep(min_gap - (time.time() - last_start))
                    print(f"[Supervisor] starting/restarting {name}")
                    proc = _start(name, cmd, env)
                    processes[name] = (cmd, proc, time.time())
            tick += 1
            if tick % 3 == 0:  # ~15s
                _reap_duplicates(single_outbox=single_outbox)
            time.sleep(5)
    except KeyboardInterrupt:
        print("[Supervisor] stopping")
        for _, proc, _ in processes.values():
            _stop(proc)
        try:
            os.close(lock_fd)
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
