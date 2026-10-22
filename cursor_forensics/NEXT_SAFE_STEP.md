# Next Safe Step

## Single recommended action

Create a **metadata-only, read-only Replit inventory** of the live source tree
and the two multi-gigabyte database candidates.

The inventory should record, without copying or opening database contents:

- absolute path;
- byte size;
- modification timestamp;
- filesystem type;
- permissions/owner;
- whether the file is a symbolic link;
- SHA-256 hash only if hashing can be performed without disrupting the running
  Replit workload;
- presence and metadata of:
  - `bacbo_royal_complete.py`
  - `bot/signal_handler.py`
  - `bot/main.py`
  - `bot/database.py`
  - `bot/state.py`
  - `bot/config.py`
  - `bot/utils.py`
  - `bot/floor_tracker.py`
  - `_gates_*.py`
  - the live and legacy `bacbo.db` files

Do not restart, deploy, patch, export, compress, or run the bot. Do not query
Telegram. Do not print environment variables or inspect session/config files
that may contain credentials.

## Why this is the safest next step

The current checkout is missing the primary engine, signal handler, most
original runtime modules, and every production database. Any restoration plan
made before confirming the exact Replit files risks applying patches to the
wrong revision or wrong database.

The metadata inventory establishes source-of-truth identity with minimal load
and no behavioral change. Only after it is reviewed should an immutable export
or database copy be planned.
