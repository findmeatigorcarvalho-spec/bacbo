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
    "PACKER_HOLD_UNTIL_REAL",
    "PRINTED_SECS_ARE_OUTCOME",
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
    "PACKER_HOLD_UNTIL_REAL",
    "PRINTED_SECS_ARE_OUTCOME",
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
        env["EDGE_LUXURY_FLOOR_GATE"] = "0"
        env.setdefault("FALLBACK_SEND_BLOCKED", "0")
        env.setdefault("FALLBACKS_ENABLED", "1")
        env.setdefault("TELEGRAM_SINGLE_OUTBOX", "1")
        env.setdefault("TELEGRAM_COUNTDOWN_PEER", "UNIQUE_g1")
        env.setdefault("GUNIQUE_PEER", "UNIQUE_g1")
    else:
        env.setdefault("EDGE_POLICY_MODE", "shadow")
    env.setdefault("EDGE_LEGACY_355_WARN", "1")
    # Engine hour gating clock — never retune for card display.
    env.setdefault("BOT_TZ", "America/Sao_Paulo")
    env.setdefault("TELEGRAM_COUNTDOWN_PEER", "UNIQUE_g1")
    env.setdefault("GUNIQUE_PEER", "UNIQUE_g1")
    # Kill G2 ESTUDO study floods + identical/near-identical spam on UNIQUE_g1
    env.setdefault("LUX_BLOCK_ESTUDO", "1")
    env.setdefault("LUX_G2_COALITION_TO_G1", "1")
    env.setdefault("OUTBOX_RESULT_LOOKBACK_HOURS", "6")
    env.setdefault("OUTBOX_SIGNAL_LOOKBACK_HOURS", "6")
    env.setdefault("LUX_CHAT_WATCH_CALL_ON_CONNECT", "1")
    env.setdefault("LUX_CHAT_WATCH_CALL_EARLY_SECS", "12")
    env.setdefault("LUX_SEND_DEDUP_SECS", "12")
    env.setdefault("TELEGRAM_TRASH_BLOCK", "1")
    env.setdefault("LUX_CHAT_WATCHDOG", "1")
    # CALL wrap OFF at boot (subscribe-safe); armed after settle by outbox/watchdog
    env.setdefault("LUX_CHAT_WATCH_CALL", "0")
    env.setdefault("LUX_CHAT_WATCH_CALL_AFTER_SETTLE", "1")
    # EMANATION LAWS
    env.setdefault("EMANATION_LAWS", "1")
    env.setdefault("COLOR_TRUTH_FACTUAL", "1")
    env.setdefault("SIGNAL_BUNDLE_VERTICAL", "1")
    env.setdefault("CHAT_HERMETIC", "1")
    env.setdefault("RESULT_REPLY_TO_FIRE", "1")
    # HUB free-propose → orchestrate (no hour/WR/volume mute on propose)
    env.setdefault("HUB_MAX", "1")
    env.setdefault("HUB_ORCHESTRATOR", "1")
    env.setdefault("VOLUME_MODE", "EXPLOSION")
    env.setdefault("V2_PROPOSERS", "1")
    env.setdefault("FREE_PROPOSE", "1")
    env.setdefault("LUXURY_NO_HOUR_BLOCKS", "1")
    # FORCE — a prior setdefault(1) when luxury_building.env existed kept the
    # floor gate ON and starved volume. Overwrite, do not setdefault.
    env["EDGE_LUXURY_FLOOR_GATE"] = "0"
    env["ROLLING_WR_MUTE_SECS"] = "0"
    env["AUTO_QUARANTINE_SECS"] = "0"
    try:
        from lux_free_volume import apply_env as _free_env

        _free_env(env)
    except Exception as exc:
        print("[Supervisor] free-volume skip:", repr(exc))
        env["LUX_FREE_VOLUME"] = "1"
        env["HUB_GUNIQUE_TRUST_MIN"] = "0"
        env["HUB_CATCHUP_MAX_PER_TICK"] = "24"
        env["LUX_SEND_DEDUP_SECS"] = "12"
    env.setdefault("FIRE_RESULT_LAW", "1")
    env.setdefault("RESULT_ATTACH_IMMEDIATE", "1")
    env.setdefault("HUB_OUTBOX_RESULT_CARDS", "1")
    env.setdefault("BACBO_READY_SECS", "12")
    env.setdefault("FALLBACK_START_DELAY_SECS", "15")
    env.setdefault("TELEGRAM_OUTBOX_INLINE", "1")
    env.setdefault("HUB_IMPACT_LEARNER", "1")
    env.setdefault("LUX_SKIP_RESOLVE_USERNAME", "1")
    # FORCE session/outbox settles — hub_max_boot used to pin stale 12/55 and win
    env["TELEGRAM_OUTBOX_INLINE"] = "1"
    env["TELEGRAM_OUTBOX_STARTUP_PING"] = "0"
    env["OUTBOX_INLINE_SETTLE_SECS"] = env.get("OUTBOX_INLINE_SETTLE_SECS") or "70"
    if float(env.get("OUTBOX_INLINE_SETTLE_SECS") or "0") < 60:
        env["OUTBOX_INLINE_SETTLE_SECS"] = "70"
    env["BACBO_SESSION_SETTLE_SECS"] = env.get("BACBO_SESSION_SETTLE_SECS") or "28"
    if float(env.get("BACBO_SESSION_SETTLE_SECS") or "0") < 20:
        env["BACBO_SESSION_SETTLE_SECS"] = "28"
    env["BACBO_AUTHKEY_SETTLE_SECS"] = env.get("BACBO_AUTHKEY_SETTLE_SECS") or "40"
    if float(env.get("BACBO_AUTHKEY_SETTLE_SECS") or "0") < 30:
        env["BACBO_AUTHKEY_SETTLE_SECS"] = "40"
    env["LUX_SESSION_GUARD"] = "1"
    env.setdefault("LUX_SESSION_RECONNECTS", "12")
    env.setdefault("LUX_DIALOG_WARM", "cache")
    env["LUX_FLASK_GUARD"] = "1"
    env["LUX_KEEPALIVE_OFF"] = "1"
    env["FLASK_DEBUG"] = "0"
    env["FLASK_ENV"] = "production"
    # Prevent Werkzeug reloader from treating this as a monitor process
    env["WERKZEUG_RUN_MAIN"] = "true"
    # Supervisor itself should not hold the web PORT either
    for k in list(env.keys()):
        ku = k.upper()
        if ku in {"PORT", "REPLIT_SOCKET", "REPLIT_SOCKETS", "REPLIT_PORT"} or (
            "REPLIT" in ku and "SOCKET" in ku
        ):
            env.pop(k, None)
    env["PYTHONPATH"] = f"{BOT}:{ROOT}:{env.get('PYTHONPATH', '')}"
    print(
        f"[Supervisor] EDGE_POLICY_MODE={env.get('EDGE_POLICY_MODE')} "
        f"FLOOR_GATE={env.get('EDGE_LUXURY_FLOOR_GATE')} "
        f"FALLBACKS={env.get('FALLBACKS_ENABLED')} "
        f"OUTBOX={env.get('TELEGRAM_SINGLE_OUTBOX')} "
        f"CD_PEER={env.get('TELEGRAM_COUNTDOWN_PEER')} "
        f"SETTLE={env.get('BACBO_SESSION_SETTLE_SECS')}/"
        f"{env.get('OUTBOX_INLINE_SETTLE_SECS')} "
        f"DIALOG_WARM={env.get('LUX_DIALOG_WARM')}"
    )
    return env


