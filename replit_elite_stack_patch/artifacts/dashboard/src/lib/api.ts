const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const API = `${BASE}/api`;

function token() {
  return localStorage.getItem("bacbo_token") || "";
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token()}`,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    localStorage.removeItem("bacbo_token");
    window.location.href = window.location.pathname.replace(/\/$/, "") + "/login";
    throw new Error("Session expired — please log in again.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

export const api = {
  login:      (email: string, password: string) =>
    req<{ token: string }>("POST", "/auth/login", { email, password }),
  status:     () => req<any>("GET", "/bot/status"),
  bankroll:   () => req<any>("GET", "/bot/bankroll"),
  leaderboard:() => req<any>("GET", "/bot/leaderboard"),
  history:    () => req<any>("GET", "/bot/history"),
  analytics:  () => req<any>("GET", "/bot/analytics"),
  outcome:    (outcome: "win" | "loss" | "tie" | "undo") =>
    req<any>("POST", "/bot/outcome", { outcome }),
  resetSession: () => req<any>("POST", "/bot/reset-session"),

  // User management
  users:          () => req<{ users: { id: number; email: string; is_admin: boolean; created_at: string }[] }>("GET", "/users"),
  addUser:        (email: string, password: string) =>
    req<{ ok: boolean }>("POST", "/users", { email, password }),
  changePassword: (email: string, password: string) =>
    req<{ ok: boolean }>("PUT", `/users/${encodeURIComponent(email)}/password`, { password }),
  removeUser:     (email: string) =>
    req<{ ok: boolean }>("DELETE", `/users/${encodeURIComponent(email)}`),

  // Rooms management
  rooms:       () => req<{ rooms: any[] }>("GET", "/bot/rooms"),
  addRoom:     (handle: string) => req<{ ok: boolean; handle: string }>("POST", "/bot/rooms", { handle }),
  removeRoom:  (handle: string) => req<{ ok: boolean }>("DELETE", `/bot/rooms/${encodeURIComponent(handle)}`),

  // Cycle monitoring
  cycles:           () => req<{ active: any[]; recent: any[]; stats: any[] }>("GET", "/bot/cycles"),
  cyclesRoom:       (handle: string) => req<{ handle: string; current: any | null; history: any[] }>("GET", `/bot/cycles/${encodeURIComponent(handle.replace(/^@/, ""))}`),

  // Telegram auth setup
  telegramStatus:  () => req<any>("GET",  "/bot/telegram/status"),
  telegramRequest: () => req<any>("POST", "/bot/telegram/request"),
  telegramVerify:  (code: string) => req<any>("POST", "/bot/telegram/verify", { code }),

  // Engine health (T012)
  engineHealth: () => req<any>("GET", "/bot/engine-health"),

  trends: (days?: number) => req<any>("GET", `/bot/trends${days ? `?days=${days}` : ""}`),
  heatmap: (days?: number) => req<any>("GET", `/bot/heatmap${days ? `?days=${days}` : ""}`),
  historyFiltered: (params: { kind?: string; outcome?: string; from?: string; to?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params.kind) q.set("kind", params.kind);
    if (params.outcome) q.set("outcome", params.outcome);
    if (params.from) q.set("from", params.from);
    if (params.to) q.set("to", params.to);
    if (params.limit) q.set("limit", String(params.limit));
    return req<any>("GET", `/bot/history-filtered?${q.toString()}`);
  },
  bankrollTracker: () => req<any>("GET", "/bot/bankroll-tracker"),
  addBankrollEntry: (amount: number, type: string, note: string) => req<any>("POST", "/bot/bankroll-tracker", { amount, type, note }),
  deleteBankrollEntry: (id: number) => req<any>("DELETE", `/bot/bankroll-tracker/${id}`),
  heatmapDow: (days?: number) => req<any>("GET", `/bot/heatmap-dow${days ? `?days=${days}` : ""}`),
  heatmapDayHour: (dow: number, days?: number) => req<any>("GET", `/bot/heatmap-day-hour?dow=${dow}${days ? `&days=${days}` : ""}`),
  bankrollPnl: () => req<any>("GET", "/bot/bankroll-pnl"),
  confidenceTrends: (days?: number) => req<any>("GET", `/bot/confidence-trends${days ? `?days=${days}` : ""}`),
  roomHealth: () => req<any>("GET", "/bot/room-health"),
  winStreak: () => req<any>("GET", "/bot/win-streak"),
  roomCorrelations: () => req<any>("GET", "/bot/room-correlations"),
  martingaleCalc: (bankroll: number, base: number, multiplier?: number) =>
    req<any>("GET", `/bot/martingale-calc?bankroll=${bankroll}&base=${base}&multiplier=${multiplier ?? 2}`),
  colorTimeline: () => req<any>("GET", "/bot/color-timeline"),
  simulate: (balance: number, bet: number, days: number) =>
    req<any>("GET", `/bot/simulate?balance=${balance}&bet=${bet}&days=${days}`),
  activityFeed: (params?: { category?: string; limit?: number; since?: string }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set("category", params.category);
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.since) q.set("since", params.since);
    return req<any>("GET", `/bot/activity-feed?${q.toString()}`);
  },
  bestPairs:   () => req<any>("GET", "/bot/best-pairs"),
  dailyStats:  () => req<any>("GET", "/bot/daily-stats"),
  g0Metrics:   () => req<any>("GET", "/bot/g0-metrics"),
  resultLagPatterns: () => req<any>("GET", "/bot/result-lag-patterns"),
  eliteStackAudit:   () => req<any>("GET", "/bot/elite-stack-audit"),
  roomCleanerReport: () => req<any>("GET", "/bot/room-cleaner-report"),
  omniScoreReport:   () => req<any>("GET", "/bot/omni-score-report"),
  martingaleAudit:   () => req<any>("GET", "/bot/martingale-audit"),
  truthVerification: () => req<any>("GET", "/bot/truth-verification"),
  systemHealthAudit: () => req<any>("GET", "/bot/system-health-audit"),
  brtHourWr:   () => req<any>("GET", "/bot/brt-hour-wr"),
  exportSignalsUrl: () => `${API}/bot/export-signals?token=${token()}`,
  exportBankrollUrl: () => `${API}/bot/export-bankroll?token=${token()}`,

  // Broadcast channel
  broadcastMessages:      () => fetch(`${API}/broadcast/messages`).then(r => r.json()),
  broadcastPost:          (content: string) =>
    req<any>("POST", "/broadcast/messages", { content }),
  broadcastDelete:        (id: number) => req<any>("DELETE", `/broadcast/messages/${id}`),
  broadcastSubscribe:     (email: string) =>
    fetch(`${API}/broadcast/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }).then(r => r.json()),
  broadcastSubscribers:   () => req<any>("GET", "/broadcast/subscribers"),
  broadcastUnsubscribe:   (email: string) =>
    req<any>("DELETE", `/broadcast/subscribers/${encodeURIComponent(email)}`),

  floors:      () => req<{ ok: boolean; floors: any[]; asOf: string }>("GET", "/bot/floors"),
  signalFeed:  () => req<{ ok: boolean; signals: any[]; today: any }>("GET", "/bot/signal-feed"),
  floorBattle: () => req<{ ok: boolean; floors: any[]; asOf: string }>("GET", "/bot/floor-battle"),
};

