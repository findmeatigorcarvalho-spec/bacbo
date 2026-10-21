#!/usr/bin/env bash
# DAY ONE ARCHIVE — every file, git blob, log, prompt artifact, DB row on Replit.
# One paste. Produces bacbo_DAY_ONE_<stamp>.zip + MANIFEST.sha256
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o DAY_ONE.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_DAY_ONE_ARCHIVE.sh'
#   bash DAY_ONE.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="bacbo_DAY_ONE_${STAMP}"
ZIP="bacbo_DAY_ONE_${STAMP}.zip"
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "=== REPLIT_DAY_ONE_ARCHIVE $STAMP ==="
rm -rf "$OUT"
mkdir -p "$OUT"

# ── 1. Complete file manifest (every file, size, mtime, sha256) ─────────────
log "[1/12] full file manifest (sha256 every file)..."
MANIFEST="$OUT/MANIFEST_all_files.tsv"
{
  echo -e "bytes\tmtime_iso\tsha256\tpath"
  find . -xdev -type f \
    ! -path './node_modules/*' \
    ! -path './.cache/*' \
    ! -path "./${OUT}/*" \
    ! -path "./bacbo_DAY_ONE_*/*" \
    ! -path './bacbo_SAVE_EVERYTHING_*/*' \
    2>/dev/null | sort | while read -r f; do
      sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
      mt=$(stat -c%Y "$f" 2>/dev/null || echo 0)
      iso=$(date -u -d "@$mt" +%Y-%m-%dT%H:%MZ 2>/dev/null || echo '?')
      hash=$(sha256sum "$f" 2>/dev/null | awk '{print $1}' || echo '?')
      printf '%s\t%s\t%s\t%s\n' "$sz" "$iso" "$hash" "$f"
    done
} > "$MANIFEST"
wc -l "$MANIFEST" | tee -a /dev/stderr

# ── 2. Git — full history since day 1 + large blob extract ──────────────────
log "[2/12] git history + large blobs..."
mkdir -p "$OUT/git"
if [ -d .git ]; then
  git bundle create "$OUT/git/full_history.bundle" --all 2>/dev/null || true
  git log --all --oneline > "$OUT/git/log_oneline.txt" 2>/dev/null || true
  git log --all --format='%H %ai %an %s' > "$OUT/git/log_full.txt" 2>/dev/null || true
  git branch -a > "$OUT/git/branches.txt" 2>/dev/null || true
  git stash list > "$OUT/git/stash.txt" 2>/dev/null || true
  git reflog > "$OUT/git/reflog.txt" 2>/dev/null || true
  git rev-list --objects --all 2>/dev/null \
    | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' 2>/dev/null \
    | awk '/^blob/ {if($3>50000) print $3, $2, $4}' | sort -rn > "$OUT/git/large_blobs.txt" || true
  mkdir -p "$OUT/git/extracted_blobs"
  head -30 "$OUT/git/large_blobs.txt" 2>/dev/null | while read -r sz oid rest; do
    name=$(echo "$rest" | tr '/' '_' | tr ' ' '_')
    git cat-file -p "$oid" > "$OUT/git/extracted_blobs/${sz}_${oid:0:12}_${name}" 2>/dev/null || true
  done
  ls -lah "$OUT/git/" 2>/dev/null || true
fi

# ── 3. bot/ — ENTIRE directory (code, gates, models, logs, data, backups) ─
log "[3/12] full bot/ tree..."
cp -a bot "$OUT/bot_full" 2>/dev/null || true

# ── 4. Engine + all .bak variants at workspace root ─────────────────────────
log "[4/12] engine + backups..."
cp -a bacbo_royal_complete.py "$OUT/" 2>/dev/null || true
cp -a bacbo_royal_complete.py.bak* "$OUT/" 2>/dev/null || true
cp -a bacbo_royal_complete.txt "$OUT/" 2>/dev/null || true
cp -a bacbo.db.bak* "$OUT/" 2>/dev/null || true

# ── 5. All SQLite databases + WAL ───────────────────────────────────────────
log "[5/12] all sqlite files..."
mkdir -p "$OUT/sqlite_all"
find . -xdev -type f \( -name '*.db' -o -name '*.db-wal' -o -name '*.db-shm' -o -name '*.sqlite' \) \
  ! -path './node_modules/*' 2>/dev/null | while read -r f; do
    mkdir -p "$OUT/sqlite_all/$(dirname "$f")"
    cp -a "$f" "$OUT/sqlite_all/$f" 2>/dev/null || true
  done

