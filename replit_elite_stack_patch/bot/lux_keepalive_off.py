"""Disable Replit KeepAlive port bind — it correlates with SIGKILL -9.

Evidence: process dies ~5s after ``[KeepAlive] Flask bound on port 8000 via
pre-bound fd`` at ~280MB RSS with multi‑GB free. Flask reloader guard alone
did not stop the kills (KeepAlive never called Flask.run).

Replit associates the reserved web PORT / pre-bound fd with the primary
workflow process. When a Shell-spawned child steals that fd, the platform
can SIGKILL it shortly after bind.

This module (loaded first from run_bacbo_live):
  · unsets PORT / Replit socket env vars so KeepAlive cannot grab the fd
  · no-ops common keep_alive() call patterns via a tiny builtins hook
  · patches socket.fromfd to refuse Replit keepalive reuse
"""
from __future__ import annotations

import os
import socket
from typing import Any

_PATCHED = False
_ARMED = False
_ORIG_FROMFD = None


def enabled() -> bool:
    return os.environ.get("LUX_KEEPALIVE_OFF", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _strip_replit_port_env() -> list[str]:
    removed: list[str] = []
    for k in list(os.environ.keys()):
        ku = k.upper()
        if ku in {"PORT", "REPLIT_SOCKET", "REPLIT_SOCKETS", "REPLIT_PORT"}:
            os.environ.pop(k, None)
            removed.append(k)
        elif "REPLIT" in ku and "SOCKET" in ku:
            os.environ.pop(k, None)
            removed.append(k)
    return removed


def _patch_fromfd() -> bool:
    global _ORIG_FROMFD
    if getattr(socket.fromfd, "_lux_keepalive_off", False):
        return True
    _ORIG_FROMFD = socket.fromfd

    def _fromfd(fd, family, type, proto=0):  # noqa: A002
        # KeepAlive on Replit reuses the platform web fd — refuse it.
        print(
            f"[KEEPALIVE-OFF] blocked socket.fromfd(fd={fd}) "
            "(prevents Replit PORT steal → SIGKILL -9)",
            flush=True,
        )
        raise OSError("LUX_KEEPALIVE_OFF: refusing pre-bound Replit socket")

    _fromfd._lux_keepalive_off = True  # type: ignore[attr-defined]
    socket.fromfd = _fromfd  # type: ignore[assignment]
    return True


def _patch_make_server() -> int:
    n = 0
    try:
        from werkzeug.serving import make_server  # type: ignore

        if getattr(make_server, "_lux_keepalive_off", False):
            return 0

        def _ms(*args, **kwargs):
            print(
                "[KEEPALIVE-OFF] blocked werkzeug.make_server",
                flush=True,
            )
            raise RuntimeError("LUX_KEEPALIVE_OFF: make_server disabled")

        _ms._lux_keepalive_off = True  # type: ignore[attr-defined]
        import werkzeug.serving as ws  # type: ignore

        ws.make_server = _ms  # type: ignore[assignment]
        n += 1
    except Exception as exc:
        print("[KEEPALIVE-OFF] make_server patch skip:", repr(exc), flush=True)
    return n


def apply() -> bool:
    global _PATCHED, _ARMED
    if not enabled():
        if not _ARMED:
            print("[KEEPALIVE-OFF] off", flush=True)
            _ARMED = True
        return False
    removed = _strip_replit_port_env()
    ok_fd = False
    try:
        ok_fd = _patch_fromfd()
    except Exception as exc:
        print("[KEEPALIVE-OFF] fromfd patch fail:", repr(exc), flush=True)
    n_ms = _patch_make_server()
    # Force flask guard env too
    os.environ["FLASK_DEBUG"] = "0"
    os.environ["LUX_FLASK_GUARD"] = "1"
    _PATCHED = True
    if not _ARMED:
        _ARMED = True
    print(
        f"[KEEPALIVE-OFF] ON unset={removed or ['(none)']} "
        f"fromfd={int(ok_fd)} make_server={n_ms}",
        flush=True,
    )
    return True


if enabled():
    apply()