def _start(name: str, cmd: list[str], env: dict[str, str]) -> subprocess.Popen:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    fh = open(log_path, "ab", buffering=0)
    fh.write(f"\n--- supervisor starting {name} at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode())
    # Child env: never inherit Replit web PORT/socket (KeepAlive steal → SIGKILL -9)
    child_env = dict(env)
    for k in list(child_env.keys()):
        ku = k.upper()
        if ku in {"PORT", "REPLIT_SOCKET", "REPLIT_SOCKETS", "REPLIT_PORT"} or (
            "REPLIT" in ku and "SOCKET" in ku
        ):
            child_env.pop(k, None)
    child_env["LUX_KEEPALIVE_OFF"] = "1"
    child_env["LUX_FLASK_GUARD"] = "1"
    child_env["FLASK_DEBUG"] = "0"
    # Stay in supervisor session — new sessions were dying under Replit Shell
    return subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=child_env,
        stdout=fh,
        stderr=subprocess.STDOUT,
        start_new_session=False,
        close_fds=True,
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


def _pid_cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        return raw.replace(b"\x00", b" ").decode("utf-8", "ignore")
    except Exception:
        return ""


def _is_gated_bacbo(pid: int) -> bool:
    """True only when launcher preloaded ESTUDO/HUB gates."""
    cmd = _pid_cmdline(pid)
    return "run_bacbo_live.py" in cmd


def _find_bacbo_pids() -> list[int]:
    # Prefer gated launcher; bare megafile alone has no ESTUDO preload.
    gated = _python_pids_with("run_bacbo_live.py")
    bare = _python_pids_with("bacbo_royal_complete.py")
    seen: set[int] = set()
    out: list[int] = []
    for p in gated + bare:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _find_gated_bacbo_pids() -> list[int]:
    return [p for p in _find_bacbo_pids() if _is_gated_bacbo(p)]


def _find_bacbo_pid() -> int | None:
    gated = _find_gated_bacbo_pids()
    if gated:
        return gated[0]
    pids = _find_bacbo_pids()
    return pids[0] if pids else None


def _kill_pat(pat: str) -> None:
    for pid in _python_pids_with(pat):
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    time.sleep(0.5)
    for pid in _python_pids_with(pat):
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass


def _session_settlers() -> None:
    """Kill every other MTProto user of the same StringSession."""
    for pat in (
        "telegram_outbox.py",
        "fallback_signal_sender.py",
        "fallback_result_sender.py",
        "museum_unique_poster.py",
        "museum_first5_poster.py",
        "museum_chrono_poster.py",
        # A bare megafile has no pre-main watchdog and is a known ESTUDO
        # flood vector. The supervised child is run_bacbo_live.py, not this.
        "bacbo_royal_complete.py",
    ):
        _kill_pat(pat)


def _reap_duplicates(
    *,
    single_outbox: bool,
    keep_bacbo_pid: int | None = None,
) -> None:
    """Kill orphan bacbos/outboxes — NEVER kill the supervised bot_live PID.

    Old bug: keep=min(pids) killed the freshly supervised child while a dying
    older copy still lingered → restart thrash → bacbo_alive never reached
    ready secs → outbox never started.
    """
    bacbos = _find_bacbo_pids()
    if bacbos:
        if keep_bacbo_pid and keep_bacbo_pid in bacbos:
            keep = keep_bacbo_pid
        else:
            keep = min(bacbos)
        for pid in bacbos:
            if pid == keep:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"[Supervisor] SIGTERM orphan bacbo pid={pid} keep={keep}")
            except Exception:
                pass
        time.sleep(1.0)
        for pid in _find_bacbo_pids():
            if pid == keep:
                continue
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"[Supervisor] killed orphan bacbo pid={pid} keep={keep}")
            except Exception:
                pass
    if single_outbox:
        _session_settlers()
        opids = _python_pids_with("telegram_outbox.py")
        if len(opids) > 1:
            keep_o = min(opids)
            for pid in opids:
                if pid == keep_o:
                    continue
                try:
                    os.kill(pid, signal.SIGKILL)
                    print(f"[Supervisor] killed extra outbox pid={pid}")
                except Exception:
                    pass