# ── 6. DB — every table to CSV + schema dump ───────────────────────────────
log "[6/12] db every table csv + schema..."
python3 - "$OUT" <<'PY'
import csv, json, sqlite3, sys
from pathlib import Path
out = Path(sys.argv[1]) / "db_all_tables"
out.mkdir(parents=True, exist_ok=True)
for dbpath in [Path("bot/bacbo.db"), Path(".local/state/replit/log-query.db")]:
    if not dbpath.exists():
        continue
    sub = out / dbpath.as_posix().replace("/", "__")
    sub.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
    schema = {t: con.execute(f"SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0] for t in tables}
    (sub / "schema.json").write_text(json.dumps(schema, indent=2))
    summary = {}
    for t in tables:
        try:
            n = con.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            summary[t] = n
            if n == 0:
                continue
            rows = con.execute(f"SELECT * FROM [{t}]").fetchall()
            cols = [d[0] for d in con.execute(f"SELECT * FROM [{t}] LIMIT 0").description]
            with (sub / f"{t}.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows(rows)
        except Exception as e:
            summary[t] = f"ERR:{e}"
    (sub / "row_counts.json").write_text(json.dumps(summary, indent=2))
    print(f"  {dbpath}: {len(tables)} tables")
    con.close()
PY

# ── 7. Luxury / may_jul exports + zips ─────────────────────────────────────
log "[7/12] luxury + may_jul packs..."
for item in luxury_full_pack.zip luxury_export_light.zip may_jul_export.zip \
  luxury_export_* may_jul_export_*; do
  [ -e "$item" ] && cp -a "$item" "$OUT/" 2>/dev/null && log "  $item"
done

# ── 8. attached_assets, artifacts, scripts, reports, core_buildings ───────
log "[8/12] assets artifacts scripts reports..."
for d in attached_assets artifacts scripts reports core_buildings lib logs; do
  [ -d "$d" ] && cp -a "$d" "$OUT/" 2>/dev/null && log "  $d/"
done

# ── 9. Replit / agent / workflow logs (prompts, shell history, AI sessions) ─
log "[9/12] .agents .local workflow-logs skills config..."
for d in .agents .config; do
  [ -d "$d" ] && cp -a "$d" "$OUT/replit_meta/$d" 2>/dev/null || true
done
mkdir -p "$OUT/replit_meta"
[ -d .local/state/workflow-logs ] && cp -a .local/state/workflow-logs "$OUT/replit_meta/workflow-logs" 2>/dev/null || true
[ -d .local/skills ] && cp -a .local/skills "$OUT/replit_meta/skills" 2>/dev/null || true
[ -d .local/state/scribe ] && cp -a .local/state/scribe "$OUT/replit_meta/scribe" 2>/dev/null || true
for f in .replit replit.md README.md pyproject.toml package.json; do
  [ -f "$f" ] && cp -a "$f" "$OUT/replit_meta/" 2>/dev/null || true
done

# ── 10. All source: py sh md json (excluding node_modules) ──────────────────
log "[10/12] all .py .sh .md source mirror..."
mkdir -p "$OUT/source_mirror"
find . -xdev -type f \( -name '*.py' -o -name '*.sh' -o -name '*.md' \) \
  ! -path './node_modules/*' ! -path './.cache/*' ! -path "./${OUT}/*" 2>/dev/null \
  | while read -r f; do
      mkdir -p "$OUT/source_mirror/$(dirname "$f")"
      cp -a "$f" "$OUT/source_mirror/$f" 2>/dev/null || true
    done

# ── 11. Index README ────────────────────────────────────────────────────────
log "[11/12] writing INDEX..."
cat > "$OUT/INDEX_DAY_ONE.txt" <<IDX
BAC BO DAY ONE ARCHIVE — $STAMP
Generated on Replit: $(hostname) $(pwd)

WHAT IS IN THIS ZIP
===================
MANIFEST_all_files.tsv     — every file: bytes, date, sha256, path
git/                       — full_history.bundle, logs, branches, top git blobs extracted
bot_full/                  — complete bot/ (gates, handler, db, models, logs, data)
bacbo_royal_complete.py*   — engine + all .bak versions
sqlite_all/                — every .db/.wal/.shm on workspace
db_all_tables/             — every DB table as CSV + schema + row counts
luxury/may_jul packs       — floor export snapshots Jul 20
attached_assets/           — images and uploads
artifacts/ scripts/ reports/
replit_meta/               — .agents, workflow-logs, skills, scribe, .replit
source_mirror/             — all .py .sh .md files

NOT ON REPLIT (get separately)
==============================
- Cursor chat history → Cursor app / cursor.com account
- YDRAY 7.4GB full app: u17818127167255IdjZb8f932d8c217QL (expired link)
- Your PC Downloads if you downloaded YDRAY in June

ROW COUNTS (live bot/bacbo.db at pack time)
===========================================
$(python3 - <<'PY' 2>/dev/null || echo "(db read failed)"
import sqlite3
from pathlib import Path
p = Path("bot/bacbo.db")
if p.exists():
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    for t in ["channel_messages","signals","consensus_signals","rooms","room_color_outcomes"]:
        try: print(f"  {t}: {c.execute(f'SELECT COUNT(*) FROM [{t}]').fetchone()[0]:,}")
        except: pass
    c.close()
PY
)

UPLOAD this zip to YDRAY/Drive → paste link in Cursor to finish integration.
IDX

# ── 12. Zip ─────────────────────────────────────────────────────────────────
log "[12/12] zipping (10-20 min for ~2GB)..."
zip -r -q "$ZIP" "$OUT" -x '*/node_modules/*' '*/__pycache__/*' '*/.cache/*'
ln -sf "$ZIP" bacbo_DAY_ONE.zip
sha256sum "$ZIP" > "${ZIP}.sha256"
ls -lah "$ZIP" bacbo_DAY_ONE.zip "${ZIP}.sha256"

log "=== DONE DAY_ONE ==="
log "Upload: $(pwd)/$ZIP"
log "Paste YDRAY/Drive link in Cursor."