export type StreamStatus = "connecting" | "connected" | "disconnected" | "error";

export interface StreamCallbacks {
  onData: (data: any) => void;
  onStatusChange: (status: StreamStatus) => void;
  onParseError?: (raw: string) => void;
}

export function openBroadcastStream(callbacks: StreamCallbacks): () => void {
  callbacks.onStatusChange("connecting");
  const es = new EventSource(`${API}/broadcast/stream`);
  es.onopen = () => { callbacks.onStatusChange("connected"); };
  es.onmessage = (e) => {
    try {
      callbacks.onData(JSON.parse(e.data));
    } catch (err) {
      if (import.meta.env.DEV) console.warn("[BroadcastSSE] Failed to parse message:", err, e.data);
      callbacks.onStatusChange("error");
      callbacks.onParseError?.(e.data);
    }
  };
  es.onerror = () => {
    const isClosed = es.readyState === EventSource.CLOSED;
    callbacks.onStatusChange(isClosed ? "disconnected" : "connecting");
  };
  return () => es.close();
}

export function openStatusStream(callbacks: StreamCallbacks): () => void {
  callbacks.onStatusChange("connecting");
  const t = encodeURIComponent(token());
  const es = new EventSource(`${API}/bot/stream?token=${t}`);
  es.onopen    = () => { callbacks.onStatusChange("connected"); };
  es.onmessage = (e) => {
    try {
      callbacks.onData(JSON.parse(e.data));
    } catch (err) {
      if (import.meta.env.DEV) console.warn("[StatusSSE] Failed to parse message:", err, e.data);
      callbacks.onStatusChange("error");
      callbacks.onParseError?.(e.data);
    }
  };
  es.onerror   = () => {
    const isClosed = es.readyState === EventSource.CLOSED;
    callbacks.onStatusChange(isClosed ? "disconnected" : "connecting");
  };
  return () => es.close();
}