def _session_settle_secs(*, authkey_flavor: bool = False) -> float:
    base = float(os.environ.get("BACBO_SESSION_SETTLE_SECS", "28") or "28")
    if authkey_flavor:
        base = max(base, float(os.environ.get("BACBO_AUTHKEY_SETTLE_SECS", "40") or "40"))
    return max(12.0, base)


def _kill_all_bacbo_and_wait(
    timeout: float = 15.0,
    *,
    authkey_flavor: bool = False,
) -> None:
    """Graceful then hard clear — SIGKILL-only leaves Telegram AuthKey held.

    Flow: SIGTERM → wait → SIGKILL → extra settle so MTProto releases the key
    before the next connect (prevents silent AuthKeyDuplicated exits).
    """
    _session_settlers()
    pids = _find_bacbo_pids()
    if not pids:
        settle = _session_settle_secs(authkey_flavor=authkey_flavor)
        # Still settle — prior ONE_CMD/pkill may have left AuthKey held with no PID
        print(f"[Supervisor] no bacbo PIDs — AuthKey settle {settle:.0f}s anyway")
        time.sleep(settle)
        return
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[Supervisor] SIGTERM bacbo pid={pid}")
        except Exception:
            pass
    # Let Telethon disconnect cleanly
    deadline = time.time() + min(8.0, max(4.0, timeout * 0.5))
    while time.time() < deadline:
        if not _find_bacbo_pids():
            break
        time.sleep(0.3)
    for pid in _find_bacbo_pids():
        try:
            os.kill(pid, signal.SIGKILL)
            print(f"[Supervisor] SIGKILL bacbo pid={pid}")
        except Exception:
            pass
    # Critical: wait for Telegram to drop the old auth-key session
    settle = _session_settle_secs(authkey_flavor=authkey_flavor)
    print(f"[Supervisor] session settle {settle:.0f}s (AuthKey release)")
    time.sleep(settle)
    left = _find_bacbo_pids()
    if left:
        print(f"[Supervisor] WARN bacbo still alive after kill: {left}")


