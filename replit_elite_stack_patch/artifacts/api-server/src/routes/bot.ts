import { Router } from "express";
import { DatabaseSync } from "node:sqlite";
import { scryptSync, randomBytes, timingSafeEqual } from "node:crypto";
import { execFileSync, spawnSync } from "child_process";
import jwt from "jsonwebtoken";
import rateLimit from "express-rate-limit";
import path from "path";
import * as fs from "fs";

// Smart DB path: works from any working directory (dev or production).
// In dev, pnpm runs from artifacts/api-server/. In prod, node runs from repo root.
function findDbPath(): string {
  const candidates = [
    path.resolve(process.cwd(), "bot/bacbo.db"),          // prod: cwd = repo root
    path.resolve(process.cwd(), "../../bot/bacbo.db"),     // dev: cwd = artifacts/api-server
    path.resolve(process.cwd(), "../../../bot/bacbo.db"),  // other contexts
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return candidates[0]; // fallback to first candidate even if not found yet
}
const DB_PATH = process.env["DB_PATH"] || findDbPath();

const REQUIRED_SECRETS = ["JWT_SECRET", "DASHBOARD_EMAIL", "DASHBOARD_PASSWORD"] as const;
const missing = REQUIRED_SECRETS.filter((k) => !process.env[k]);
if (missing.length > 0) {
  console.error(
    `[FATAL] Missing required environment variables: ${missing.join(", ")}. ` +
    "Set them in the Replit Secrets tab before starting the server."
  );
  process.exit(1);
}

const JWT_SECRET      = process.env["JWT_SECRET"]!;
const SEED_EMAIL      = process.env["DASHBOARD_EMAIL"]!;
const SEED_PASSWORD   = process.env["DASHBOARD_PASSWORD"]!;
const DB_DOWNLOAD_KEY = process.env["DB_DOWNLOAD_KEY"] || "";

function readBotDataReport(filename: string): any {
  const dataDir = path.join(path.dirname(DB_PATH), "data");
  const reportPath = path.join(dataDir, filename);
  if (!fs.existsSync(reportPath)) {
    return {
      ok: false,
      missing: true,
      report: filename,
      hint: `Run: cd bot && python elite_stack_audit.py`,
    };
  }
  try {
    return { ok: true, ...JSON.parse(fs.readFileSync(reportPath, "utf8")) };
  } catch (err: any) {
    return {
      ok: false,
      missing: false,
      report: filename,
      error: err?.message || "failed to parse report",
    };
  }
}

// ── Password hashing (scrypt, Node.js built-in) ───────────────────────────────
function hashPassword(password: string, salt: string): string {
  return scryptSync(password, salt, 64).toString("hex");
}
function verifyPassword(password: string, hash: string, salt: string): boolean {
  try {
    const derived = scryptSync(password, salt, 64);
    return timingSafeEqual(derived, Buffer.from(hash, "hex"));
  } catch { return false; }
}

// ── Ensure dashboard_users table exists and seed from env vars ────────────────
function initDashboardUsers(): void {
  const db = getDb(false);
  try {
    db.exec(`
      CREATE TABLE IF NOT EXISTS dashboard_users (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        email      TEXT    UNIQUE NOT NULL,
        hash       TEXT    NOT NULL,
        salt       TEXT    NOT NULL,
        is_admin   INTEGER DEFAULT 0,
        created_at TEXT    DEFAULT CURRENT_TIMESTAMP
      )
    `);
    // Migration: add is_admin column to existing databases
    const cols = (db.prepare("PRAGMA table_info(dashboard_users)").all() as any[]).map((r: any) => r.name);
    if (!cols.includes("is_admin")) {
      db.exec("ALTER TABLE dashboard_users ADD COLUMN is_admin INTEGER DEFAULT 0");
    }
    const existing = db.prepare("SELECT COUNT(*) AS n FROM dashboard_users").get() as { n: unknown };
    if (Number(existing.n) === 0) {
      const salt = randomBytes(16).toString("hex");
      const hash = hashPassword(SEED_PASSWORD, salt);
      db.prepare("INSERT INTO dashboard_users (email, hash, salt, is_admin) VALUES (?, ?, ?, 1)")
        .run(SEED_EMAIL.toLowerCase(), hash, salt);
    } else {
      const adminRow = db.prepare("SELECT email FROM dashboard_users WHERE is_admin = 1 LIMIT 1").get() as { email: string } | undefined;
      if (adminRow && adminRow.email !== SEED_EMAIL.toLowerCase()) {
        const salt = randomBytes(16).toString("hex");
        const hash = hashPassword(SEED_PASSWORD, salt);
        db.prepare("UPDATE dashboard_users SET email = ?, hash = ?, salt = ? WHERE email = ?")
          .run(SEED_EMAIL.toLowerCase(), hash, salt, adminRow.email);
      } else if (adminRow) {
        const salt = randomBytes(16).toString("hex");
        const hash = hashPassword(SEED_PASSWORD, salt);
        db.prepare("UPDATE dashboard_users SET hash = ?, salt = ? WHERE email = ?")
          .run(hash, salt, adminRow.email);
      }
      db.prepare("UPDATE dashboard_users SET is_admin = 1 WHERE email = ?")
        .run(SEED_EMAIL.toLowerCase());
    }
  } finally {
    db.close();
  }
}

const router = Router();

// ── Simple in-memory rate limiter for login (5 attempts / 15 min / IP) ───────
const loginAttempts = new Map<string, { count: number; resetAt: number }>();
const LOGIN_MAX     = 5;
const LOGIN_WINDOW  = 15 * 60 * 1000;

function checkRateLimit(ip: string): boolean {
  const now  = Date.now();
  // Clean up expired entries to prevent unbounded memory growth
  for (const [key, val] of loginAttempts) {
    if (now > val.resetAt) loginAttempts.delete(key);
  }
  const entry = loginAttempts.get(ip);
  if (!entry || now > entry.resetAt) {
    loginAttempts.set(ip, { count: 1, resetAt: now + LOGIN_WINDOW });
    return true;
  }
  if (entry.count >= LOGIN_MAX) return false;
  entry.count++;
  return true;
}

function getDb(_readOnly = false): DatabaseSync {
  let lastErr: unknown;
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const db = new DatabaseSync(DB_PATH);
      db.exec("PRAGMA journal_mode=WAL");
      db.exec("PRAGMA busy_timeout=15000");
      db.exec("PRAGMA synchronous=NORMAL");
      db.exec("PRAGMA cache_size=-8000");
      db.exec("PRAGMA temp_store=MEMORY");
      db.exec("PRAGMA mmap_size=134217728");
      return db;
    } catch (e) {
      lastErr = e;
      const msg = (e as Error).message || "";
      if (!msg.includes("locked") && !msg.includes("busy")) throw e;
      const delay = 200 * (attempt + 1);
      const t0 = Date.now(); while (Date.now() - t0 < delay) { /* spin */ }
    }
  }
  throw lastErr;
}

function authMiddleware(req: any, res: any, next: any) {
  const header = req.headers["authorization"] || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token) return res.status(401).json({ error: "Unauthorized" });
  try {
    const decoded = jwt.verify(token, JWT_SECRET) as any;
    req.authUser = decoded;
    next();
  } catch {
    return res.status(401).json({ error: "Invalid token" });
  }
}

function authMiddlewareOrToken(req: any, res: any, next: any) {
  const header = req.headers["authorization"] || "";
  const headerToken = header.startsWith("Bearer ") ? header.slice(7) : "";
  const queryToken = (req.query?.token as string) || "";
  const token = headerToken || queryToken;
  if (!token) return res.status(401).json({ error: "Unauthorized" });
  try {
    const decoded = jwt.verify(token, JWT_SECRET) as any;
    req.authUser = decoded;
    next();
  } catch {
    return res.status(401).json({ error: "Invalid token" });
  }
}

// ── DB helpers — mirror Python's database.py logic exactly ──────────────────

function updateRoomMemory(db: DatabaseSync, handle: string, outcome: string) {
  const h = handle.toLowerCase();
  db.prepare("INSERT OR IGNORE INTO room_memory (handle) VALUES (?)").run(h);
  const col =
    outcome === "win" ? "total_wins" :
    outcome === "loss" ? "total_losses" : "total_ties";
  db.prepare(
    `UPDATE room_memory SET ${col} = ${col} + 1, total_signals = total_signals + 1 WHERE handle = ?`
  ).run(h);

  const row = db.prepare(`
    SELECT total_wins, total_losses, total_ties, total_signals,
      consecutive_wins, consecutive_losses, max_consecutive_wins, max_consecutive_losses
    FROM room_memory WHERE handle = ?
  `).get(h) as any;

  if (row && (row.total_signals as number) > 0) {
    const wr = ((row.total_wins as number) + (row.total_ties as number) * 0.5) / (row.total_signals as number);
    let cWins = row.consecutive_wins as number;
    let cLoss = row.consecutive_losses as number;
    if (outcome === "win" || outcome === "tie") { cWins++; cLoss = 0; }
    else { cWins = 0; cLoss++; }
    const maxWins = Math.max(row.max_consecutive_wins as number, cWins);
    const maxLoss = Math.max(row.max_consecutive_losses as number, cLoss);
    db.prepare(`
      UPDATE room_memory
      SET all_time_wr = ?, consecutive_wins = ?, consecutive_losses = ?,
          max_consecutive_wins = ?, max_consecutive_losses = ?,
          last_outcome = ?, last_updated = CURRENT_TIMESTAMP
      WHERE handle = ?
    `).run(wr, cWins, cLoss, maxWins, maxLoss, outcome, h);
  }

  const ctx = db.prepare(`
    SELECT sc.confidence FROM signal_context sc
    JOIN consensus_signals cs ON sc.consensus_id = cs.id
    WHERE LOWER(sc.room_handle) = ?
    ORDER BY sc.id DESC LIMIT 1
  `).get(h) as any;
  const conf = ctx?.confidence ?? "entry";
  if (conf === "entry") {
    const eCol = outcome === "win" ? "entry_wins" : outcome === "loss" ? "entry_losses" : "entry_ties";
    db.prepare(`
      UPDATE room_memory
      SET entry_calls = entry_calls + 1, ${eCol} = ${eCol} + 1
      WHERE handle = ?
    `).run(h);
  }
}

function reverseRoomMemory(db: DatabaseSync, handle: string, outcome: string) {
  const h = handle.toLowerCase();
  db.prepare("INSERT OR IGNORE INTO room_memory (handle) VALUES (?)").run(h);
  const col =
    outcome === "win" ? "total_wins" :
    outcome === "loss" ? "total_losses" : "total_ties";
  db.prepare(`
    UPDATE room_memory
    SET ${col} = MAX(0, ${col} - 1),
        total_signals = MAX(0, total_signals - 1),
        last_updated = CURRENT_TIMESTAMP
    WHERE handle = ?
  `).run(h);

  const row = db.prepare(`
    SELECT total_wins, total_losses, total_ties, total_signals,
      consecutive_wins, consecutive_losses
    FROM room_memory WHERE handle = ?
  `).get(h) as any;

  if (row && (row.total_signals as number) > 0) {
    const wr = ((row.total_wins as number) + (row.total_ties as number) * 0.5) / (row.total_signals as number);
    let cWins = row.consecutive_wins as number;
    let cLoss = row.consecutive_losses as number;
    if ((outcome === "win" || outcome === "tie") && cWins > 0) cWins--;
    else if (outcome === "loss" && cLoss > 0) cLoss--;
    db.prepare(`
      UPDATE room_memory
      SET all_time_wr = ?, consecutive_wins = ?, consecutive_losses = ?
      WHERE handle = ?
    `).run(wr, cWins, cLoss, h);
  } else if (row && (row.total_signals as number) === 0) {
    db.prepare(`
      UPDATE room_memory
      SET all_time_wr = 0.5, consecutive_wins = 0, consecutive_losses = 0
      WHERE handle = ?
    `).run(h);
  }

  // Reverse entry assertiveness counters (mirrors Python database.py logic)
  const rCtx = db.prepare(`
    SELECT sc.confidence FROM signal_context sc
    JOIN consensus_signals cs ON sc.consensus_id = cs.id
    WHERE LOWER(sc.room_handle) = ?
    ORDER BY sc.id DESC LIMIT 1
  `).get(h) as any;
  const rConf = rCtx?.confidence ?? "entry";
  if (rConf === "entry") {
    const eCol = outcome === "win" ? "entry_wins" : outcome === "loss" ? "entry_losses" : "entry_ties";
    db.prepare(`
      UPDATE room_memory
      SET entry_calls = MAX(0, entry_calls - 1),
          ${eCol} = MAX(0, ${eCol} - 1)
      WHERE handle = ?
    `).run(h);
  }
}

function updateCorrelations(db: DatabaseSync, rooms: string[], outcome: string) {
  if (rooms.length < 2) return;
  const col =
    outcome === "win" ? "wins" :
    outcome === "loss" ? "losses" : "ties";
  const sorted = [...rooms].sort();
  for (let i = 0; i < sorted.length; i++) {
    for (let j = i + 1; j < sorted.length; j++) {
      db.prepare(
        "INSERT OR IGNORE INTO room_correlations (room_a, room_b) VALUES (?, ?)"
      ).run(sorted[i], sorted[j]);
      db.prepare(
        `UPDATE room_correlations SET ${col} = ${col} + 1, agreements = agreements + 1 WHERE room_a = ? AND room_b = ?`
      ).run(sorted[i], sorted[j]);
    }
  }
}

function reverseCorrelations(db: DatabaseSync, rooms: string[], outcome: string) {
  if (rooms.length < 2) return;
  const col =
    outcome === "win" ? "wins" :
    outcome === "loss" ? "losses" : "ties";
  const sorted = [...rooms].sort();
  for (let i = 0; i < sorted.length; i++) {
    for (let j = i + 1; j < sorted.length; j++) {
      db.prepare(
        `UPDATE room_correlations SET ${col} = MAX(0, ${col} - 1), agreements = MAX(0, agreements - 1) WHERE room_a = ? AND room_b = ?`
      ).run(sorted[i], sorted[j]);
    }
  }
}

