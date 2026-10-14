# Ydray and Database Candidates

Audit timestamp: 2026-10-14 UTC

No multi-gigabyte file was opened or copied. No remote download was attempted.

## Local candidates

| Rank | Path | Size | Modified (UTC) | File type | Assessment |
|---:|---|---:|---|---|---|
| 1 | `/workspace/replit_elite_stack_patch.zip` | 229,152 B | 2026-10-13 16:19:50 | ZIP archive | Small patch bundle only. The archive listing totals about 1.59 MB uncompressed across 60 files. It is not the Ydray full-app archive and contains no live multi-GB database. |

No other project `.db`, `.sqlite`, `.sqlite3`, `.zip`, `.7z`, or `.rar` file
was found in:

- `/workspace`
- `/home/ubuntu/Downloads` (directory absent)
- `/home/ubuntu/Desktop` (directory absent)
- `/home/ubuntu/Documents` (directory absent)
- accessible Cursor-local data

## Expected historical Ydray full-app archive

| Expected filename | Recorded size | Local status | Historical assessment |
|---|---:|---|---|
| `YDRAY-Bac-Bo-Watcher-replit-full-app-audit-for-cursor-Ai.zip` | 7,400,961,129 B | **Not found** | Most likely historical full Replit export. Manifest says it contained the main engine, a roughly 2.8 GB `bot/bacbo.db`, `signal_handler.py`, supporting runtime modules, and gate files. |

The project manifest records that this Ydray transfer expired, a prior ephemeral
copy was deleted, and the archive was never committed to Git. This audit did
not test the old URL and intentionally omits transfer IDs, URLs, and hashes.

## Remote Replit candidates reported by the operator

These are not local files and were not opened in this audit:

| Rank | Replit path | Reported size | Candidate type | Assessment |
|---:|---|---:|---|---|
| 1 | `./bot/bacbo.db` | 3,461,976,064 B | Current live database | **Best currently available full database candidate.** It is the largest active DB and contains the 55,096 consensus rows reported by the read-only check. |
| 2 | `./bot_LEGACY_JULY_16/bacbo.db` | 3,334,729,728 B | Legacy snapshot | Valuable comparison/recovery candidate; likely preserves older source-era state. |
| 3 | `./bacbo.db` | 45,056 B | Tiny sibling | Too small to be the historical production database. A known source of incorrect DB selection. |
| 4 | `./bot_LEGACY_JULY_16/data/bacbo.db` | 0 B | Empty sibling | Not usable. |

## Best candidate conclusion

- Best **local Ydray** candidate: none; the expected 7.4 GB archive is absent.
- Best **currently reachable full database** candidate: Replit
  `./bot/bacbo.db` at 3,461,976,064 bytes.
- Best **historical comparison** candidate: Replit
  `./bot_LEGACY_JULY_16/bacbo.db` at 3,334,729,728 bytes.

The live and legacy Replit databases should eventually be preserved as immutable
read-only copies with size, modification time, and cryptographic hash recorded.
That is a future acquisition step, not something performed in this audit.