def _bacbo_authenticated_in_log() -> bool:
    """True when current bot_live boot reached Telegram auth (session owner)."""
    try:
        logp = LOG_DIR / "bot_live.log"
        if not logp.is_file():
            return False
        lines = logp.read_text(encoding="utf-8", errors="ignore").splitlines()
        last = -1
        for i, ln in enumerate(lines):
            if "supervisor starting bot_live" in ln:
                last = i
        chunk = lines[last + 1 :] if last >= 0 else lines[-80:]
        for ln in chunk:
            if "Authenticated as" in ln or "dialogs warmed" in ln:
                return True
    except Exception:
        pass
    return False


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
    fallback_delay = float(env.get("FALLBACK_START_DELAY_SECS", "15"))
    boot_t0 = time.time()
    # Prefer launcher so ESTUDO/dedup gate loads BEFORE bacbo main (EOF binds never run).
    launcher = BOT / "run_bacbo_live.py"
    bot_cmd = (
        [sys.executable, "-u", str(launcher)]
        if launcher.is_file()
        else [sys.executable, "-u", str(ROOT / "bacbo_royal_complete.py")]
    )
    processes: dict[str, tuple[list[str], subprocess.Popen | _AdoptedProc | None, float]] = {
        "bot_live": (bot_cmd, None, 0.0),
    }
    print(f"[Supervisor] bot_live cmd={' '.join(bot_cmd)}")
    existing_pids = _find_bacbo_pids()
    gated_pids = _find_gated_bacbo_pids()
    if existing_pids and not gated_pids:
        # Bare bacbo_royal_complete without run_bacbo_live = ESTUDO flood vector.
        print(
            f"[Supervisor] REFUSE adopt ungated bacbo {existing_pids} "
            f"— kill + relaunch via run_bacbo_live",
            flush=True,
        )
        for pid in existing_pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        time.sleep(2.0)
        for pid in existing_pids:
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"[Supervisor] killed ungated bacbo pid={pid}", flush=True)
            except Exception:
                pass
        settle = _session_settle_secs(authkey_flavor=True)
        print(f"[Supervisor] AuthKey settle after ungated kill {settle:.0f}s", flush=True)
        time.sleep(settle)
        existing_pids = []
        gated_pids = []
    if gated_pids:
        keep = min(gated_pids)
        print(f"[Supervisor] adopting GATED bacbo pid={keep} (seen={existing_pids})")
        processes["bot_live"] = (processes["bot_live"][0], _AdoptedProc(keep), time.time())
        # Kill extras immediately (including any bare megafile siblings)
        for pid in existing_pids:
            if pid != keep:
                try:
                    os.kill(pid, signal.SIGKILL)
                    print(f"[Supervisor] killed extra bacbo at boot pid={pid}")
                except Exception:
                    pass

    outbox_inline = env.get("TELEGRAM_OUTBOX_INLINE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    # Always kill standalone outbox when inline — second session AuthKey-kills bacbo
    if outbox_inline:
        _session_settlers()
        print(
            "[Supervisor] TELEGRAM_OUTBOX_INLINE=1 — outbox runs on bacbo client "
            "(no second MTProto session)"
        )

    if fallbacks_enabled:
        if single_outbox and (BOT / "telegram_outbox.py").exists() and not outbox_inline:
            processes["telegram_outbox"] = (
                [sys.executable, "-u", str(BOT / "telegram_outbox.py")],
                None,
                0.0,
            )
        elif not single_outbox:
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
    env.setdefault("BACBO_SESSION_SETTLE_SECS", "28")
    env.setdefault("BACBO_AUTHKEY_SETTLE_SECS", "40")
    env.setdefault("OUTBOX_INLINE_SETTLE_SECS", "70")
    env.setdefault("LUX_SESSION_GUARD", "1")

    print("[Supervisor] starting. Logs in /home/runner/workspace/logs/")
    print(
        f"[Supervisor] pid={os.getpid()} lock={LOCK_PATH} "
        f"fallbacks_enabled={fallbacks_enabled} "
        f"single_outbox={single_outbox} fallback_start_delay_secs={fallback_delay}"
    )
    if single_outbox or outbox_inline:
        _session_settlers()
    # Fresh supervisor boot after ONE_CMD pkill: AuthKey may still be held.
    # Cap cold-start — ONE_CMD already waited ~35s; don't stack another full 40s
    # of downtime (false BACBO_DOWN during settle windows).
    if processes["bot_live"][1] is None:
        settle0 = min(20.0, _session_settle_secs(authkey_flavor=False))
        print(
            f"[Supervisor] cold-start AuthKey settle {settle0:.0f}s "
            "(ONE_CMD already pre-settled)"
        )
        time.sleep(settle0)

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

    bacbo_ready_secs = float(env.get("BACBO_READY_SECS", "12") or "12")
    bot_live_fails = 0
    bot_live_grace_until = 0.0  # no orphan-reap during subscribe boot

    def _owned_bacbo_pid() -> int | None:
        proc = processes.get("bot_live", (None, None, 0.0))[1]
        if proc is None:
            return None
        if proc.poll() is not None:
            return None
        return int(getattr(proc, "pid", 0) or 0) or None

    def _bacbo_ready_for_outbox() -> tuple[bool, str]:
        alive = _bacbo_alive_secs()
        auth = _bacbo_authenticated_in_log()
        # Authenticated + ≥8s is enough; else wait full ready secs.
        if auth and alive >= min(8.0, bacbo_ready_secs):
            return True, f"auth+alive={alive:.0f}s"
        if alive >= bacbo_ready_secs:
            return True, f"alive={alive:.0f}s"
        return False, f"bacbo_alive={alive:.0f}s auth={int(auth)} ready={bacbo_ready_secs:.0f}s"

    try:
        tick = 0
        while True:
            for name, (cmd, proc, last_start) in list(processes.items()):
                if proc is None or proc.poll() is not None:
                    # Outbox/fallbacks: wait boot delay AND bacbo healthy (session owner).
                    if _is_delayed_sender(name):
                        if (time.time() - boot_t0) < fallback_delay:
                            continue
                        ready, why = _bacbo_ready_for_outbox()
                        if not ready:
                            if tick % 2 == 0:
                                print(f"[Supervisor] hold {name}: {why}")
                            continue
                        print(f"[Supervisor] release {name}: {why}")
                    if name == "bot_live":
                        existing = _find_bacbo_pid()
                        gated = _find_gated_bacbo_pids()
                        owned = None
                        if proc is not None:
                            owned = int(getattr(proc, "pid", 0) or 0) or None
                        # Prefer re-adopt only GATED launcher — never bare megafile
                        adopt_pid = None
                        if gated:
                            for g in gated:
                                if g != owned:
                                    adopt_pid = g
                                    break
                        if adopt_pid:
                            print(f"[Supervisor] re-adopting GATED bacbo pid={adopt_pid}")
                            processes[name] = (cmd, _AdoptedProc(adopt_pid), time.time())
                            bot_live_fails = 0
                            bot_live_grace_until = time.time() + 45.0
                            continue
                        if existing and existing != owned and not _is_gated_bacbo(existing):
                            print(
                                f"[Supervisor] skip re-adopt ungated bacbo pid={existing}",
                                flush=True,
                            )
                            try:
                                os.kill(existing, signal.SIGKILL)
                            except Exception:
                                pass
                        if proc is not None and proc.poll() is not None:
                            bot_live_fails += 1
                            code = proc.poll()
                            authkey_death = False
                            sigkill = code == -9 or code == 137
                            _dump_bot_live_tail(
                                f"bot_live exited (fail#{bot_live_fails} code={code})"
                            )
                            if sigkill:
                                print(
                                    "[Supervisor] SIGKILL code=-9 — not AuthKey. "
                                    "If RSS was ~200-400MB with free RAM: Flask/Werkzeug "
                                    "reloader or external pkill. Look for [FLASK-GUARD] "
                                    "+ rss_heartbeat in bot_live.log",
                                    flush=True,
                                )
                            # Highlight crash signatures
                            try:
                                logp = LOG_DIR / "bot_live.log"
                                tail = logp.read_text(encoding="utf-8", errors="ignore").splitlines()[-100:]
                                hits = [
                                    ln
                                    for ln in tail
                                    if any(
                                        k in ln
                                        for k in (
                                            "AuthKey",
                                            "SESSION-GUARD",
                                            "Traceback",
                                            "Error",
                                            "Killed",
                                            "MemoryError",
                                            "SystemExit",
                                            "EXITING",
                                            "got SIGTERM",
                                            "rss_heartbeat",
                                            "dialogs warm",
                                        )
                                    )
                                ]
                                for ln in hits[-16:]:
                                    print(f"[Supervisor] crash-sig: {ln}")
                                authkey_death = any(
                                    "AuthKey" in ln or "auth-key" in ln.lower()
                                    for ln in hits
                                )
                            except Exception:
                                pass
                            # Clear corpses once + long AuthKey settle (only after death)
                            _kill_all_bacbo_and_wait(
                                10.0,
                                authkey_flavor=(
                                    authkey_death or bot_live_fails >= 2 or sigkill
                                ),
                            )
                            time.sleep(2.0)
                            if sigkill:
                                # Extra cool-down so we don't thrash into more OOM kills
                                cool = min(180.0, 60.0 + 30.0 * bot_live_fails)
                                print(
                                    f"[Supervisor] SIGKILL cool-down {cool:.0f}s",
                                    flush=True,
                                )
                                time.sleep(cool)
                        else:
                            # First start: just ensure no session thieves
                            _session_settlers()
                    # Back off harder when bacbo keeps dying
                    min_gap = (
                        10.0
                        if name != "bot_live"
                        else min(180.0, 25.0 + 15.0 * bot_live_fails)
                    )
                    if time.time() - last_start < min_gap:
                        time.sleep(min_gap - (time.time() - last_start))
                    print(f"[Supervisor] starting/restarting {name}")
                    proc = _start(name, cmd, env)
                    processes[name] = (cmd, proc, time.time())
                    if name == "bot_live":
                        # Long grace — subscribe of ~70 rooms + outbox settle
                        bot_live_grace_until = time.time() + 180.0
            tick += 1
            if tick % 4 == 0:  # ~20s
                if time.time() >= bot_live_grace_until:
                    _reap_duplicates(
                        single_outbox=single_outbox,
                        keep_bacbo_pid=_owned_bacbo_pid(),
                    )
            # Heartbeat so we know supervisor itself is alive
            if tick % 12 == 0:
                pid = _owned_bacbo_pid()
                print(
                    f"[Supervisor] heartbeat bacbo_pid={pid} "
                    f"alive={_bacbo_alive_secs():.0f}s fails={bot_live_fails}"
                )
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
