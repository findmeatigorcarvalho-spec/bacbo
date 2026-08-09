"""Stop Flask/Werkzeug reloader from SIGKILL-ing bacbo mid-boot.

Replit KeepAlive often does ``app.run(...)`` in a thread. If ``debug=True``
or ``use_reloader=True``, Werkzeug's reloader watches the filesystem and
**SIGKILLs the whole process** when logs/cache/env files change during
subscribe — exit code **-9** at ~200–300MB RSS with gigabytes free.

This guard forces ``use_reloader=False`` / ``use_debugger=False`` on
Flask and Werkzeug entry points before KeepAlive starts.
"""
from __future__ import annotations

import os
from typing import Any

_PATCHED = False
_ARMED = False


def enabled() -> bool:
    return os.environ.get("LUX_FLASK_GUARD", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _force_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    out = dict(kwargs)
    out["use_reloader"] = False
    out["use_debugger"] = False
    # debug=True implies reloader on many Flask versions
    if out.get("debug"):
        out["debug"] = False
    return out


def patch() -> bool:
    global _PATCHED
    if _PATCHED:
        return True
    patched = 0

    # Flask.Flask.run
    try:
        from flask import Flask  # type: ignore

        orig = Flask.run
        if not getattr(orig, "_lux_flask_guard", False):

            def _run(self, *args, **kwargs):  # noqa: ANN001
                kwargs = _force_kwargs(kwargs)
                print(
                    "[FLASK-GUARD] Flask.run use_reloader=False "
                    "(prevents SIGKILL -9 on file change)",
                    flush=True,
                )
                return orig(self, *args, **kwargs)

            _run._lux_flask_guard = True  # type: ignore[attr-defined]
            Flask.run = _run  # type: ignore[method-assign]
            patched += 1
    except Exception as exc:
        print("[FLASK-GUARD] Flask patch skip:", repr(exc), flush=True)

    # werkzeug.serving.run_simple (underlying entry)
    try:
        import werkzeug.serving as ws  # type: ignore

        orig_rs = ws.run_simple
        if not getattr(orig_rs, "_lux_flask_guard", False):

            def _run_simple(*args, **kwargs):
                kwargs = _force_kwargs(kwargs)
                print(
                    "[FLASK-GUARD] werkzeug.run_simple use_reloader=False",
                    flush=True,
                )
                return orig_rs(*args, **kwargs)

            _run_simple._lux_flask_guard = True  # type: ignore[attr-defined]
            ws.run_simple = _run_simple  # type: ignore[assignment]
            patched += 1
    except Exception as exc:
        print("[FLASK-GUARD] werkzeug patch skip:", repr(exc), flush=True)

    # Neutralize reloader entry entirely (file-watch → SIGKILL -9)
    try:
        import werkzeug._reloader as rel  # type: ignore

        if not getattr(rel.run_with_reloader, "_lux_flask_guard", False):

            def _no_reloader(main_func, *args, **kwargs):  # noqa: ANN001
                print(
                    "[FLASK-GUARD] werkzeug.run_with_reloader bypassed",
                    flush=True,
                )
                return main_func()

            _no_reloader._lux_flask_guard = True  # type: ignore[attr-defined]
            rel.run_with_reloader = _no_reloader  # type: ignore[assignment]
            patched += 1
    except Exception as exc:
        print("[FLASK-GUARD] reloader bypass skip:", repr(exc), flush=True)

    # Env belt-and-suspenders
    os.environ["FLASK_DEBUG"] = "0"
    os.environ["FLASK_ENV"] = "production"
    os.environ["WERKZEUG_RUN_MAIN"] = "true"

    _PATCHED = True
    print(f"[FLASK-GUARD] ON patches={patched}", flush=True)
    return True


def apply() -> bool:
    global _ARMED
    if not enabled():
        if not _ARMED:
            print("[FLASK-GUARD] off", flush=True)
            _ARMED = True
        return False
    ok = patch()
    if not ok:
        try:
            import threading

            threading.Timer(0.5, patch).start()
            threading.Timer(2.0, patch).start()
        except Exception:
            pass
    if not _ARMED:
        _ARMED = True
    return True


if enabled():
    apply()
