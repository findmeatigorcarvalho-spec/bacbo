#!/usr/bin/env python3
"""Build Result Essence Atlas — every KEEP signal+RESULT scored for Profit Family AI.

  PYTHONPATH=. python3 replit_elite_stack_patch/bot/build_result_essence_atlas.py
  # or on Replit:
  python3 bot/build_result_essence_atlas.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOTS = [HERE.parent.parent, Path("/workspace"), Path("/home/runner/workspace")]


def main() -> int:
    for root in ROOTS:
        cfg = root / "bot" / "config" / "result_essence_engine.py"
        if cfg.is_file():
            s = str(root)
            if s not in sys.path:
                sys.path.insert(0, s)
            break

    from bot.config.result_essence_engine import build_atlas, family_ai_manifest

    data = HERE / "data"
    atlas = build_atlas(data)
    out = data / "result_essence_atlas.json"
    out.write_text(json.dumps(atlas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Mirror into workspace bot/data when present
    for root in ROOTS:
        alt = root / "bot" / "data" / "result_essence_atlas.json"
        try:
            alt.parent.mkdir(parents=True, exist_ok=True)
            alt.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass

    manifest = family_ai_manifest()
    print(json.dumps({
        "wrote": str(out),
        "stats": atlas.get("stats"),
        "invent_directives": len(atlas.get("invent_directives") or []),
        "manifest": {
            "model": manifest.get("model"),
            "layers": manifest.get("layers"),
            "ambition": manifest.get("ambition"),
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
