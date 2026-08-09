"""Guard against AuthKeyDuplicated / silent Telethon disconnect exits.

When supervisor/ONE_CMD kills bacbo, Telegram still holds the auth key briefly.
The next connect gets kicked → ``run_until_disconnected()`` returns → process
exits with no Traceback (BACBO_DIED_AFTER_BOOT).

This module:
  · retries connect on AuthKeyDuplicatedError
  · keeps the client alive after transient drops (reconnect loop on
    ``_run_until_disconnected``)
  · logs disconnect / SIGTERM so silent exits are visible
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import os
import signal
import sys
from typing import Any

_PATCHED = False
_ARMED = False
_SIGNALS = False


def enabled() -> bool:
    return os.environ.get("LUX_SESSION_GUARD", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _reconnect_budget() -> int:
    try:
        return max(1, int(os.environ.get("LUX_SESSION_RECONNECTS", "12") or "12"))
    except Exception:
        return 12


def _install_signal_logs() -> None:
    """Log SIGTERM/SIGINT — proves supervisor/ONE_CMD kills (vs silent Telethon exit)."""
    global _SIGNALS
    if _SIGNALS:
        return

    def _handler(signum: int, _frame: Any) -> None:
        name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        print(f"[SESSION-GUARD] got {name} — shutting down", flush=True)
        signal.signal(signum, signal.SIG_DFL)
        try:
            os.kill(os.getpid(), signum)
        except Exception:
            sys.exit(128 + int(signum))

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handler)
        except Exception:
            pass
    _SIGNALS = True
    print("[SESSION-GUARD] SIGTERM/SIGINT log ON", flush=True)


async def _safe_connected(client: Any) -> bool:
    try:
        return bool(client.is_connected())
    except Exception:
        return False


def patch_telethon() -> bool:
    global _PATCHED
    if _PATCHED:
        return True
    try:
        from telethon import TelegramClient  # type: ignore
        from telethon.errors import AuthKeyDuplicatedError  # type: ignore
    except Exception as exc:
        print("[SESSION-GUARD] telethon missing:", repr(exc), flush=True)
        return False

    orig_connect = TelegramClient.connect
    if getattr(orig_connect, "_lux_session_guard", False):
        _PATCHED = True
        return True

    @functools.wraps(orig_connect)
    async def _connect(self: Any, *args: Any, **kwargs: Any):
        # Longer backoff — Telegram can hold AuthKey 20–40s after hard kill
        delays = (0, 12, 25, 40, 55)
        last_exc: Exception | None = None
        for i, d in enumerate(delays):
            if d:
                print(f"[SESSION-GUARD] connect retry #{i} after {d}s", flush=True)
                await asyncio.sleep(d)
            try:
                result = await orig_connect(self, *args, **kwargs)
                if i:
                    print(f"[SESSION-GUARD] connect OK on retry #{i}", flush=True)
                else:
                    print("[SESSION-GUARD] connect OK", flush=True)
                return result
            except AuthKeyDuplicatedError as exc:
                last_exc = exc
                print(
                    "[SESSION-GUARD] AuthKeyDuplicatedError — "
                    "old session still held; waiting before retry",
                    flush=True,
                )
            except Exception as exc:
                msg = repr(exc).lower()
                if "authkey" in msg or "authorization key" in msg:
                    last_exc = exc
                    print("[SESSION-GUARD] auth-key failure:", repr(exc), flush=True)
                    continue
                raise
        print("[SESSION-GUARD] connect giving up:", repr(last_exc), flush=True)
        if last_exc:
            raise last_exc
        raise RuntimeError("SESSION-GUARD connect failed")

    _connect._lux_session_guard = True  # type: ignore[attr-defined]
    TelegramClient.connect = _connect  # type: ignore[method-assign]

    # Log disconnects so silent exits are visible
    try:
        orig_disc = TelegramClient.disconnect

        @functools.wraps(orig_disc)
        async def _disconnect(self: Any, *args: Any, **kwargs: Any):
            print("[SESSION-GUARD] client.disconnect() called", flush=True)
            return await orig_disc(self, *args, **kwargs)

        if asyncio.iscoroutinefunction(orig_disc):
            _disconnect._lux_session_guard = True  # type: ignore[attr-defined]
            TelegramClient.disconnect = _disconnect  # type: ignore[method-assign]
    except Exception as exc:
        print("[SESSION-GUARD] disconnect wrap skip:", repr(exc), flush=True)

    # Keep-alive: wrap async _run_until_disconnected (not sync run_until_disconnected)
    try:
        orig_inner = getattr(TelegramClient, "_run_until_disconnected", None)
        if orig_inner is not None and not getattr(orig_inner, "_lux_session_guard", False):

            @functools.wraps(orig_inner)
            async def _inner(self: Any, *args: Any, **kwargs: Any):
                budget = _reconnect_budget()
                for attempt in range(budget):
                    if not await _safe_connected(self):
                        print(
                            f"[SESSION-GUARD] pre-rud connect "
                            f"(attempt {attempt + 1}/{budget})",
                            flush=True,
                        )
                        try:
                            await self.connect()
                        except Exception as exc:
                            print(
                                "[SESSION-GUARD] pre-rud connect fail:",
                                repr(exc),
                                flush=True,
                            )
                            await asyncio.sleep(min(60, 10 + 5 * attempt))
                            continue
                    print(
                        f"[SESSION-GUARD] _run_until_disconnected "
                        f"(attempt {attempt + 1}/{budget})",
                        flush=True,
                    )
                    try:
                        result = orig_inner(self, *args, **kwargs)
                        if inspect.isawaitable(result):
                            result = await result
                    except AuthKeyDuplicatedError as exc:
                        print(
                            "[SESSION-GUARD] AuthKey during rud:",
                            repr(exc),
                            flush=True,
                        )
                        await asyncio.sleep(min(60, 15 + 5 * attempt))
                        continue
                    except Exception as exc:
                        msg = repr(exc).lower()
                        if "authkey" in msg or "authorization key" in msg:
                            print(
                                "[SESSION-GUARD] auth-key during rud:",
                                repr(exc),
                                flush=True,
                            )
                            await asyncio.sleep(min(60, 15 + 5 * attempt))
                            continue
                        print(
                            "[SESSION-GUARD] rud raised:",
                            repr(exc),
                            flush=True,
                        )
                        raise
                    if await _safe_connected(self):
                        print(
                            "[SESSION-GUARD] rud returned but still connected",
                            flush=True,
                        )
                        return result
                    wait = min(45, 12 + 4 * attempt)
                    print(
                        "[SESSION-GUARD] rud returned (disconnected) — "
                        f"reconnect in {wait}s ({attempt + 1}/{budget})",
                        flush=True,
                    )
                    await asyncio.sleep(wait)
                print(
                    "[SESSION-GUARD] reconnect budget exhausted — exiting rud",
                    flush=True,
                )
                return None

            _inner._lux_session_guard = True  # type: ignore[attr-defined]
            TelegramClient._run_until_disconnected = _inner  # type: ignore[method-assign]
            print("[SESSION-GUARD] _run_until_disconnected reconnect ON", flush=True)
        else:
            # Fallback: wrap public run_until_disconnected carefully (sync/async)
            orig_rud = TelegramClient.run_until_disconnected
            if not getattr(orig_rud, "_lux_session_guard", False):

                def _rud(self: Any, *args: Any, **kwargs: Any):
                    async def _loop():
                        budget = _reconnect_budget()
                        for attempt in range(budget):
                            if not await _safe_connected(self):
                                try:
                                    await self.connect()
                                except Exception as exc:
                                    print(
                                        "[SESSION-GUARD] rud-connect fail:",
                                        repr(exc),
                                        flush=True,
                                    )
                                    await asyncio.sleep(min(60, 10 + 5 * attempt))
                                    continue
                            print(
                                f"[SESSION-GUARD] run_until_disconnected "
                                f"(attempt {attempt + 1}/{budget})",
                                flush=True,
                            )
                            result = orig_rud(self, *args, **kwargs)
                            if inspect.isawaitable(result):
                                result = await result
                            if await _safe_connected(self):
                                return result
                            wait = min(45, 12 + 4 * attempt)
                            print(
                                "[SESSION-GUARD] rud returned — "
                                f"reconnect in {wait}s",
                                flush=True,
                            )
                            await asyncio.sleep(wait)
                        return None

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            return _loop()
                        return loop.run_until_complete(_loop())
                    except RuntimeError:
                        return asyncio.run(_loop())

                _rud._lux_session_guard = True  # type: ignore[attr-defined]
                TelegramClient.run_until_disconnected = _rud  # type: ignore[method-assign]
                print("[SESSION-GUARD] run_until_disconnected reconnect ON", flush=True)
    except Exception as exc:
        print("[SESSION-GUARD] rud wrap skip:", repr(exc), flush=True)

    _PATCHED = True
    print("[SESSION-GUARD] AuthKey retry + disconnect log ON", flush=True)
    return True


def apply() -> bool:
    global _ARMED
    if not enabled():
        if not _ARMED:
            print("[SESSION-GUARD] off", flush=True)
            _ARMED = True
        return False
    _install_signal_logs()
    ok = patch_telethon()
    if not ok:
        try:
            import threading

            threading.Timer(1.0, patch_telethon).start()
            threading.Timer(3.0, patch_telethon).start()
        except Exception:
            pass
    if not _ARMED:
        _ARMED = True
    return True


if enabled():
    apply()