function parseRooms(roomsAgreed: string | null | undefined): string[] {
  return (roomsAgreed || "").split(",").map((r) => r.trim()).filter(Boolean);
}

// ── Routes ───────────────────────────────────────────────────────────────────

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

router.post("/auth/login", (req, res) => {
  const ip = (req.headers["x-forwarded-for"] as string || req.socket.remoteAddress || "unknown").split(",")[0].trim();
  if (!checkRateLimit(ip)) {
    return res.status(429).json({ error: "Too many attempts. Please wait 15 minutes." });
  }
  const { email, password } = req.body as { email?: string; password?: string };
  if (!email || !password) {
    return res.status(401).json({ error: "Invalid email or password." });
  }
  let user: { hash: string; salt: string; is_admin: number; email: string } | undefined;
  try {
    const db = getDb(true);
    try {
      user = db.prepare(
        "SELECT hash, salt, is_admin, email FROM dashboard_users WHERE email = ?"
      ).get(email.trim().toLowerCase()) as { hash: string; salt: string; is_admin: number; email: string } | undefined;
    } finally {
      db.close();
    }
  } catch {
    return res.status(503).json({ error: "Database unavailable. Try again shortly." });
  }
  if (!user || !verifyPassword(password, user.hash, user.salt)) {
    return res.status(401).json({ error: "Invalid email or password." });
  }
  const token = jwt.sign(
    { email: user.email, is_admin: Boolean(user.is_admin) },
    JWT_SECRET,
    { expiresIn: "24h" }
  );
  return res.json({ token });
});

// ── User management ───────────────────────────────────────────────────────────

router.get("/users", authMiddleware, (req, res) => {
  if (!(req as any).authUser?.is_admin) return res.status(403).json({ error: "Admin access required." });
  const db = getDb(true);
  try {
    const rows = db.prepare(
      "SELECT id, email, is_admin, created_at FROM dashboard_users ORDER BY created_at ASC"
    ).all() as { id: number; email: string; is_admin: number; created_at: string }[];
    return res.json({ users: rows.map(r => ({ id: Number(r.id), email: String(r.email), is_admin: Boolean(r.is_admin), created_at: String(r.created_at) })) });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

router.post("/users", authMiddleware, (req, res) => {
  if (!(req as any).authUser?.is_admin) return res.status(403).json({ error: "Admin access required." });
  const { email, password } = req.body as { email?: string; password?: string };
  if (!email || !password) return res.status(400).json({ error: "Email and password are required." });
  if (!EMAIL_RE.test(email.trim())) return res.status(400).json({ error: "Invalid email format." });
  if (password.length < 8) return res.status(400).json({ error: "Password must be at least 8 characters." });
  const norm = email.trim().toLowerCase();
  const salt = randomBytes(16).toString("hex");
  const hash = hashPassword(password, salt);
  const db = getDb(false);
  try {
    db.prepare("INSERT INTO dashboard_users (email, hash, salt) VALUES (?, ?, ?)").run(norm, hash, salt);
    return res.json({ ok: true });
  } catch (e: any) {
    if (e.message?.includes("UNIQUE")) return res.status(409).json({ error: "Email already registered." });
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

router.put("/users/:email/password", authMiddleware, (req, res) => {
  if (!(req as any).authUser?.is_admin) return res.status(403).json({ error: "Admin access required." });
  const norm = decodeURIComponent(req.params["email"]!).trim().toLowerCase();
  const { password } = req.body as { password?: string };
  if (!password) return res.status(400).json({ error: "New password is required." });
  if (password.length < 8) return res.status(400).json({ error: "Password must be at least 8 characters." });
  const salt = randomBytes(16).toString("hex");
  const hash = hashPassword(password, salt);
  const db = getDb(false);
  try {
    const result = db.prepare("UPDATE dashboard_users SET hash=?, salt=? WHERE email=?").run(hash, salt, norm);
    if ((result as any).changes === 0) return res.status(404).json({ error: "User not found." });
    return res.json({ ok: true });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

router.delete("/users/:email", authMiddleware, (req, res) => {
  if (!(req as any).authUser?.is_admin) return res.status(403).json({ error: "Admin access required." });
  const norm = decodeURIComponent(req.params["email"]!).trim().toLowerCase();
  const db = getDb(false);
  try {
    const target = db.prepare("SELECT is_admin FROM dashboard_users WHERE email = ?").get(norm) as any;
    if (!target) return res.status(404).json({ error: "User not found." });
    if (target.is_admin) return res.status(403).json({ error: "Cannot remove the administrator account." });
    db.prepare("DELETE FROM dashboard_users WHERE email = ?").run(norm);
    return res.json({ ok: true });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

function queryBotStatus(db: DatabaseSync): object {
  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD UTC — matches SQLite CURRENT_TIMESTAMP

  const acc = db.prepare(`
    SELECT COUNT(*) AS total,
      COALESCE(SUM(CASE WHEN outcome='win'     THEN 1 ELSE 0 END), 0) AS wins,
      COALESCE(SUM(CASE WHEN outcome='loss'    THEN 1 ELSE 0 END), 0) AS losses,
      COALESCE(SUM(CASE WHEN outcome='tie'     THEN 1 ELSE 0 END), 0) AS ties,
      COALESCE(SUM(CASE WHEN outcome='pending' THEN 1 ELSE 0 END), 0) AS pending,
      COALESCE(SUM(CASE WHEN outcome='win' AND (won_at_gale IS NULL OR won_at_gale=0) THEN 1 ELSE 0 END), 0) AS g0_wins,
      COALESCE(SUM(CASE WHEN outcome='win' AND won_at_gale=1 THEN 1 ELSE 0 END), 0) AS g1_wins,
      COALESCE(SUM(CASE WHEN outcome='win' AND won_at_gale=2 THEN 1 ELSE 0 END), 0) AS g2_wins,
      COALESCE(SUM(CASE WHEN outcome='win' AND won_at_gale>=3 THEN 1 ELSE 0 END), 0) AS g3_wins
    FROM consensus_signals WHERE DATE(fired_at) = ?
  `).get(today) as any;

  // Auto-expire pending signals older than 5 minutes — best-effort, isolated so failures
  // never crash the status read (write contention during heavy bot activity is expected).
  try {
    db.prepare(`
      UPDATE consensus_signals SET outcome='loss'
      WHERE outcome='pending'
        AND (CAST(strftime('%s','now') AS INTEGER) - CAST(strftime('%s', fired_at) AS INTEGER)) > 300
    `).run();
  } catch { /* non-fatal — will retry on next poll */ }

  const last = db.prepare(`
    SELECT cs.*,
      COALESCE((SELECT ROUND(SUM(sc.room_score),3) FROM signal_context sc WHERE sc.consensus_id = cs.id), NULL) AS total_score,
      COALESCE((SELECT MAX(sc.gale_level) FROM signal_context sc WHERE sc.consensus_id = cs.id), 0) AS gale_depth,
      cs.confidence_pct, cs.signal_tier, cs.coalition_rooms
    FROM consensus_signals cs WHERE cs.outcome='pending' ORDER BY cs.id DESC LIMIT 1
  `).get() as any;

  const lastResolved = db.prepare(`
    SELECT id, outcome FROM consensus_signals WHERE outcome NOT IN ('pending') ORDER BY id DESC LIMIT 1
  `).get() as any;

  const rooms = db.prepare(`
    SELECT r.handle, r.is_muted,
      rm.all_time_wr, rm.total_signals, rm.total_wins, rm.total_losses,
      rm.total_ties, rm.consecutive_wins, rm.consecutive_losses
    FROM rooms r
    LEFT JOIN room_memory rm ON LOWER(rm.handle) = LOWER(r.handle)
    ORDER BY r.is_muted ASC, rm.all_time_wr DESC
  `).all() as any[];

  const lossStreak = (() => {
    const rows = db.prepare(`
      SELECT outcome FROM consensus_signals
      WHERE outcome != 'pending' ORDER BY id DESC LIMIT 20
    `).all() as any[];
    let count = 0;
    for (const r of rows) {
      if (r.outcome === "loss") count++;
      else break;
    }
    return count;
  })();

  const tiePressure = db.prepare(`
    SELECT COUNT(*) AS cnt FROM consensus_signals
    WHERE outcome != 'pending'
      AND id > COALESCE(
        (SELECT MAX(id) FROM consensus_signals WHERE outcome='tie'), 0
      )
  `).get() as any;

  const resolvedCount = (acc.wins as number) + (acc.losses as number) + (acc.ties as number);
  const wr = resolvedCount > 0
    ? Math.round(((acc.wins as number) + (acc.ties as number) * 0.5) / resolvedCount * 1000) / 10
    : null;

  const heartbeatRow = (() => {
    try {
      return db.prepare("SELECT value FROM bot_state WHERE key = 'last_heartbeat'").get() as any;
    } catch { return null; }
  })();

  const recvFlow = (() => {
    try {
      const row = db.prepare("SELECT value FROM bot_state WHERE key = 'recv_flow'").get() as any;
      return row?.value ? JSON.parse(row.value) : null;
    } catch { return null; }
  })();

  let latestActivityId: number | null = null;
  try {
    const actRow = db.prepare("SELECT MAX(id) AS mid FROM activity_feed").get() as any;
    latestActivityId = actRow?.mid ?? null;
  } catch { /* table may not exist yet */ }

  return {
    accuracy: {
      ...acc, wr,
      g0Wins: Number(acc.g0_wins ?? 0),
      g1Wins: Number(acc.g1_wins ?? 0),
      g2Wins: Number(acc.g2_wins ?? 0),
      g3Wins: Number(acc.g3_wins ?? 0),
    },
    lastPending: last || null,
    lastResolvedId: (lastResolved?.id ?? null) as number | null,
    lastOutcome: (lastResolved?.outcome ?? null) as string | null,
    rooms,
    lossStreak,
    tiePressureRounds: tiePressure.cnt,
    botLastSeen: heartbeatRow?.value || null,
    recvFlow,
    latestActivityId,
  };
}

router.get("/bot/status", authMiddleware, (_req, res) => {
  const db = getDb(true);
  try {
    return res.json(queryBotStatus(db));
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

router.get("/bot/stream", authMiddlewareOrToken, (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.flushHeaders();

  let lastResolvedId: number | null = null;
  let lastPendingId:  number | null = null;
  let lastHeartbeat:  string | null = null;
  let lastActivityId: number | null = null;
  let closed = false;

  const tick = () => {
    if (closed) return;
    try {
      const db = getDb(true);
      let payload: any;
      try {
        payload = queryBotStatus(db);
      } finally {
        db.close();
      }

      const newResolvedId  = payload.lastResolvedId ?? null;
      const newPendingId   = payload.lastPending?.id ?? null;
      const newHeartbeat   = payload.botLastSeen ?? null;
      const newActivityId  = payload.latestActivityId ?? null;
      const changed =
        newResolvedId !== lastResolvedId ||
        newPendingId  !== lastPendingId  ||
        newHeartbeat  !== lastHeartbeat  ||
        newActivityId !== lastActivityId;

      if (changed) {
        lastResolvedId = newResolvedId;
        lastPendingId  = newPendingId;
        lastHeartbeat  = newHeartbeat;
        lastActivityId = newActivityId;
        res.write(`data: ${JSON.stringify(payload)}\n\n`);
      } else {
        res.write(`: keepalive\n\n`);
      }
    } catch {
      res.write(`: error\n\n`);
    }
  };

  tick();
  const interval = setInterval(tick, 250);

  req.on("close", () => {
    closed = true;
    clearInterval(interval);
  });
});

router.get("/bot/bankroll", authMiddleware, (_req, res) => {
  const db = getDb(true);
  let rows: any[], atRows: any[];
  try {
    const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD UTC — matches SQLite CURRENT_TIMESTAMP
    rows = db.prepare(`
      SELECT outcome FROM consensus_signals
      WHERE DATE(fired_at) = ? AND outcome != 'pending'
    `).all(today) as any[];

    atRows = db.prepare(`
      SELECT outcome FROM consensus_signals WHERE outcome != 'pending'
    `).all() as any[];
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }

  const calc = (rs: any[]) => {
    let units = 0, wins = 0, losses = 0, ties = 0;
    for (const r of rs) {
      if (r.outcome === "win")  { units += 1; wins++; }
      if (r.outcome === "loss") { units -= 1; losses++; }
      if (r.outcome === "tie")  { units += 1; ties++; }
    }
    return { units, wins, losses, ties, total: wins + losses + ties };
  };

  return res.json({ today: calc(rows!), alltime: calc(atRows!) });
});

router.get("/bot/leaderboard", authMiddleware, (_req, res) => {
  const db = getDb(true);
  try {
    const rooms = db.prepare(`
      SELECT handle, all_time_wr, total_signals, total_wins, total_losses,
        total_ties, consecutive_wins, consecutive_losses, last_outcome,
        max_consecutive_wins, max_consecutive_losses,
        entry_calls, entry_wins, entry_losses, entry_ties
      FROM room_memory
      WHERE total_signals >= 3
      ORDER BY all_time_wr DESC
      LIMIT 15
    `).all() as any[];
    return res.json({ rooms });
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

// ── Rooms management ─────────────────────────────────────────────────────────
router.get("/bot/rooms", authMiddleware, (_req, res) => {
  const db = getDb(true);
  try {
    const rooms = db.prepare(`
      SELECT r.id, r.handle, r.is_muted, r.added_at,
        rm.total_signals, rm.total_wins, rm.total_losses, rm.total_ties, rm.all_time_wr
      FROM rooms r
      LEFT JOIN room_memory rm ON LOWER(r.handle) = LOWER(rm.handle)
      ORDER BY r.added_at ASC
    `).all();
    return res.json({ rooms });
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

router.post("/bot/rooms", authMiddleware, (req, res) => {
  const { handle } = req.body as { handle?: string };
  if (!handle || !handle.startsWith("@")) {
    return res.status(400).json({ error: "handle must start with @" });
  }
  const clean = handle.trim().toLowerCase();
  const db = getDb(false);
  try {
    const exists = db.prepare("SELECT id FROM rooms WHERE LOWER(handle)=?").get(clean);
    if (exists) return res.status(409).json({ error: "Room already exists" });
    db.prepare("INSERT INTO rooms (handle, is_muted, added_at) VALUES (?, 0, datetime('now'))").run(handle.trim());
    db.prepare("INSERT OR IGNORE INTO room_memory (handle) VALUES (?)").run(handle.trim());
    return res.json({ ok: true, handle: handle.trim() });
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

router.delete("/bot/rooms/:handle", authMiddleware, (req, res) => {
  const handle = decodeURIComponent(req.params.handle);
  const db = getDb(false);
  try {
    const row = db.prepare("SELECT id FROM rooms WHERE handle=?").get(handle);
    if (!row) return res.status(404).json({ error: "Room not found" });
    db.prepare("DELETE FROM rooms WHERE handle=?").run(handle);
    return res.json({ ok: true, removed: handle });
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

router.get("/bot/history", authMiddleware, (_req, res) => {
  const db = getDb(true);
  try {
    // Deduplicate by fired_at second: when GOLDEN + SOLO_ELITE fire simultaneously
    // for the same round, only the highest-ID row (GOLDEN) is shown in the feed.
    const rows = db.prepare(`
      SELECT cs.id, cs.signal_kind, cs.color, cs.classification, cs.rooms_agreed,
        cs.tie_info, cs.outcome, cs.fired_at, cs.resolved_at,
        ROUND(sc_agg.total_score, 3) AS total_score,
        COALESCE(sc_agg.gale_depth, 0)  AS gale_depth,
        cs.confidence_pct, cs.signal_tier, cs.coalition_rooms
      FROM consensus_signals cs
      LEFT JOIN (
        SELECT consensus_id,
               SUM(room_score) AS total_score,
               MAX(gale_level) AS gale_depth
        FROM signal_context
        GROUP BY consensus_id
      ) sc_agg ON sc_agg.consensus_id = cs.id
      WHERE cs.id IN (
        SELECT MAX(id)
        FROM consensus_signals
        GROUP BY strftime('%Y-%m-%d %H:%M:%S', fired_at)
      )
      ORDER BY cs.id DESC LIMIT 50
    `).all() as any[];
    return res.json({ signals: rows });
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

router.get("/bot/analytics", authMiddleware, (_req, res) => {
  const db = getDb(true);
  try {
    // Last 30 resolved signals → derive actual winning color from prediction + outcome
    const resolved = db.prepare(`
      SELECT cs.id, cs.signal_kind, cs.color, cs.tie_info, cs.outcome, cs.fired_at, cs.rooms_agreed, cs.classification,
        COALESCE((SELECT ROUND(SUM(sc.room_score),3) FROM signal_context sc WHERE sc.consensus_id = cs.id), NULL) AS total_score,
        cs.confidence_pct, cs.signal_tier, cs.coalition_rooms
      FROM consensus_signals cs
      WHERE cs.outcome != 'pending'
      ORDER BY cs.id DESC LIMIT 30
    `).all() as any[];

    const sequence = resolved.map((sig: any) => {
      const c = (sig.color || "").toLowerCase();
      const isBlue = c.includes("blue") || c.includes("azul");
      const isRed  = c.includes("red")  || c.includes("vermelho");
      let actual: string | null = null;
      if (sig.outcome === "tie")  actual = "tie";
      else if (sig.outcome === "win")  actual = isBlue ? "blue" : isRed ? "red" : null;
      else if (sig.outcome === "loss") actual = isBlue ? "red"  : isRed ? "blue" : null;
      return { actual, kind: sig.signal_kind, outcome: sig.outcome, firedAt: sig.fired_at };
    }).filter((x: any) => x.actual !== null).reverse(); // oldest first

    const now = new Date();
    const today      = now.toISOString().slice(0, 10); // YYYY-MM-DD UTC
    const weekAgo    = new Date(now.getTime() - 7 * 86400000).toISOString().slice(0, 10);
    const monthStart = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-01`;

    // Read today_cutoff from bot_state — set by reset-session button
    const cutoffRow = db.prepare("SELECT value FROM bot_state WHERE key='today_cutoff'").get() as any;
    const todayCutoff: string | null = cutoffRow ? String(cutoffRow.value) : null;

    function fetchStats(db: any, whereClause: string, params: any[], includeGaleBreakdown = false) {
      const s = db.prepare(`
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN outcome='win'     THEN 1 ELSE 0 END) AS wins,
          SUM(CASE WHEN outcome='loss'    THEN 1 ELSE 0 END) AS losses,
          SUM(CASE WHEN outcome='tie'     THEN 1 ELSE 0 END) AS ties,
          SUM(CASE WHEN outcome='pending' THEN 1 ELSE 0 END) AS pending,
          SUM(CASE WHEN outcome='win' AND (won_at_gale IS NULL OR won_at_gale=0) THEN 1 ELSE 0 END) AS g0_wins,
          SUM(CASE WHEN outcome='win' AND won_at_gale=1 THEN 1 ELSE 0 END) AS g1_wins,
          SUM(CASE WHEN outcome='win' AND won_at_gale=2 THEN 1 ELSE 0 END) AS g2_wins,
          SUM(CASE WHEN outcome='win' AND won_at_gale>=3 THEN 1 ELSE 0 END) AS g3_wins
        FROM consensus_signals ${whereClause}
      `).get(...params) as any;
      const wins    = Number(s?.wins    ?? 0);
      const losses  = Number(s?.losses  ?? 0);
      const ties    = Number(s?.ties    ?? 0);
      const pending = Number(s?.pending ?? 0);
      const g0Wins  = Number(s?.g0_wins ?? 0);
      const g1Wins  = Number(s?.g1_wins ?? 0);
      const g2Wins  = Number(s?.g2_wins ?? 0);
      const g3Wins  = Number(s?.g3_wins ?? 0);
      const resolved = wins + losses + ties;
      const decidedWL = wins + losses;
      return { wins, losses, ties, pending, total: resolved + pending, wr: decidedWL > 0 ? Math.round((wins + ties) / decidedWL * 100) : null, g0Wins, g1Wins, g2Wins, g3Wins };
    }

    // Session stats: filter by cutoff if set, otherwise use today's date
    const sessionStats = todayCutoff
      ? fetchStats(db, "WHERE fired_at > ?", [todayCutoff])
      : fetchStats(db, "WHERE DATE(fired_at) = ?", [today]);

    const weeklyStats  = fetchStats(db, "WHERE DATE(fired_at) >= ?",         [weekAgo]);
    const monthlyStats = fetchStats(db, "WHERE DATE(fired_at) >= ?",         [monthStart]);
    const allTimeStats = fetchStats(db, "WHERE outcome IN ('win','loss','tie','pending')", []);

    // Per-kind breakdown — all time (including G0/G1/G2 gale breakdown)
    const kindBreakdown = db.prepare(`
      SELECT signal_kind,
        COUNT(*) AS total,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties,
        SUM(CASE WHEN outcome='win' AND (won_at_gale IS NULL OR won_at_gale=0) THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win' AND won_at_gale=1 THEN 1 ELSE 0 END) AS g1_wins,
        SUM(CASE WHEN outcome='win' AND won_at_gale>=2 THEN 1 ELSE 0 END) AS g2plus_wins
      FROM consensus_signals
      WHERE outcome != 'pending'
      GROUP BY signal_kind ORDER BY total DESC
    `).all() as any[];

    // Per-kind breakdown — today only
    const todayKindBreakdown = db.prepare(`
      SELECT signal_kind,
        COUNT(*) AS total,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties,
        SUM(CASE WHEN outcome='win' AND (won_at_gale IS NULL OR won_at_gale=0) THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win' AND won_at_gale=1 THEN 1 ELSE 0 END) AS g1_wins,
        SUM(CASE WHEN outcome='win' AND won_at_gale>=2 THEN 1 ELSE 0 END) AS g2plus_wins
      FROM consensus_signals
      WHERE outcome != 'pending' AND DATE(fired_at) = ?
      GROUP BY signal_kind ORDER BY total DESC
    `).all(today) as any[];

    // Blocked hours — written by Python's auto_evaluate_hour_blocks(), default if not set
    const blockedHoursRow = db.prepare(
      "SELECT value FROM bot_state WHERE key='blocked_hours_json'"
    ).get() as any;
    const blockedHours: number[] = blockedHoursRow
      ? (() => { try { return JSON.parse(String(blockedHoursRow.value)); } catch { return [10,17,21,22,23]; } })()
      : [10, 17, 21, 22, 23];

    const sessionLabelRow = db.prepare("SELECT value FROM bot_state WHERE key='session_label'").get() as any;
    const sessionLabel: string | null = sessionLabelRow ? String(sessionLabelRow.value) : null;

    return res.json({
      sequence,
      sessionStats,
      weeklyStats,
      monthlyStats,
      allTimeStats,
      kindBreakdown,
      todayKindBreakdown,
      todayDate:      today,
      weekStartDate:  weekAgo,
      monthStartDate: monthStart,
      sessionCutoff:  todayCutoff,
      sessionLabel,
      blockedHours,
    });
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

function persistLossStreak(db: DatabaseSync, delta: "win" | "loss" | "tie" | "undo_loss" | "undo_other"): void {
  const row = db.prepare("SELECT value FROM bot_state WHERE key = 'loss_streak'").get() as any;
  const cur = row ? (parseInt(String(row.value), 10) || 0) : 0;
  let next = cur;
  if (delta === "win" || delta === "tie")          next = 0;
  else if (delta === "loss")                        next = cur + 1;
  else if (delta === "undo_loss")                   next = Math.max(0, cur - 1);
  // undo_other: no change — undoing a win/tie doesn't restore a loss streak
  db.prepare(
    "INSERT OR REPLACE INTO bot_state (key, value, updated_at) VALUES ('loss_streak', ?, datetime('now'))"
  ).run(String(next));
}

router.post("/bot/reset-session", authMiddleware, (_req, res) => {
  const db = getDb(false);
  try {
    // 1. Reset loss streak to 0
    db.prepare("INSERT OR REPLACE INTO bot_state (key, value, updated_at) VALUES ('loss_streak', '0', datetime('now'))").run();
    // 2. Expire any stale pending signals
    const expired = db.prepare("UPDATE consensus_signals SET outcome='loss' WHERE outcome='pending'").run();
    // 3. Set a flag for the bot to clear its in-memory gale/cooldown state on next heartbeat
    db.prepare("INSERT OR REPLACE INTO bot_state (key, value, updated_at) VALUES ('reset_session_flag', '1', datetime('now'))").run();
    // 4. Set today_cutoff to NOW — the "Today" section on the dashboard starts fresh from this moment
    db.prepare("INSERT OR REPLACE INTO bot_state (key, value, updated_at) VALUES ('today_cutoff', datetime('now'), datetime('now'))").run();
    const cutoffRow = db.prepare("SELECT value FROM bot_state WHERE key='today_cutoff'").get() as any;
    return res.json({ ok: true, expiredPending: (expired as any).changes, sessionCutoff: cutoffRow?.value });
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

router.post("/bot/outcome", authMiddleware, (req, res) => {
  const { outcome } = req.body as { outcome?: string };
  if (!["win", "loss", "tie", "undo"].includes(outcome || "")) {
    return res.status(400).json({ error: "outcome must be win|loss|tie|undo" });
  }
  const db = getDb(false);
  try {
    if (outcome === "undo") {
      const row = db.prepare(`
        SELECT id, outcome, rooms_agreed FROM consensus_signals
        WHERE outcome != 'pending' ORDER BY id DESC LIMIT 1
      `).get() as any;
      if (!row) return res.status(404).json({ error: "Nenhum resultado para desfazer" });

      const rooms = parseRooms(row.rooms_agreed);
      db.prepare("UPDATE consensus_signals SET outcome='pending' WHERE id=?").run(row.id);
      for (const handle of rooms) reverseRoomMemory(db, handle, row.outcome);
      reverseCorrelations(db, rooms, row.outcome);
      persistLossStreak(db, row.outcome === "loss" ? "undo_loss" : "undo_other");
      return res.json({ ok: true, undone: row.outcome, id: row.id });
    }

    // Use the most recent pending signal for room memory + as the canonical reference
    const pending = db.prepare(`
      SELECT id, rooms_agreed, fired_at FROM consensus_signals
      WHERE outcome='pending' ORDER BY id DESC LIMIT 1
    `).get() as any;
    if (!pending) return res.status(404).json({ error: "Nenhum sinal pendente" });

    const rooms = parseRooms(pending.rooms_agreed);
    // Resolve ALL pending signals from the same round (fired within 90 s of the latest).
    // This handles GOLDEN + SOLO_ELITE pairs that are both pending simultaneously.
    db.prepare(`
      UPDATE consensus_signals SET outcome=?
      WHERE outcome='pending'
        AND ABS(CAST(strftime('%s', fired_at) AS INTEGER)
              - CAST(strftime('%s', ?) AS INTEGER)) <= 90
    `).run(outcome!, pending.fired_at);
    for (const handle of rooms) updateRoomMemory(db, handle, outcome as string);
    updateCorrelations(db, rooms, outcome as string);
    persistLossStreak(db, outcome as "win" | "loss" | "tie");

    // ── Retroactive gale win: if this is a gale recovery WIN, mark preceding
    // LOSS signals from the same chain as WIN too.  gale_depth is derived from
    // signal_context for the pending signal (max gale_level across its rooms).
    if (outcome === "win") {
      const galeRow = db.prepare(`
        SELECT COALESCE(MAX(gale_level), 0) AS depth
        FROM signal_context WHERE consensus_id = ?
      `).get(pending.id) as any;
      const galeDepth: number = galeRow?.depth ?? 0;
      if (galeDepth > 0) {
        const lookbackSecs = galeDepth * 35;
        // Find up to galeDepth recent LOSS signals and mark them WIN
        const stale = db.prepare(`
          SELECT id FROM consensus_signals
          WHERE outcome = 'loss'
            AND (CAST(strftime('%s', 'now') AS INTEGER)
                 - CAST(strftime('%s', fired_at) AS INTEGER)) <= ?
          ORDER BY id DESC LIMIT ?
        `).all(lookbackSecs, galeDepth) as any[];
        if (stale.length > 0) {
          const ids = stale.map((r: any) => r.id);
          db.prepare(`UPDATE consensus_signals SET outcome='win' WHERE id IN (${ids.map(() => "?").join(",")})`)
            .run(...ids);
        }
      }
    }

    return res.json({ ok: true, recorded: outcome, id: pending.id });
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

// ── Telegram auth helpers ─────────────────────────────────────────────────────
// Resolve bot/ directory the same smart way as DB_PATH (supports dev & prod cwd)
function findBotDir(): string {
  const candidates = [
    path.resolve(process.cwd(), "bot"),
    path.resolve(process.cwd(), "../../bot"),
    path.resolve(process.cwd(), "../../../bot"),
  ];
  for (const d of candidates) {
    if (fs.existsSync(path.join(d, "tg_auth.py"))) return d;
  }
  return candidates[0];
}
const TG_AUTH_SCRIPT = path.join(findBotDir(), "tg_auth.py");
function runPythonAuth(args: string[]): Record<string, unknown> {
  try {
    const out = execFileSync(
      "python3",
      [TG_AUTH_SCRIPT, ...args],
      { timeout: 30_000, env: process.env }
    ).toString().trim();
    return JSON.parse(out);
  } catch (err: any) {
    const raw = (err.stdout?.toString() || err.stderr?.toString() || err.message || "").trim();
    try { return JSON.parse(raw); } catch { return { status: "error", error: raw || "Unknown error" }; }
  }
}


// ── Cycle monitoring ──────────────────────────────────────────────────────────

// GET /bot/cycles — all active cycles + last 5 closed cycles per room
router.get("/bot/cycles", authMiddleware, (_req, res) => {
  const db = getDb(true);
  try {
    const active = db.prepare(
      "SELECT * FROM room_cycles WHERE is_open=1 ORDER BY opened_at DESC"
    ).all() as any[];

    // Latest closed cycle per room (for rooms with no active cycle)
    const recent = db.prepare(`
      SELECT rc.*
      FROM room_cycles rc
      INNER JOIN (
        SELECT handle, MAX(id) AS max_id
        FROM room_cycles
        WHERE is_open=0
        GROUP BY handle
      ) latest ON rc.id = latest.max_id
      ORDER BY rc.closed_at DESC
    `).all() as any[];

    // All-time cycle stats per handle
    const stats = db.prepare(`
      SELECT
        handle,
        COUNT(*)                        AS total_cycles,
        ROUND(AVG(cycle_wr),4)          AS avg_wr,
        MAX(cycle_wr)                   AS best_wr,
        MIN(CASE WHEN cycle_wr IS NOT NULL THEN cycle_wr END) AS worst_wr,
        SUM(wins)                       AS total_wins,
        SUM(losses)                     AS total_losses,
        SUM(ties)                       AS total_ties
      FROM room_cycles
      WHERE is_open=0 AND (wins+losses)>0
      GROUP BY handle
    `).all() as any[];

    return res.json({ active, recent, stats });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

// GET /bot/cycles/:handle — cycle history for one room (last 30)
router.get("/bot/cycles/:handle", authMiddleware, (req, res) => {
  const handle = "@" + req.params.handle.replace(/^@/, "");
  const db = getDb(true);
  try {
    const cycles = db.prepare(
      "SELECT * FROM room_cycles WHERE handle=? ORDER BY id DESC LIMIT 30"
    ).all(handle) as any[];
    const current = db.prepare(
      "SELECT * FROM room_cycles WHERE handle=? AND is_open=1 ORDER BY id DESC LIMIT 1"
    ).get(handle) as any | null;
    return res.json({ handle, current, history: cycles });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

// GET /bot/telegram/status
router.get("/bot/telegram/status", authMiddleware, (_req, res) => {
  return res.json(runPythonAuth(["status"]));
});

let lastCodeRequestAt = 0;
const CODE_REQUEST_COOLDOWN_MS = 60_000;

// POST /bot/telegram/request  — sends code to user's Telegram
router.post("/bot/telegram/request", authMiddleware, (_req, res) => {
  const now = Date.now();
  if (now - lastCodeRequestAt < CODE_REQUEST_COOLDOWN_MS) {
    const waitSec = Math.ceil((CODE_REQUEST_COOLDOWN_MS - (now - lastCodeRequestAt)) / 1000);
    return res.json({ status: "error", error: `Please wait ${waitSec}s before requesting another code.` });
  }
  const result = runPythonAuth(["request"]);
  if (result.status === "code_sent") {
    lastCodeRequestAt = now;
  }
  return res.json(result);
});

// POST /bot/telegram/verify  — verifies the code entered by user
router.post("/bot/telegram/verify", authMiddleware, (req, res) => {
  const code = String(req.body?.code ?? "").replace(/\D/g, "").trim();
  if (!code) return res.status(400).json({ status: "error", error: "Code is required" });
  const result = runPythonAuth(["verify", code]);
  if (result.status === "success") {
    try {
      spawnSync("pkill", ["-TERM", "-f", "python.*bot/main.py"], { timeout: 5000 });
      (result as any).bot_restarted = true;
      (result as any).bot_note = "Session saved. Bot workflow will auto-restart with the new session.";
    } catch {
      (result as any).bot_restarted = false;
      (result as any).bot_note = "Session saved. Please restart the Telegram Bot workflow manually.";
    }
  }
  return res.json(result);
});

router.post("/bot/telegram/start-bot", authMiddleware, (req: any, res: any) => {
  if (!req.authUser?.is_admin) return res.status(403).json({ error: "Admin only" });
  try {
    spawnSync("pkill", ["-TERM", "-f", "python.*bot/main.py"], { timeout: 5000 });
    return res.json({ status: "ok", message: "Bot process killed. Workflow will auto-restart it." });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ status: "error", error: "Internal server error" });
  }
});

// ── Broadcast Channel ─────────────────────────────────────────────────────────

const broadcastClients = new Set<any>();

const subscribeLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many subscribe attempts. Please try again later." },
});

function initBroadcast(): void {
  const db = getDb(false);
  try {
    db.exec(`
      CREATE TABLE IF NOT EXISTS broadcast_messages (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        content    TEXT NOT NULL,
        sent_at    TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);
    db.exec(`
      CREATE TABLE IF NOT EXISTS broadcast_subscribers (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT UNIQUE NOT NULL,
        subscribed_at TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);
  } finally {
    db.close();
  }
}

// POST /broadcast/messages — admin only: post new message
router.post("/broadcast/messages", authMiddleware, (req: any, res: any) => {
  if (!req.authUser?.is_admin) return res.status(403).json({ error: "Admin only" });
  const content = String(req.body?.content ?? "").trim();
  if (!content) return res.status(400).json({ error: "content required" });
  try {
    const db = getDb(false);
    const result = db.prepare("INSERT INTO broadcast_messages (content) VALUES (?)").run(content);
    const msg = db.prepare("SELECT * FROM broadcast_messages WHERE id = ?").get(result.lastInsertRowid) as any;
    db.close();
    const data = JSON.stringify(msg);
    for (const client of broadcastClients) {
      try { client.write(`data: ${data}\n\n`); } catch { /* stale client */ }
    }
    return res.json(msg);
  } catch (e: any) { console.error("[API error]", e); return res.status(500).json({ error: "Internal server error" }); }
});

// GET /broadcast/messages — public: list last 50 messages
router.get("/broadcast/messages", (_req: any, res: any) => {
  try {
    const db = getDb(true);
    const msgs = db.prepare("SELECT * FROM broadcast_messages ORDER BY id DESC LIMIT 50").all() as any[];
    db.close();
    return res.json({ messages: msgs });
  } catch (e: any) { console.error("[API error]", e); return res.status(500).json({ error: "Internal server error" }); }
});

// DELETE /broadcast/messages/:id — admin only
router.delete("/broadcast/messages/:id", authMiddleware, (req: any, res: any) => {
  if (!req.authUser?.is_admin) return res.status(403).json({ error: "Admin only" });
  try {
    const db = getDb(false);
    db.prepare("DELETE FROM broadcast_messages WHERE id = ?").run(Number(req.params.id));
    db.close();
    return res.json({ ok: true });
  } catch (e: any) { console.error("[API error]", e); return res.status(500).json({ error: "Internal server error" }); }
});

// GET /broadcast/stream — auth-protected SSE: push new messages in real time
router.get("/broadcast/stream", authMiddlewareOrToken, (_req: any, res: any) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.flushHeaders();
  broadcastClients.add(res);
  res.write(`: connected\n\n`);
  _req.on("close", () => { broadcastClients.delete(res); });
});

// POST /broadcast/subscribe — rate-limited: register email
router.post("/broadcast/subscribe", subscribeLimiter, (req: any, res: any) => {
  const email = String(req.body?.email ?? "").trim().toLowerCase();
  if (!email || !email.includes("@")) return res.status(400).json({ error: "valid email required" });
  try {
    const db = getDb(false);
    db.prepare("INSERT OR IGNORE INTO broadcast_subscribers (email) VALUES (?)").run(email);
    db.close();
    return res.json({ ok: true });
  } catch (e: any) { console.error("[API error]", e); return res.status(500).json({ error: "Internal server error" }); }
});

// GET /broadcast/subscribers — admin only
router.get("/broadcast/subscribers", authMiddleware, (req: any, res: any) => {
  if (!req.authUser?.is_admin) return res.status(403).json({ error: "Admin only" });
  try {
    const db = getDb(true);
    const subs = db.prepare("SELECT * FROM broadcast_subscribers ORDER BY subscribed_at DESC").all() as any[];
    db.close();
    return res.json({ subscribers: subs, count: subs.length });
  } catch (e: any) { console.error("[API error]", e); return res.status(500).json({ error: "Internal server error" }); }
});

// DELETE /broadcast/subscribers/:email — admin only
router.delete("/broadcast/subscribers/:email", authMiddleware, (req: any, res: any) => {
  if (!req.authUser?.is_admin) return res.status(403).json({ error: "Admin only" });
  try {
    const db = getDb(false);
    db.prepare("DELETE FROM broadcast_subscribers WHERE email = ?").run(decodeURIComponent(req.params.email));
    db.close();
    return res.json({ ok: true });
  } catch (e: any) { console.error("[API error]", e); return res.status(500).json({ error: "Internal server error" }); }
});

// ── Database download (auth-protected, also accepts ?key=DB_DOWNLOAD_KEY for browser links) ──
router.get("/download/db", (req: any, res: any) => {
  try {
    const queryKey = req.query?.key as string | undefined;
    if (queryKey) {
      if (!DB_DOWNLOAD_KEY || queryKey !== DB_DOWNLOAD_KEY) {
        return res.status(401).json({ error: "Invalid key" });
      }
    } else {
      // Fall back to JWT auth header
      const auth = req.headers["authorization"];
      if (!auth || !auth.startsWith("Bearer ")) {
        return res.status(401).json({ error: "Unauthorized" });
      }
      try {
        jwt.verify(auth.slice(7), JWT_SECRET);
      } catch {
        return res.status(401).json({ error: "Invalid token" });
      }
    }
    if (!fs.existsSync(DB_PATH)) {
      return res.status(404).json({ error: "Database file not found" });
    }
    const stat = fs.statSync(DB_PATH);
    const filename = `bacbo_${new Date().toISOString().slice(0, 10)}.db`;
    res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
    res.setHeader("Content-Type", "application/octet-stream");
    res.setHeader("Content-Length", stat.size);
    const stream = fs.createReadStream(DB_PATH);
    stream.pipe(res);
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/bot/log", (req: any, res: any) => {
  const queryKey = req.query?.key as string | undefined;
  if (!queryKey || !DB_DOWNLOAD_KEY || queryKey !== DB_DOWNLOAD_KEY) {
    const auth = req.headers["authorization"];
    if (!auth || !auth.startsWith("Bearer ")) return res.status(401).json({ error: "Unauthorized" });
    try { jwt.verify(auth.slice(7), JWT_SECRET); } catch { return res.status(401).json({ error: "Invalid token" }); }
  }
  const logPath = path.join(path.dirname(DB_PATH), "bot.log");
  try {
    const lines = (req.query?.lines ? parseInt(req.query.lines) : 100);
    const content = fs.readFileSync(logPath, "utf-8");
    const allLines = content.split("\n");
    const tail = allLines.slice(-lines).join("\n");
    res.type("text/plain").send(tail);
  } catch (e: any) {
    console.error("[API error]", e);
    res.status(500).send("Log file unavailable");
  }
});

// ── Engine Health endpoint (T012) ────────────────────────────────────────────
router.get("/bot/engine-health", authMiddleware, (_req, res) => {
  try {
    const db = getDb();

    // Recent engine events (last 50)
    const events = db.prepare(`
      SELECT event_type, detail, created_at
      FROM engine_events
      ORDER BY created_at DESC
      LIMIT 50
    `).all() as { event_type: string; detail: string; created_at: string }[];

    let kellyRow: { threshold: number; updated_at: string } | undefined;
    try {
      const cols = db.prepare("PRAGMA table_info(kelly_state)").all() as any[];
      const colNames = cols.map((c: any) => c.name);
      if (colNames.includes("threshold")) {
        kellyRow = db.prepare(`SELECT threshold, updated_at FROM kelly_state ORDER BY rowid DESC LIMIT 1`).get() as any;
      } else if (colNames.includes("key") && colNames.includes("value")) {
        const kr = db.prepare(`SELECT value, updated_at FROM kelly_state WHERE key='threshold' LIMIT 1`).get() as any;
        if (kr) kellyRow = { threshold: kr.value, updated_at: kr.updated_at };
      }
    } catch {}

    let plattRow: { coef_a: number; coef_b: number; n_samples: number; trained_at: string } | undefined;
    try {
      plattRow = db.prepare(`
        SELECT coef_a, coef_b, n_samples, trained_at
        FROM calibration_coefficients
        ORDER BY id DESC LIMIT 1
      `).get() as any;
    } catch {
      try {
        plattRow = db.prepare(`
          SELECT coef_a, coef_b, n_samples, updated_at AS trained_at
          FROM calibration_coefficients
          ORDER BY id DESC LIMIT 1
        `).get() as any;
      } catch {}
    }

    // Outcome history stats (last 200)
    const histRows = db.prepare(`
      SELECT result AS outcome, score, kind, gale_depth, recorded_at AS created_at
      FROM outcome_history
      ORDER BY id DESC
      LIMIT 200
    `).all() as { outcome: string; score: number; kind: string; gale_depth: number; created_at: string }[];

    const wins   = histRows.filter(r => r.outcome === "win").length;
    const losses = histRows.filter(r => r.outcome === "loss").length;
    const ties   = histRows.filter(r => r.outcome === "tie").length;
    const total  = histRows.length;
    const winRate = total > 0 ? Math.round((wins / total) * 1000) / 10 : null;

    // Markov chain sample count (proxy: count outcome_history rows)
    const markovSamples = db.prepare(`SELECT COUNT(*) as n FROM outcome_history`).get() as { n: number };

    // Bot startup time
    const startupRow = db.prepare(`SELECT started_at FROM bot_startup ORDER BY id DESC LIMIT 1`).get() as
      { started_at: string } | undefined;

    return res.json({
      ok: true,
      startup: startupRow?.started_at ?? null,
      kelly: kellyRow
        ? { threshold: kellyRow.threshold, updatedAt: kellyRow.updated_at }
        : null,
      platt: plattRow
        ? {
            trained:   true,
            coefA:     plattRow.coef_a,
            coefB:     plattRow.coef_b,
            nSamples:  plattRow.n_samples,
            updatedAt: plattRow.trained_at,
          }
        : { trained: false },
      markov: {
        samples:    markovSamples.n,
        sufficient: markovSamples.n >= 30,
      },
      outcomeStats: {
        total, wins, losses, ties,
        winRate,
        recent: histRows.slice(0, 10).map(r => ({
          outcome: r.outcome,
          score:   r.score,
          kind:    r.kind,
          gale:    r.gale_depth,
          ts:      r.created_at,
        })),
      },
      engineEvents: events.slice(0, 20),
    });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Weekly performance trends (T002) ─────────────────────────────────────────
router.get("/bot/trends", authMiddleware, (req, res) => {
  try {
    const db = getDb();
    const daysRaw = Number(req.query.days) || 9999;
    const allData = daysRaw >= 9999;

    const rows = (allData
      ? db.prepare(`
          SELECT
            DATE(recorded_at) AS day,
            COUNT(*)          AS total,
            SUM(CASE WHEN result = 'win'  THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN result = 'tie'  THEN 1 ELSE 0 END) AS ties
          FROM outcome_history
          GROUP BY DATE(recorded_at)
          ORDER BY day ASC
        `).all()
      : db.prepare(`
          SELECT
            DATE(recorded_at) AS day,
            COUNT(*)          AS total,
            SUM(CASE WHEN result = 'win'  THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN result = 'tie'  THEN 1 ELSE 0 END) AS ties
          FROM outcome_history
          WHERE recorded_at >= DATE('now', '-' || ? || ' days')
          GROUP BY DATE(recorded_at)
          ORDER BY day ASC
        `).all(daysRaw)
    ) as { day: string; total: number; wins: number; losses: number; ties: number }[];

    const data = rows.map(r => ({
      day:     r.day,
      total:   r.total,
      wins:    r.wins,
      losses:  r.losses,
      ties:    r.ties,
      winRate: r.total > 0 ? Math.round(((r.wins + r.ties * 0.5) / r.total) * 1000) / 10 : 0,
    }));

    return res.json({ ok: true, data });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Time-of-day heatmap ───────────────────────────────────────────────────────
router.get("/bot/heatmap", authMiddleware, (req, res) => {
  try {
    const db = getDb(true);
    const daysRaw = Number(req.query.days) || 9999;
    const allData = daysRaw >= 9999;
    const rows = (allData
      ? db.prepare(`
          SELECT
            CAST(strftime('%H', fired_at) AS INTEGER) AS hour,
            COUNT(*) AS total,
            SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties
          FROM consensus_signals
          WHERE outcome != 'pending'
          GROUP BY hour ORDER BY hour
        `).all()
      : db.prepare(`
          SELECT
            CAST(strftime('%H', fired_at) AS INTEGER) AS hour,
            COUNT(*) AS total,
            SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties
          FROM consensus_signals
          WHERE outcome != 'pending'
            AND fired_at >= datetime('now', '-' || ? || ' days')
          GROUP BY hour ORDER BY hour
        `).all(daysRaw)
    ) as any[];
    db.close();
    const hours = Array.from({ length: 24 }, (_, h) => {
      const r = rows.find((x: any) => x.hour === h);
      if (!r || r.total === 0) return { hour: h, total: 0, wins: 0, losses: 0, ties: 0, wr: 0 };
      return { hour: h, total: r.total, wins: r.wins, losses: r.losses, ties: r.ties, wr: Math.round(((r.wins + r.ties * 0.5) / r.total) * 1000) / 10 };
    });
    return res.json({ ok: true, hours });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Bankroll tracker CRUD ─────────────────────────────────────────────────────
function initBankrollTracker(): void {
  const db = getDb(false);
  try {
    db.exec(`
      CREATE TABLE IF NOT EXISTS bankroll_entries (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        amount     REAL    NOT NULL,
        type       TEXT    NOT NULL DEFAULT 'bet',
        note       TEXT    DEFAULT '',
        created_at TEXT    DEFAULT (datetime('now'))
      )
    `);
  } finally {
    db.close();
  }
}

router.get("/bot/bankroll-tracker", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);
    const entries = db.prepare("SELECT * FROM bankroll_entries ORDER BY id DESC LIMIT 100").all();
    const summary = db.prepare(`
      SELECT
        COALESCE(SUM(amount), 0) AS balance,
        COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS totalWon,
        COALESCE(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 0) AS totalLost,
        COUNT(*) AS totalEntries
      FROM bankroll_entries
    `).get() as any;
    db.close();
    return res.json({ entries, summary });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/bot/bankroll-tracker", authMiddleware, (req, res) => {
  const { amount, type, note } = req.body as { amount?: number; type?: string; note?: string };
  if (amount == null || isNaN(Number(amount))) return res.status(400).json({ error: "amount required" });
  try {
    const db = getDb(false);
    db.prepare("INSERT INTO bankroll_entries (amount, type, note) VALUES (?, ?, ?)").run(Number(amount), type || "bet", note || "");
    db.close();
    return res.json({ ok: true });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.delete("/bot/bankroll-tracker/:id", authMiddleware, (req, res) => {
  try {
    const db = getDb(false);
    db.prepare("DELETE FROM bankroll_entries WHERE id = ?").run(Number(req.params.id));
    db.close();
    return res.json({ ok: true });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Extended history with filters ─────────────────────────────────────────────
router.get("/bot/history-filtered", authMiddleware, (req, res) => {
  try {
    const db = getDb(true);
    const kind = req.query.kind as string | undefined;
    const outcome = req.query.outcome as string | undefined;
    const from = req.query.from as string | undefined;
    const to = req.query.to as string | undefined;
    const limit = Math.min(Number(req.query.limit) || 50, 200);

    let where = "WHERE 1=1";
    const params: any[] = [];
    if (kind && kind !== "all") { where += " AND cs.signal_kind = ?"; params.push(kind); }
    if (outcome && outcome !== "all") { where += " AND cs.outcome = ?"; params.push(outcome); }
    if (from) { where += " AND DATE(cs.fired_at) >= ?"; params.push(from); }
    if (to) { where += " AND DATE(cs.fired_at) <= ?"; params.push(to); }

    const rows = db.prepare(`
      SELECT cs.id, cs.signal_kind, cs.color, cs.classification, cs.rooms_agreed,
        cs.tie_info, cs.outcome, cs.fired_at,
        ROUND(sc_agg.total_score, 3) AS total_score,
        COALESCE(sc_agg.gale_depth, 0) AS gale_depth,
        cs.confidence_pct, cs.signal_tier, cs.coalition_rooms
      FROM consensus_signals cs
      LEFT JOIN (
        SELECT consensus_id, SUM(room_score) AS total_score, MAX(gale_level) AS gale_depth
        FROM signal_context GROUP BY consensus_id
      ) sc_agg ON sc_agg.consensus_id = cs.id
      ${where}
      ORDER BY cs.id DESC LIMIT ?
    `).all(...params, limit) as any[];
    db.close();
    return res.json({ signals: rows });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Day-of-week heatmap ───────────────────────────────────────────────────────
router.get("/bot/heatmap-dow", authMiddleware, (req, res) => {
  try {
    const db = getDb(true);
    const daysRaw = Number(req.query.days) || 9999;
    const allData = daysRaw >= 9999;
    const rows = (allData
      ? db.prepare(`
          SELECT
            CAST(strftime('%w', fired_at) AS INTEGER) AS dow,
            COUNT(*) AS total,
            SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties
          FROM consensus_signals
          WHERE outcome != 'pending'
          GROUP BY dow ORDER BY dow
        `).all()
      : db.prepare(`
          SELECT
            CAST(strftime('%w', fired_at) AS INTEGER) AS dow,
            COUNT(*) AS total,
            SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties
          FROM consensus_signals
          WHERE outcome != 'pending'
            AND fired_at >= datetime('now', '-' || ? || ' days')
          GROUP BY dow ORDER BY dow
        `).all(daysRaw)
    ) as any[];
    db.close();
    const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const dowData = Array.from({ length: 7 }, (_, d) => {
      const r = rows.find((x: any) => x.dow === d);
      if (!r || r.total === 0) return { dow: d, name: dayNames[d], total: 0, wins: 0, losses: 0, ties: 0, wr: 0 };
      return { dow: d, name: dayNames[d], total: r.total, wins: r.wins, losses: r.losses, ties: r.ties, wr: Math.round(((r.wins + r.ties * 0.5) / r.total) * 1000) / 10 };
    });
    return res.json({ ok: true, days: dowData });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Hourly breakdown for a specific day-of-week ───────────────────────────────
// GET /bot/heatmap-day-hour?dow=0..6&days=30
// Returns 24 hourly buckets (UTC) for the given SQLite %w day (0=Sun…6=Sat).
router.get("/bot/heatmap-day-hour", authMiddleware, (req, res) => {
  try {
    const db   = getDb(true);
    const dow     = Math.min(6, Math.max(0, Number(req.query.dow) || 0));
    const daysRaw = Number(req.query.days) || 9999;
    const allData = daysRaw >= 9999;
    const rows = allData
      ? db.prepare(`
          SELECT
            CAST(strftime('%H', fired_at) AS INTEGER) AS hour,
            COUNT(*)                                  AS total,
            SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties
          FROM consensus_signals
          WHERE outcome != 'pending'
            AND CAST(strftime('%w', fired_at) AS INTEGER) = ?
          GROUP BY hour ORDER BY hour
        `).all(dow) as any[]
      : db.prepare(`
          SELECT
            CAST(strftime('%H', fired_at) AS INTEGER) AS hour,
            COUNT(*)                                  AS total,
            SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties
          FROM consensus_signals
          WHERE outcome != 'pending'
            AND CAST(strftime('%w', fired_at) AS INTEGER) = ?
            AND fired_at >= datetime('now', '-' || ? || ' days')
          GROUP BY hour ORDER BY hour
        `).all(dow, daysRaw) as any[];
    db.close();
    const hours = Array.from({ length: 24 }, (_, h) => {
      const r = rows.find((x: any) => x.hour === h);
      if (!r || r.total === 0) return { hour: h, total: 0, wins: 0, losses: 0, ties: 0, wr: null };
      return {
        hour: h,
        total: r.total,
        wins:  r.wins,
        losses: r.losses,
        ties:  r.ties,
        wr: r.total >= 3 ? Math.round((r.wins / (r.wins + r.losses)) * 1000) / 10 : null,
      };
    });
    return res.json({ ok: true, dow, days: daysRaw, hours });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── BRT-Hour WR breakdown (24 buckets, UTC-3 fixed offset) ───────────────────
// GET /bot/brt-hour-wr
// Returns all 24 BRT hours with historical WR + current BRT time metadata.
router.get("/bot/brt-hour-wr", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);
    const rows = db.prepare(`
      SELECT
        ((CAST(strftime('%H', fired_at) AS INT) - 3 + 24) % 24) AS brt_hour,
        COUNT(*)                                                  AS total,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END)          AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END)          AS losses,
        SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END)          AS ties
      FROM consensus_signals
      WHERE outcome IN ('win','loss','tie')
      GROUP BY brt_hour
      ORDER BY brt_hour
    `).all() as { brt_hour: number; total: number; wins: number; losses: number; ties: number }[];
    db.close();

    const nowUtc  = new Date();
    const brtHour = (nowUtc.getUTCHours() - 3 + 24) % 24;
    const brtMin  = nowUtc.getUTCMinutes();

    const hours = Array.from({ length: 24 }, (_, h) => {
      const r = rows.find((x: any) => x.brt_hour === h);
      if (!r || r.total === 0) return { brt_hour: h, total: 0, wins: 0, losses: 0, ties: 0, wr: null };
      const wl = r.wins + r.losses;
      return {
        brt_hour: h,
        total:    r.total,
        wins:     r.wins,
        losses:   r.losses,
        ties:     r.ties,
        wr:       wl >= 5 ? Math.round((r.wins / wl) * 1000) / 10 : null,
      };
    });

    // Pre-compute next hot hour (WR >= 75%) after current BRT hour
    let nextHot: number | null = null;
    for (let i = 1; i <= 24; i++) {
      const h = (brtHour + i) % 24;
      const entry = hours[h];
      if (entry.wr !== null && entry.wr >= 75) { nextHot = h; break; }
    }

    return res.json({ ok: true, brt_hour: brtHour, brt_min: brtMin, hours, next_hot_brt: nextHot });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Bankroll P&L timeline ─────────────────────────────────────────────────────
router.get("/bot/bankroll-pnl", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);
    const rows = db.prepare(`
      SELECT
        DATE(created_at) AS day,
        COALESCE(SUM(amount), 0) AS net
      FROM bankroll_entries
      GROUP BY DATE(created_at)
      ORDER BY day ASC
    `).all() as any[];
    db.close();
    let cumulative = 0;
    const timeline = rows.map((r: any) => {
      cumulative += r.net;
      return { day: r.day, net: Math.round(r.net * 100) / 100, cumulative: Math.round(cumulative * 100) / 100 };
    });
    return res.json({ ok: true, timeline });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Signal confidence trends ──────────────────────────────────────────────────
router.get("/bot/confidence-trends", authMiddleware, (req, res) => {
  try {
    const db = getDb(true);
    const daysRaw = Number(req.query.days) || 9999;
    const allData = daysRaw >= 9999;
    const rows = (allData
      ? db.prepare(`
          SELECT
            DATE(cs.fired_at) AS day,
            COUNT(*) AS total,
            ROUND(AVG(COALESCE(sc_agg.total_score, 0)), 3) AS avg_score,
            SUM(CASE WHEN cs.outcome='win' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN cs.outcome='loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN cs.outcome='tie' THEN 1 ELSE 0 END) AS ties
          FROM consensus_signals cs
          LEFT JOIN (
            SELECT consensus_id, SUM(room_score) AS total_score
            FROM signal_context GROUP BY consensus_id
          ) sc_agg ON sc_agg.consensus_id = cs.id
          WHERE cs.outcome != 'pending'
          GROUP BY DATE(cs.fired_at)
          ORDER BY day ASC
        `).all()
      : db.prepare(`
          SELECT
            DATE(cs.fired_at) AS day,
            COUNT(*) AS total,
            ROUND(AVG(COALESCE(sc_agg.total_score, 0)), 3) AS avg_score,
            SUM(CASE WHEN cs.outcome='win' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN cs.outcome='loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN cs.outcome='tie' THEN 1 ELSE 0 END) AS ties
          FROM consensus_signals cs
          LEFT JOIN (
            SELECT consensus_id, SUM(room_score) AS total_score
            FROM signal_context GROUP BY consensus_id
          ) sc_agg ON sc_agg.consensus_id = cs.id
          WHERE cs.outcome != 'pending'
            AND cs.fired_at >= datetime('now', '-' || ? || ' days')
          GROUP BY DATE(cs.fired_at)
          ORDER BY day ASC
        `).all(daysRaw)
    ) as any[];
    db.close();
    const trend = rows.map((r: any) => ({
      day: r.day,
      total: r.total,
      avgScore: r.avg_score,
      wins: r.wins,
      losses: r.losses,
      ties: r.ties,
      wr: r.total > 0 ? Math.round(((r.wins + r.ties * 0.5) / r.total) * 1000) / 10 : 0,
    }));
    return res.json({ ok: true, trend });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Room auto-health / promote-mute recommendations ─────────────────────────
router.get("/bot/room-health", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);
    const rows = db.prepare(`
      SELECT
        sc.room_handle AS handle,
        COUNT(*) AS total_7d,
        SUM(CASE WHEN cs.outcome='win'  THEN 1 ELSE 0 END) AS wins_7d,
        SUM(CASE WHEN cs.outcome='loss' THEN 1 ELSE 0 END) AS losses_7d,
        SUM(CASE WHEN cs.outcome='tie'  THEN 1 ELSE 0 END) AS ties_7d
      FROM signal_context sc
      JOIN consensus_signals cs ON cs.id = sc.consensus_id
      WHERE cs.outcome != 'pending'
        AND cs.fired_at >= datetime('now', '-7 days')
      GROUP BY sc.room_handle
      ORDER BY total_7d DESC
    `).all() as any[];

    const allTimeRows = db.prepare(`
      SELECT
        sc.room_handle AS handle,
        COUNT(*) AS total,
        SUM(CASE WHEN cs.outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN cs.outcome='loss' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN cs.outcome='tie'  THEN 1 ELSE 0 END) AS ties
      FROM signal_context sc
      JOIN consensus_signals cs ON cs.id = sc.consensus_id
      WHERE cs.outcome != 'pending'
      GROUP BY sc.room_handle
    `).all() as any[];
    db.close();

    const atMap = new Map<string, any>();
    for (const r of allTimeRows) atMap.set(r.handle, r);

    const rooms = rows.map((r: any) => {
      const wr7d = r.total_7d > 0 ? Math.round(((r.wins_7d + r.ties_7d * 0.5) / r.total_7d) * 1000) / 10 : 0;
      const at = atMap.get(r.handle);
      const wrAll = at && at.total > 0 ? Math.round(((at.wins + at.ties * 0.5) / at.total) * 1000) / 10 : 0;
      let action: string;
      let reason: string;
      if (wr7d >= 65) {
        action = "PROMOTE";
        reason = `${wr7d}% WR (7d) — strong performer`;
      } else if (wr7d >= 50) {
        action = "KEEP";
        reason = `${wr7d}% WR (7d) — stable`;
      } else if (wr7d >= 35) {
        action = "WATCH";
        reason = `${wr7d}% WR (7d) — declining, monitor closely`;
      } else {
        action = "MUTE";
        reason = `${wr7d}% WR (7d) — underperforming, consider muting`;
      }
      return {
        handle: r.handle,
        total7d: r.total_7d,
        wr7d,
        wins7d: r.wins_7d,
        losses7d: r.losses_7d,
        ties7d: r.ties_7d,
        wrAll,
        totalAll: at?.total ?? 0,
        action,
        reason,
      };
    });
    return res.json({ ok: true, rooms });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Win streak tracking ─────────────────────────────────────────────────────
router.get("/bot/win-streak", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);
    const rows = db.prepare(`
      SELECT outcome FROM consensus_signals
      WHERE outcome != 'pending'
      ORDER BY id DESC LIMIT 50
    `).all() as any[];
    db.close();
    let currentStreak = 0;
    let maxStreak = 0;
    let tempStreak = 0;
    for (const r of rows) {
      if (r.outcome === "win" || r.outcome === "tie") {
        if (tempStreak >= 0) tempStreak++;
        else tempStreak = 1;
      } else {
        if (tempStreak > maxStreak) maxStreak = tempStreak;
        tempStreak = 0;
      }
    }
    if (tempStreak > maxStreak) maxStreak = tempStreak;
    for (const r of rows) {
      if (r.outcome === "win" || r.outcome === "tie") currentStreak++;
      else break;
    }
    return res.json({ ok: true, currentStreak, maxStreak });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Room correlation matrix ──────────────────────────────────────────────────
router.get("/bot/room-correlations", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);
    const rows = db.prepare(`
      SELECT room_a, room_b, agreements, wins, losses, ties
      FROM room_correlations
      WHERE agreements > 0
      ORDER BY agreements DESC
    `).all() as any[];
    db.close();

    const rooms = new Set<string>();
    for (const r of rows) { rooms.add(r.room_a); rooms.add(r.room_b); }
    const roomList = [...rooms].sort();

    const matrix: Record<string, Record<string, { agreements: number; wins: number; losses: number; wr: number }>> = {};
    for (const rm of roomList) {
      matrix[rm] = {};
      for (const rm2 of roomList) {
        matrix[rm][rm2] = { agreements: 0, wins: 0, losses: 0, wr: 0 };
      }
    }
    for (const r of rows) {
      const total = r.wins + r.losses + r.ties;
      const wr = total > 0 ? Math.round((r.wins + r.ties * 0.5) / total * 1000) / 10 : 0;
      const entry = { agreements: r.agreements, wins: r.wins, losses: r.losses, wr };
      matrix[r.room_a][r.room_b] = entry;
      matrix[r.room_b][r.room_a] = entry;
    }
    return res.json({ ok: true, rooms: roomList, matrix, pairs: rows });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Martingale calculator ───────────────────────────────────────────────────
router.get("/bot/martingale-calc", authMiddleware, (req, res) => {
  try {
    const bankroll = Number(req.query.bankroll) || 100;
    const baseBet = Number(req.query.base) || 1;
    const multiplier = Number(req.query.multiplier) || 2;

    const levels: { gale: number; bet: number; totalRisk: number; potentialWin: number }[] = [];
    let totalRisk = 0;
    for (let g = 0; g < 10; g++) {
      const bet = baseBet * Math.pow(multiplier, g);
      totalRisk += bet;
      if (totalRisk > bankroll) break;
      levels.push({
        gale: g,
        bet: Math.round(bet * 100) / 100,
        totalRisk: Math.round(totalRisk * 100) / 100,
        potentialWin: Math.round((bet * 0.95 - (totalRisk - bet)) * 100) / 100,
      });
    }

    const db = getDb(true);
    let hasWonAtGale = false;
    try {
      const cols = db.prepare("PRAGMA table_info(consensus_signals)").all() as any[];
      hasWonAtGale = cols.some((c: any) => c.name === "won_at_gale");
    } catch {}

    const row = hasWonAtGale
      ? db.prepare(`
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN outcome='win' AND (won_at_gale IS NULL OR won_at_gale=0) THEN 1 ELSE 0 END) AS g0,
          SUM(CASE WHEN outcome='win' AND won_at_gale=1 THEN 1 ELSE 0 END) AS g1,
          SUM(CASE WHEN outcome='win' AND won_at_gale>=2 THEN 1 ELSE 0 END) AS g2,
          SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses
        FROM consensus_signals WHERE outcome != 'pending'
      `).get() as any
      : db.prepare(`
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) AS g0,
          0 AS g1, 0 AS g2,
          SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses
        FROM consensus_signals WHERE outcome != 'pending'
      `).get() as any;
    db.close();

    const total = row?.total ?? 0;
    const g0Rate = total > 0 ? Math.round((row.g0 / total) * 1000) / 10 : 0;
    const g1Rate = total > 0 ? Math.round((row.g1 / total) * 1000) / 10 : 0;
    const g2Rate = total > 0 ? Math.round((row.g2 / total) * 1000) / 10 : 0;
    const lossRate = total > 0 ? Math.round((row.losses / total) * 1000) / 10 : 0;

    return res.json({
      ok: true,
      maxSafeGale: levels.length - 1,
      levels,
      stats: { total, g0Rate, g1Rate, g2Rate, lossRate },
    });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Color pattern timeline ──────────────────────────────────────────────────
router.get("/bot/color-timeline", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);
    let hasGale = false;
    try {
      const cols = db.prepare("PRAGMA table_info(consensus_signals)").all() as any[];
      hasGale = cols.some((c: any) => c.name === "gale_depth");
    } catch {}
    const rows = db.prepare(`
      SELECT id, color, outcome, fired_at, signal_kind${hasGale ? ", gale_depth" : ""}
      FROM consensus_signals
      WHERE outcome != 'pending'
      ORDER BY id DESC LIMIT 100
    `).all() as any[];
    db.close();

    rows.reverse();

    const timeline = rows.map(r => ({
      id: r.id,
      color: r.color || "tie",
      outcome: r.outcome,
      kind: r.signal_kind,
      gale: r.gale_depth ?? 0,
      time: r.fired_at,
    }));

    let streaks: { color: string; length: number; start: number; end: number }[] = [];
    if (timeline.length > 0) {
      let cur = { color: timeline[0].color, length: 1, start: 0, end: 0 };
      for (let i = 1; i < timeline.length; i++) {
        if (timeline[i].color === cur.color && cur.color !== "tie") {
          cur.length++;
          cur.end = i;
        } else {
          if (cur.length >= 2) streaks.push({ ...cur });
          cur = { color: timeline[i].color, length: 1, start: i, end: i };
        }
      }
      if (cur.length >= 2) streaks.push(cur);
    }

    let alternations = 0;
    for (let i = 2; i < timeline.length; i++) {
      const a = timeline[i - 2].color;
      const b = timeline[i - 1].color;
      const c = timeline[i].color;
      if (a !== "tie" && b !== "tie" && c !== "tie" && a === c && a !== b) alternations++;
    }

    return res.json({ ok: true, timeline, streaks, alternations });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Bankroll Simulator — replay historical signals with different strategies ──
router.get("/bot/simulate", authMiddleware, (req, res) => {
  try {
    const startBalance = Number(req.query.balance) || 105;
    const betSize = Number(req.query.bet) || 5;
    const days = Math.min(Number(req.query.days) || 7, 90);
    const db = getDb(true);
    const rows = db.prepare(`
      SELECT id, signal_kind, color, outcome, fired_at,
        CAST(strftime('%H', fired_at) AS INTEGER) AS hour_utc
      FROM consensus_signals
      WHERE outcome IN ('win','loss','tie')
        AND fired_at >= datetime('now', '-' || ? || ' days')
      ORDER BY id ASC
    `).all(days) as any[];
    db.close();

    const strategies: Record<string, { balance: number; curve: { id: number; balance: number; time: string }[]; wins: number; losses: number; maxDrawdown: number; peak: number }> = {
      flat: { balance: startBalance, curve: [], wins: 0, losses: 0, maxDrawdown: 0, peak: startBalance },
      golden_only: { balance: startBalance, curve: [], wins: 0, losses: 0, maxDrawdown: 0, peak: startBalance },
      peak_hours: { balance: startBalance, curve: [], wins: 0, losses: 0, maxDrawdown: 0, peak: startBalance },
    };

    const peakHoursUTC = new Set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 21, 22, 23]);

    for (const r of rows) {
      const payout = betSize * 0.95;
      const process = (key: string) => {
        const s = strategies[key];
        if (r.outcome === "win") {
          s.balance += payout;
          s.wins++;
        } else if (r.outcome === "loss") {
          s.balance -= betSize;
          s.losses++;
        }
        if (s.balance > s.peak) s.peak = s.balance;
        const dd = s.peak - s.balance;
        if (dd > s.maxDrawdown) s.maxDrawdown = dd;
        s.curve.push({ id: r.id, balance: Math.round(s.balance * 100) / 100, time: r.fired_at });
      };

      process("flat");
      if (r.signal_kind === "GOLDEN" || r.signal_kind === "PLATINUM") process("golden_only");
      if (peakHoursUTC.has(r.hour_utc)) process("peak_hours");
    }

    const result: Record<string, any> = {};
    for (const [key, s] of Object.entries(strategies)) {
      const totalBets = s.wins + s.losses;
      result[key] = {
        finalBalance: Math.round(s.balance * 100) / 100,
        profit: Math.round((s.balance - startBalance) * 100) / 100,
        wins: s.wins,
        losses: s.losses,
        winRate: totalBets > 0 ? Math.round(s.wins / totalBets * 1000) / 10 : 0,
        maxDrawdown: Math.round(s.maxDrawdown * 100) / 100,
        curve: s.curve.length > 200
          ? s.curve.filter((_: any, i: number) => i % Math.ceil(s.curve.length / 200) === 0 || i === s.curve.length - 1)
          : s.curve,
      };
    }
    return res.json({ ok: true, startBalance, betSize, days, totalSignals: rows.length, strategies: result });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Best Room Pairs — find winning combos ───────────────────────────────────
router.get("/bot/best-pairs", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);
    const rows = db.prepare(`
      SELECT room_a, room_b, agreements, wins, losses, ties
      FROM room_correlations
      WHERE agreements >= 5
      ORDER BY agreements DESC
    `).all() as any[];
    db.close();

    const pairs = rows.map((r: any) => {
      const total = r.wins + r.losses + r.ties;
      const wr = total > 0 ? Math.round(r.wins / total * 1000) / 10 : 0;
      return {
        rooms: [r.room_a, r.room_b],
        agreements: r.agreements,
        wins: r.wins,
        losses: r.losses,
        ties: r.ties,
        wr,
        score: Math.round(wr * Math.log2(r.agreements + 1) * 10) / 10,
      };
    }).sort((a: any, b: any) => b.score - a.score).slice(0, 15);

    return res.json({ ok: true, pairs });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── CSV export: signals ───────────────────────────────────────────────────────
router.get("/bot/export-signals", authMiddlewareOrToken, (req, res) => {
  try {
    const db = getDb(true);
    const limit = Math.min(Number(req.query.limit) || 500, 2000);
    const rows = db.prepare(`
      SELECT cs.id, cs.signal_kind, cs.color, cs.classification, cs.rooms_agreed,
        cs.outcome, cs.fired_at,
        ROUND(COALESCE(sc_agg.total_score, 0), 3) AS total_score,
        cs.confidence_pct, cs.signal_tier, cs.coalition_rooms
      FROM consensus_signals cs
      LEFT JOIN (
        SELECT consensus_id, SUM(room_score) AS total_score
        FROM signal_context GROUP BY consensus_id
      ) sc_agg ON sc_agg.consensus_id = cs.id
      ORDER BY cs.id DESC LIMIT ?
    `).all(limit) as any[];
    db.close();
    const header = "id,signal_kind,color,classification,rooms_agreed,outcome,fired_at,total_score,confidence_pct,signal_tier,coalition_rooms\n";
    const csv = header + rows.map((r: any) =>
      `${r.id},${r.signal_kind},${r.color ?? ""},${r.classification ?? ""},${(r.rooms_agreed ?? "").replace(/,/g, ";")},${r.outcome},${r.fired_at},${r.total_score},${r.confidence_pct ?? ""},${r.signal_tier ?? ""},${(r.coalition_rooms ?? "").replace(/,/g, ";")}`
    ).join("\n");
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", "attachment; filename=signals_export.csv");
    return res.send(csv);
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── CSV export: bankroll ──────────────────────────────────────────────────────
router.get("/bot/export-bankroll", authMiddlewareOrToken, (_req, res) => {
  try {
    const db = getDb(true);
    const rows = db.prepare("SELECT * FROM bankroll_entries ORDER BY id DESC").all() as any[];
    db.close();
    const header = "id,amount,type,note,created_at\n";
    const csv = header + rows.map((r: any) =>
      `${r.id},${r.amount},${r.type},"${(r.note ?? "").replace(/"/g, '""')}",${r.created_at}`
    ).join("\n");
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", "attachment; filename=bankroll_export.csv");
    return res.send(csv);
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/bot/activity-feed", authMiddleware, (req, res) => {
  const limit = Math.min(parseInt(req.query.limit as string) || 100, 500);
  const category = (req.query.category as string) || null;
  const since = (req.query.since as string) || null;
  const db = getDb(true);
  try {
    const clauses: string[] = [];
    const params: any[] = [];
    if (category) {
      clauses.push("category = ?");
      params.push(category);
    }
    if (since) {
      clauses.push("created_at > ?");
      params.push(since);
    }
    const where = clauses.length > 0 ? "WHERE " + clauses.join(" AND ") : "";
    let rows: any[];
    try {
      rows = db.prepare(
        `SELECT id, event_type, category, title, detail, room_handle, severity, created_at
         FROM activity_feed ${where} ORDER BY id DESC LIMIT ?`
      ).all(...params, limit) as any[];
    } catch {
      rows = [];
    }
    return res.json({ events: rows });
  } catch (err: any) {
    console.error("[API error]", err);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

async function initWithRetry(fn: () => void, label: string, retries = 10, delayMs = 1000): Promise<void> {
  for (let i = 0; i < retries; i++) {
    try { fn(); return; } catch (e) {
      if (i < retries - 1) {
        await new Promise(r => setTimeout(r, delayMs));
      } else {
        console.warn(`[${label}] DB init failed after ${retries} attempts:`, (e as Error).message);
      }
    }
  }
}

// ── Per-day calendar stats (last 60 days) ────────────────────────────────────
router.get("/bot/daily-stats", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);
    const rows = db.prepare(`
      SELECT
        DATE(fired_at) AS day,
        COUNT(*) AS total,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties
      FROM consensus_signals
      WHERE outcome IN ('win','loss','tie')
        AND fired_at >= DATE('now', '-60 days')
      GROUP BY day
      ORDER BY day ASC
    `).all() as { day: string; total: number; wins: number; losses: number; ties: number }[];
    db.close();
    const days = rows.map(r => ({
      day:    r.day,
      total:  r.total,
      wins:   r.wins,
      losses: r.losses,
      ties:   r.ties,
      wr:     r.wins + r.losses + r.ties > 0
                ? Math.round(((r.wins + r.ties * 0.5) / (r.wins + r.losses + r.ties)) * 1000) / 10
                : null,
    }));
    return res.json({ ok: true, days });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── G0 Metrics — full cross-dimensional G0 analysis over all signals ─────────
router.get("/bot/g0-metrics", authMiddleware, (_req, res) => {
  try {
    const db = getDb(true);

    const sql = (q: string) => db.prepare(q).all() as any[];

    const byKind = sql(`
      SELECT signal_kind AS label,
        COUNT(*) AS total,
        SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        ROUND(100.0*SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) AS g0_pct,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),1) AS wr,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN confidence_pct END),1) AS avg_conf,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN secs_to_result END),1) AS avg_secs
      FROM consensus_signals
      WHERE signal_kind IN ('GOLDEN','SOLO_ELITE','PLATINUM','FLASH','SEQUENCE')
      GROUP BY signal_kind ORDER BY g0_pct DESC
    `);

    const byColor = sql(`
      SELECT color AS label,
        COUNT(*) AS total,
        SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        ROUND(100.0*SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) AS g0_pct,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),1) AS wr,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN confidence_pct END),1) AS avg_conf,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN secs_to_result END),1) AS avg_secs
      FROM consensus_signals WHERE color IN ('blue','red')
      GROUP BY color ORDER BY g0_pct DESC
    `);

    const byConf = sql(`
      SELECT
        CASE
          WHEN confidence_pct < 70  THEN '<70'
          WHEN confidence_pct < 80  THEN '70–79'
          WHEN confidence_pct < 85  THEN '80–84'
          WHEN confidence_pct < 90  THEN '85–89'
          WHEN confidence_pct < 95  THEN '90–94'
          ELSE '95+'
        END AS label,
        COUNT(*) AS total,
        SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        ROUND(100.0*SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) AS g0_pct,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),1) AS wr,
        MIN(confidence_pct) AS _sort
      FROM consensus_signals WHERE confidence_pct IS NOT NULL AND outcome IN ('win','loss')
      GROUP BY label ORDER BY _sort ASC
    `);

    const bySpread = sql(`
      SELECT COALESCE(spread_label,'No spread') AS label,
        COUNT(*) AS total,
        SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        ROUND(100.0*SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) AS g0_pct,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),1) AS wr,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN confidence_pct END),1) AS avg_conf,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN secs_to_result END),1) AS avg_secs
      FROM consensus_signals
      GROUP BY label ORDER BY total DESC
    `);

    const byRooms = sql(`
      SELECT CAST(rooms_count AS TEXT) AS label,
        COUNT(*) AS total,
        SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        ROUND(100.0*SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) AS g0_pct,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),1) AS wr,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN confidence_pct END),1) AS avg_conf,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN secs_to_result END),1) AS avg_secs
      FROM consensus_signals WHERE rooms_count IS NOT NULL
      GROUP BY rooms_count ORDER BY rooms_count ASC
    `);

    const byStreak = sql(`
      SELECT
        CASE
          WHEN streak_count IS NULL THEN 'None'
          WHEN streak_count = 0 THEN '0'
          WHEN streak_count = 1 THEN '1'
          WHEN streak_count BETWEEN 2 AND 3 THEN '2–3'
          WHEN streak_count BETWEEN 4 AND 6 THEN '4–6'
          WHEN streak_count BETWEEN 7 AND 10 THEN '7–10'
          ELSE '11+'
        END AS label,
        COUNT(*) AS total,
        SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        ROUND(100.0*SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) AS g0_pct,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),1) AS wr,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN confidence_pct END),1) AS avg_conf,
        MIN(COALESCE(streak_count,0)) AS _sort
      FROM consensus_signals
      GROUP BY label ORDER BY _sort ASC
    `);

    const byHour = sql(`
      SELECT
        printf('%02d:00', CAST(strftime('%H', fired_at) AS INTEGER)) AS label,
        CAST(strftime('%H', fired_at) AS INTEGER) AS hour,
        COUNT(*) AS total,
        SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        ROUND(100.0*SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) AS g0_pct,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),1) AS wr
      FROM consensus_signals
      GROUP BY hour ORDER BY hour ASC
    `);

    const crossKindColor = sql(`
      SELECT signal_kind, color,
        COUNT(*) AS total,
        SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        ROUND(100.0*SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) AS g0_pct,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),1) AS wr,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN confidence_pct END),1) AS avg_conf,
        ROUND(AVG(CASE WHEN outcome IN ('win','loss') THEN secs_to_result END),1) AS avg_secs
      FROM consensus_signals
      WHERE signal_kind IN ('GOLDEN','SOLO_ELITE','PLATINUM','FLASH','SEQUENCE')
        AND color IN ('blue','red')
        AND outcome IN ('win','loss')
      GROUP BY signal_kind, color ORDER BY signal_kind, color
    `);

    const totals = (db.prepare(`
      SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
        SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN outcome='tie' THEN 1 ELSE 0 END) AS ties,
        SUM(CASE WHEN outcome='recovered' THEN 1 ELSE 0 END) AS recovered,
        ROUND(100.0*SUM(CASE WHEN won_at_gale=0 AND outcome='win' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) AS g0_pct,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),1) AS wr,
        ROUND(AVG(CASE WHEN outcome='win' AND won_at_gale=0 THEN secs_to_result END),1) AS avg_secs_g0_win,
        ROUND(AVG(CASE WHEN outcome='loss' THEN secs_to_result END),1) AS avg_secs_loss
      FROM consensus_signals WHERE outcome IN ('win','loss','tie','recovered')
    `).get() as any);

    db.close();
    return res.json({ ok: true, totals, byKind, byColor, byConf, bySpread, byRooms, byStreak, byHour, crossKindColor });
  } catch (e: any) {
    console.error("[API error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── Elite Stack reports generated by bot/*.py audit tools ────────────────────
router.get("/bot/result-lag-patterns", authMiddleware, (_req, res) => {
  return res.json(readBotDataReport("result_lag_patterns.json"));
});

router.get("/bot/elite-stack-audit", authMiddleware, (_req, res) => {
  return res.json(readBotDataReport("elite_stack_audit.json"));
});

router.get("/bot/room-cleaner-report", authMiddleware, (_req, res) => {
  return res.json(readBotDataReport("room_cleaner_report.json"));
});

router.get("/bot/omni-score-report", authMiddleware, (_req, res) => {
  return res.json(readBotDataReport("omni_score_report.json"));
});

// ── Floor Monitor ─────────────────────────────────────────────────────────────
router.get("/bot/floors", authMiddleware, (_req, res) => {
  try {
    const db = getDb();

    const FLOOR_META: Record<string, { label: string; peakWr: number | null; peakVol: number | null; peakDate: string; floorN: string }> = {
      LIVE:  { label: "Live Engine",           peakWr: null,  peakVol: null, peakDate: "ongoing", floorN: "live" },
      MAR19: { label: "F0a · MAR 19 Origin",   peakWr: 89.5,  peakVol: 19,   peakDate: "Mar 19",  floorN: "0a"  },
      MAR20: { label: "F0b · MAR 20 Volume",   peakWr: 83.1,  peakVol: 579,  peakDate: "Mar 20",  floorN: "0b"  },
      MAR21: { label: "F0c · MAR 21 Best WR",  peakWr: 93.6,  peakVol: 280,  peakDate: "Mar 21",  floorN: "0c"  },
      APR20: { label: "F1 · APR 20 Perfect",   peakWr: 100.0, peakVol: 17,   peakDate: "Apr 20",  floorN: "1"   },
      APR30: { label: "F2 · APR 30 All-Kinds", peakWr: 90.6,  peakVol: 170,  peakDate: "Apr 30",  floorN: "2"   },
      APR19: { label: "F3 · APR 19 Golden",    peakWr: 90.3,  peakVol: 62,   peakDate: "Apr 19",  floorN: "3"   },
      APR21: { label: "F4 · APR 21 Golden",    peakWr: 90.3,  peakVol: 227,  peakDate: "Apr 21",  floorN: "4"   },
      MAY02: { label: "F5 · MAY 02 Pipeline",  peakWr: 87.8,  peakVol: 109,  peakDate: "May 2",   floorN: "5"   },
      MAY01: { label: "F6 · MAY 01 Flash",     peakWr: 87.4,  peakVol: 101,  peakDate: "May 1",   floorN: "6"   },
      APR26: { label: "F7 · APR 26 Weekend",   peakWr: 87.2,  peakVol: 188,  peakDate: "Apr 26",  floorN: "7"   },
      APR24: { label: "F8 · APR 24 Volume",    peakWr: 84.9,  peakVol: 218,  peakDate: "Apr 24",  floorN: "8"   },
      MAY04: { label: "F9 · MAY 04 MaxVol",    peakWr: 83.1,  peakVol: 267,  peakDate: "May 4",   floorN: "9"   },
      APR22: { label: "F10 · APR 22 Solo100",  peakWr: 83.0,  peakVol: 159,  peakDate: "Apr 22",  floorN: "10"  },
      APR29: { label: "F11 · APR 29 Flash1",   peakWr: 81.8,  peakVol: 110,  peakDate: "Apr 29",  floorN: "11"  },
      APR28: { label: "F12 · APR 28 Complex",  peakWr: 81.5,  peakVol: 286,  peakDate: "Apr 28",  floorN: "12"  },
      APR25: { label: "F13 · APR 25 Pre-WE",   peakWr: 82.1,  peakVol: 117,  peakDate: "Apr 25",  floorN: "13"  },
      APR27: { label: "F14 · APR 27 Post-WE",  peakWr: 80.5,  peakVol: 261,  peakDate: "Apr 27",  floorN: "14"  },
      JUN12A:{ label: "N1 · JUN 12 Avalanche", peakWr: 81.8,  peakVol: null, peakDate: "Jun 12",  floorN: "N1"  },
      JUN12B:{ label: "N2 · JUN 12 EliteGuard",peakWr: 81.8,  peakVol: null, peakDate: "Jun 12",  floorN: "N2"  },
    };
    const FLOOR_ORDER = [
      "LIVE","MAR19","MAR20","MAR21","APR20","APR30","APR19","APR21",
      "MAY02","MAY01","APR26","APR24","MAY04","APR22","APR29","APR28","APR25","APR27",
      "JUN12A","JUN12B",
    ];

    // All-time fired per floor
    const firedRows = db.prepare(`
      SELECT source_floor,
        COUNT(*) AS fired,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)
          /NULLIF(SUM(CASE WHEN outcome IN('win','loss') THEN 1 ELSE 0 END),0),1) AS wr,
        MAX(fired_at) AS last_fired_at
      FROM consensus_signals
      WHERE source_floor IS NOT NULL
      GROUP BY source_floor
    `).all() as any[];

    // Today fired per floor
    const todayFiredRows = db.prepare(`
      SELECT source_floor, COUNT(*) AS today_fired,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS today_wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS today_losses
      FROM consensus_signals
      WHERE source_floor IS NOT NULL AND date(fired_at)=date('now')
      GROUP BY source_floor
    `).all() as any[];

    // All-time blocked per floor
    const blockedRows = db.prepare(`
      SELECT source_floor,
        COUNT(*) AS blocked,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS shadow_wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS shadow_losses,
        ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)
          /NULLIF(SUM(CASE WHEN outcome IN('win','loss') THEN 1 ELSE 0 END),0),1) AS shadow_wr
      FROM blocked_signals
      WHERE source_floor IS NOT NULL
      GROUP BY source_floor
    `).all() as any[];

    // Today blocked per floor
    const todayBlockedRows = db.prepare(`
      SELECT source_floor, COUNT(*) AS today_blocked
      FROM blocked_signals
      WHERE source_floor IS NOT NULL AND date(blocked_at)=date('now')
      GROUP BY source_floor
    `).all() as any[];

    // Top gate per floor (most frequent block reason)
    const topGateRows = db.prepare(`
      SELECT source_floor, gate_reason, COUNT(*) AS n
      FROM blocked_signals
      WHERE source_floor IS NOT NULL
      GROUP BY source_floor, gate_reason
      ORDER BY n DESC
    `).all() as any[];

    // Index all results by floor_id
    const firedByFloor: Record<string, any>  = {};
    firedRows.forEach((r: any) => { firedByFloor[r.source_floor] = r; });
    const todayFiredByFloor: Record<string, any> = {};
    todayFiredRows.forEach((r: any) => { todayFiredByFloor[r.source_floor] = r; });
    const blockedByFloor: Record<string, any> = {};
    blockedRows.forEach((r: any) => { blockedByFloor[r.source_floor] = r; });
    const todayBlockedByFloor: Record<string, any> = {};
    todayBlockedRows.forEach((r: any) => { todayBlockedByFloor[r.source_floor] = r; });
    const topGateByFloor: Record<string, string> = {};
    topGateRows.forEach((r: any) => {
      if (!topGateByFloor[r.source_floor]) topGateByFloor[r.source_floor] = r.gate_reason;
    });

    const floors = FLOOR_ORDER.map(fid => {
      const meta  = FLOOR_META[fid] ?? { label: fid, peakWr: null, peakVol: null, peakDate: "?", floorN: "?" };
      const f     = firedByFloor[fid]      ?? { fired: 0, wins: 0, losses: 0, ties: 0, wr: null, last_fired_at: null };
      const tf    = todayFiredByFloor[fid] ?? { today_fired: 0, today_wins: 0, today_losses: 0 };
      const b     = blockedByFloor[fid]    ?? { blocked: 0, shadow_wins: 0, shadow_losses: 0, shadow_wr: null };
      const tb    = todayBlockedByFloor[fid] ?? { today_blocked: 0 };
      const totalAttempts = (f.fired ?? 0) + (b.blocked ?? 0);
      const fireRate = totalAttempts > 0 ? Math.round(100 * (f.fired ?? 0) / totalAttempts) : null;
      const todayAttempts = (tf.today_fired ?? 0) + (tb.today_blocked ?? 0);
      const todayFireRate = todayAttempts > 0 ? Math.round(100 * (tf.today_fired ?? 0) / todayAttempts) : null;

      let status = "no_data";
      if (tf.today_fired > 0) status = "active";
      else if (f.fired > 0 && f.last_fired_at) {
        const lastMs = new Date(f.last_fired_at + "Z").getTime();
        const agoMs  = Date.now() - lastMs;
        if (agoMs < 4 * 3600 * 1000) status = "recent";
        else if (agoMs < 24 * 3600 * 1000) status = "idle_today";
        else status = "dormant";
      }

      return {
        id: fid,
        ...meta,
        allTime: {
          fired:      f.fired       ?? 0,
          wins:       f.wins        ?? 0,
          losses:     f.losses      ?? 0,
          ties:       f.ties        ?? 0,
          wr:         f.wr          ?? null,
          blocked:    b.blocked     ?? 0,
          shadowWr:   b.shadow_wr   ?? null,
          fireRate,
          lastFiredAt: f.last_fired_at ?? null,
        },
        today: {
          fired:      tf.today_fired   ?? 0,
          wins:       tf.today_wins    ?? 0,
          losses:     tf.today_losses  ?? 0,
          blocked:    tb.today_blocked ?? 0,
          fireRate:   todayFireRate,
        },
        topBlockGate: topGateByFloor[fid] ?? null,
        status,
      };
    });

    db.close();
    return res.json({ ok: true, floors, asOf: new Date().toISOString() });
  } catch (e: any) {
    console.error("[API /bot/floors error]", e);
    return res.status(500).json({ error: "Internal server error" });
  }
});

// ── /bot/signal-feed — last 60 signals with full details for live feed ──────
router.get("/bot/signal-feed", authMiddleware, (_req, res) => {
  const db = getDb(true);
  try {
    const signals = db.prepare(`
      SELECT id, signal_kind, color, outcome, gale_depth, won_at_gale,
             confidence_pct, fired_at, resolved_at, source_floor,
             rooms_count, coalition_rooms, secs_to_result, rounds_to_result
      FROM consensus_signals
      ORDER BY id DESC LIMIT 60
    `).all() as any[];

    const today = db.prepare(`
      SELECT
        COUNT(*) AS fired,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties,
        SUM(CASE WHEN outcome='pending' THEN 1 ELSE 0 END) AS pending,
        ROUND(100.0*(SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)+SUM(CASE WHEN outcome='tie' THEN 1 ELSE 0 END))
          /NULLIF(SUM(CASE WHEN outcome IN('win','loss','tie') THEN 1 ELSE 0 END),0),1) AS wr
      FROM consensus_signals
      WHERE DATE(fired_at) = DATE('now')
    `).get() as any;

    // Median time-to-result — robust to the few very-long-tail signals that skew the mean
    const medSecs = db.prepare(`
      SELECT secs_to_result AS v
      FROM consensus_signals
      WHERE DATE(fired_at) = DATE('now')
        AND outcome IN('win','loss','tie')
        AND secs_to_result IS NOT NULL
      ORDER BY secs_to_result
      LIMIT 1
      OFFSET (
        SELECT COUNT(*) / 2
        FROM consensus_signals
        WHERE DATE(fired_at) = DATE('now')
          AND outcome IN('win','loss','tie')
          AND secs_to_result IS NOT NULL
      )
    `).get() as any;
    if (today) today.median_secs = medSecs ? Math.round(Number(medSecs.v) * 10) / 10 : null;

    return res.json({ ok: true, signals, today });
  } catch (e: any) {
    console.error("[API /bot/signal-feed error]", e);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

// ── /bot/floor-battle — floors ranked by today's live WR ────────────────────
router.get("/bot/floor-battle", authMiddleware, (_req, res) => {
  const db = getDb(true);
  try {
    const FLOOR_META: Record<string, { label: string; peakWr: number | null; rank: number }> = {
      LIVE:  { label: "Live Engine",           peakWr: null,  rank: 0  },
      MAR19: { label: "F0a · MAR 19 Origin",   peakWr: 89.5,  rank: 6  },
      MAR20: { label: "F0b · MAR 20 Volume",   peakWr: 83.1,  rank: 11 },
      MAR21: { label: "F0c · MAR 21 Best WR",  peakWr: 93.6,  rank: 2  },
      APR20: { label: "F1 · APR 20 Perfect",   peakWr: 100.0, rank: 1  },
      APR30: { label: "F2 · APR 30 All-Kinds", peakWr: 90.6,  rank: 3  },
      APR19: { label: "F3 · APR 19 Golden",    peakWr: 90.3,  rank: 4  },
      APR21: { label: "F4 · APR 21 Golden",    peakWr: 90.3,  rank: 5  },
      MAY02: { label: "F5 · MAY 02 Pipeline",  peakWr: 87.8,  rank: 7  },
      MAY01: { label: "F6 · MAY 01 Flash",     peakWr: 87.4,  rank: 8  },
      APR26: { label: "F7 · APR 26 Weekend",   peakWr: 87.2,  rank: 9  },
      APR24: { label: "F8 · APR 24 Volume",    peakWr: 84.9,  rank: 10 },
      MAY04: { label: "F9 · MAY 04 MaxVol",    peakWr: 83.1,  rank: 12 },
      APR22: { label: "F10 · APR 22 Solo100",  peakWr: 83.0,  rank: 13 },
      APR29: { label: "F11 · APR 29 Flash1",   peakWr: 81.8,  rank: 15 },
      APR28: { label: "F12 · APR 28 Complex",  peakWr: 81.5,  rank: 16 },
      APR25: { label: "F13 · APR 25 Pre-WE",   peakWr: 82.1,  rank: 14 },
      APR27: { label: "F14 · APR 27 Post-WE",  peakWr: 80.5,  rank: 17 },
      JUN12A:{ label: "N1 · JUN 12 Avalanche", peakWr: 81.8,  rank: 33 },
      JUN12B:{ label: "N2 · JUN 12 EliteGuard",peakWr: 81.8,  rank: 34 },
    };

    const todayRows = db.prepare(`
      SELECT source_floor,
        COUNT(*) AS fired,
        SUM(CASE WHEN outcome='win'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN outcome='tie'  THEN 1 ELSE 0 END) AS ties,
        SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN outcome='pending' THEN 1 ELSE 0 END) AS pending,
        ROUND(100.0*(SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)+SUM(CASE WHEN outcome='tie' THEN 1 ELSE 0 END))
          /NULLIF(SUM(CASE WHEN outcome IN('win','loss','tie') THEN 1 ELSE 0 END),0),1) AS live_wr
      FROM consensus_signals
      WHERE DATE(fired_at) = DATE('now') AND source_floor IS NOT NULL
      GROUP BY source_floor
    `).all() as any[];

    const todayMap: Record<string, any> = {};
    for (const r of todayRows) todayMap[r.source_floor] = r;

    const floors = Object.keys(FLOOR_META)
      .filter(fid => fid !== "LIVE")
      .map(fid => {
        const meta = FLOOR_META[fid];
        const td   = todayMap[fid];
        const liveWr  = td?.live_wr  ?? null;
        const haslive = td && (td.wins + td.losses + td.ties) >= 3;
        const effectiveWr = haslive ? liveWr : meta.peakWr;
        const wrSource    = haslive ? "hoje" : "pico";
        return {
          fid,
          label:       meta.label,
          rank:        meta.rank,
          peakWr:      meta.peakWr,
          liveWr,
          effectiveWr,
          wrSource,
          fired:   td?.fired   ?? 0,
          wins:    td?.wins    ?? 0,
          ties:    td?.ties    ?? 0,
          losses:  td?.losses  ?? 0,
          pending: td?.pending ?? 0,
        };
      })
      .sort((a, b) => (b.effectiveWr ?? 0) - (a.effectiveWr ?? 0));

    return res.json({ ok: true, floors, asOf: new Date().toISOString() });
  } catch (e: any) {
    console.error("[API /bot/floor-battle error]", e);
    return res.status(500).json({ error: "Internal server error" });
  } finally {
    db.close();
  }
});

setTimeout(() => {
  Promise.all([
    initWithRetry(initDashboardUsers, "users"),
    initWithRetry(initBroadcast, "broadcast"),
    initWithRetry(initBankrollTracker, "bankroll"),
  ]).then(() => console.log("[init] DB tables ready"));
}, 0);

export default router;
