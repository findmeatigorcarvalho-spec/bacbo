import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { api, openStatusStream, type StreamStatus } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useLang } from "@/contexts/LanguageContext";
import { useTheme } from "@/contexts/ThemeContext";
import { useSignalAlert } from "@/hooks/use-signal-alert";
import { useWakeLock } from "@/hooks/use-wake-lock";
import { getIsAdmin, LOSS_COOLDOWN_THRESHOLD, TIE_PRESSURE_THRESHOLD } from "@/components/shared";

import LiveTab from "@/components/tabs/LiveTab";
import DashboardTab from "@/components/tabs/DashboardTab";
import LeaderboardTab from "@/components/tabs/LeaderboardTab";
import HistoryTab from "@/components/tabs/HistoryTab";
import RoomsTab from "@/components/tabs/RoomsTab";
import CyclesTab from "@/components/tabs/CyclesTab";
import UsersTab from "@/components/tabs/UsersTab";
import BroadcastTab from "@/components/tabs/BroadcastTab";
import EngineTab from "@/components/tabs/EngineTab";
import HeatmapTab from "@/components/tabs/HeatmapTab";
import BankrollTab from "@/components/tabs/BankrollTab";
import ActivityTab from "@/components/tabs/ActivityTab";
import G0Tab from "@/components/tabs/G0Tab";
import GuideTab from "@/components/tabs/GuideTab";
import FloorsTab from "@/components/tabs/FloorsTab";
import SignalFeedTab from "@/components/tabs/SignalFeedTab";
import FloorBattleTab from "@/components/tabs/FloorBattleTab";

type TabKey = "live" | "dashboard" | "leaderboard" | "history" | "users" | "rooms" | "cycles" | "broadcast" | "engine" | "heatmap" | "bankroll" | "activity" | "g0" | "guide" | "floors" | "feed" | "battle";

function parseUtc(value?: string | null): Date | null {
  if (!value) return null;
  const text = value.includes("Z") || value.includes("+") ? value : `${value}Z`;
  const d = new Date(text);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatResultSeconds(result: any): string {
  const direct = Number(result?.secsToResult);
  if (Number.isFinite(direct) && direct >= 0) return `${Math.round(direct)}s from fire`;
  const fired = parseUtc(result?.firedAt);
  const resolved = parseUtc(result?.resolvedAt);
  if (fired && resolved) {
    const secs = Math.max(0, Math.round((resolved.getTime() - fired.getTime()) / 1000));
    return `${secs}s from fire`;
  }
  return "timing pending";
}

function resultColorClasses(color?: string | null): string {
  if (color === "blue") return "bg-blue-600/90 text-white border-blue-300/60";
  if (color === "red") return "bg-red-600/90 text-white border-red-300/60";
  if (color === "tie") return "bg-yellow-500/90 text-black border-yellow-200/70";
  return "bg-gray-700 text-gray-200 border-gray-500";
}

function resultLabel(color?: string | null): string {
  if (color === "blue") return "BLUE";
  if (color === "red") return "RED";
  if (color === "tie") return "TIE";
  return "—";
}

function outcomeBadge(result: any): string {
  if (result?.outcome === "tie") return "T";
  if (result?.outcome === "loss") return "L";
  const g = Number(result?.wonAtGale ?? 0);
  return g > 0 ? `G${g}` : "G0";
}

export default function DashboardPage() {
  const [, setLoc] = useLocation();
  const { toast } = useToast();
  const { t, toggleLang } = useLang();
  const qc = useQueryClient();
  const { theme, toggleTheme } = useTheme();
  const [tab, setTab] = useState<TabKey>("live");
  const [cycleRoom, setCycleRoom] = useState<string | null>(null);

  const [histKind, setHistKind] = useState("all");
  const [histOutcome, setHistOutcome] = useState("all");
  const [histFrom, setHistFrom] = useState("");
  const [histTo, setHistTo] = useState("");

  const [brAmount, setBrAmount] = useState("");
  const [brType, setBrType] = useState<"win" | "loss" | "deposit" | "withdraw">("win");
  const [brNote, setBrNote] = useState("");

  const [sessionMinutes, setSessionMinutes] = useState(60);
  const [sessionEnd, setSessionEnd] = useState<number | null>(null);
  const [sessionRemaining, setSessionRemaining] = useState<string | null>(null);

  const [autoGuardEnabled, setAutoGuardEnabled] = useState(() => {
    try { return localStorage.getItem("bacbo_auto_guard") === "true"; } catch (err) { if (import.meta.env.DEV) console.warn("[localStorage] Failed to read auto-guard:", err); return false; }
  });
  const [autoGuardLimit, setAutoGuardLimit] = useState(() => {
    try { return parseInt(localStorage.getItem("bacbo_auto_guard_limit") || "3") || 3; } catch (err) { if (import.meta.env.DEV) console.warn("[localStorage] Failed to read auto-guard-limit:", err); return 3; }
  });
  const [autoGuardTriggered, setAutoGuardTriggered] = useState(false);

  const [mgBankroll, setMgBankroll] = useState("100");
  const [mgBase, setMgBase] = useState("1");
  const [simBalance, setSimBalance] = useState("105");
  const [simBet, setSimBet] = useState("5");
  const [simDays, setSimDays] = useState("7");

  const [newEmail, setNewEmail] = useState("");
  const [newPass, setNewPass]   = useState("");
  const [chgEmail, setChgEmail]   = useState("");
  const [chgPass,  setChgPass]    = useState("");
  const [chgPass2, setChgPass2]   = useState("");
  const [removeTarget, setRemoveTarget] = useState<string | null>(null);

  const [newRoom, setNewRoom] = useState("");
  const [activityCategory, setActivityCategory] = useState("all");
  const [removeRoomTarget, setRemoveRoomTarget] = useState<string | null>(null);

  const [clock, setClock] = useState(() => new Date().toLocaleTimeString("en-US"));
  useEffect(() => {
    const id = setInterval(() => setClock(new Date().toLocaleTimeString("en-US")), 1000);
    return () => clearInterval(id);
  }, []);

  const { permission, requestPermission, alertSignal, alertOutcome, testAlert, soundTheme, changeSoundTheme } = useSignalAlert();
  const { supported: wakeLockSupported, isActive: wakeLockActive, toggle: toggleWakeLock } = useWakeLock();

  const [streamStatus, setStreamStatus] = useState<StreamStatus>("connecting");
  const streamLive = streamStatus === "connected";
  const [dataStale, setDataStale] = useState(false);
  const lastDataTimestampRef = useRef<number>(Date.now());
  const lastResolvedIdRef = useRef<number | null>(null);
  const lastPendingIdRef  = useRef<number | null>(null);
  const lastActivityIdRef = useRef<number | null>(null);
  const [newSignalFlash, setNewSignalFlash] = useState(false);
  const lastOutcomeRef = useRef<string | null>(null);

  useEffect(() => {
    const close = openStatusStream({
      onData: (data) => {
        qc.setQueryData(["status"], data);
        setStreamStatus("connected");
        setDataStale(false);
        lastDataTimestampRef.current = Date.now();
        const rid = data?.lastResolvedId ?? null;
        if (rid !== null && rid !== lastResolvedIdRef.current) {
          lastResolvedIdRef.current = rid;
          qc.invalidateQueries({ queryKey: ["bankroll"] });
          qc.invalidateQueries({ queryKey: ["history"] });
          qc.invalidateQueries({ queryKey: ["leaderboard"] });
          qc.invalidateQueries({ queryKey: ["analytics"] });
          const outcome = data?.lastOutcome;
          if (outcome && outcome !== lastOutcomeRef.current && (outcome === "win" || outcome === "loss" || outcome === "tie")) {
            lastOutcomeRef.current = outcome;
            alertOutcome(outcome);
          }
        }
        const pid = data?.lastPending?.id ?? null;
        if (pid !== null && pid !== lastPendingIdRef.current) {
          lastPendingIdRef.current = pid;
          alertSignal(data.lastPending);
          setNewSignalFlash(true);
          setTimeout(() => setNewSignalFlash(false), 1500);
          qc.invalidateQueries({ queryKey: ["history"] });
          qc.invalidateQueries({ queryKey: ["analytics"] });
        }
        const aid = data?.latestActivityId ?? null;
        if (aid !== null && aid !== lastActivityIdRef.current) {
          lastActivityIdRef.current = aid;
          qc.invalidateQueries({ queryKey: ["activity"] });
        }
      },
      onStatusChange: (status) => {
        setStreamStatus(status);
        if (status === "disconnected") {
          const elapsed = Date.now() - lastDataTimestampRef.current;
          if (elapsed > 30_000) setDataStale(true);
        }
      },
      onParseError: (raw) => {
        toast({ title: t("error"), description: "Failed to parse stream data", variant: "destructive" });
        if (import.meta.env.DEV) console.warn("[StatusSSE] Bad payload:", raw);
      },
    });
    return close;
  }, [qc, alertSignal, alertOutcome, toast, t]);

  useEffect(() => {
    if (streamLive) return;
    const id = setInterval(() => {
      const elapsed = Date.now() - lastDataTimestampRef.current;
      if (elapsed > 30_000) setDataStale(true);
    }, 5_000);
    return () => clearInterval(id);
  }, [streamLive]);

  const onDashboard = tab === "dashboard" || tab === "live";
  const isAdmin = getIsAdmin();
  const statusQ     = useQuery({ queryKey: ["status"],      queryFn: api.status,       refetchInterval: onDashboard ? 1_000 : false });
  const bankrollQ   = useQuery({ queryKey: ["bankroll"],    queryFn: api.bankroll,     refetchInterval: onDashboard ? 5_000 : false });
  const leaderQ     = useQuery({ queryKey: ["leaderboard"], queryFn: api.leaderboard,  enabled: tab === "leaderboard", refetchInterval: tab === "leaderboard" ? 60_000 : false });
  const histQ       = useQuery({ queryKey: ["history"],     queryFn: api.history,      enabled: tab === "history" || tab === "dashboard" || tab === "live", refetchInterval: tab === "dashboard" || tab === "live" ? 2_000 : tab === "history" ? 10_000 : false });
  const analyticsQ  = useQuery({ queryKey: ["analytics"],   queryFn: api.analytics,    enabled: tab === "live" || tab === "dashboard", refetchInterval: tab === "live" || tab === "dashboard" ? 2_000 : false });
  const usersQ    = useQuery({ queryKey: ["users"],       queryFn: api.users,        enabled: tab === "users" && isAdmin });
  const roomsQ    = useQuery({ queryKey: ["rooms"],       queryFn: api.rooms,        enabled: tab === "rooms" });
  const cyclesQ   = useQuery({ queryKey: ["cycles"],      queryFn: api.cycles,       enabled: tab === "cycles", refetchInterval: tab === "cycles" ? 30_000 : false });
  const cycleRoomQ = useQuery({ queryKey: ["cycleRoom", cycleRoom], queryFn: () => api.cyclesRoom(cycleRoom!), enabled: !!cycleRoom && tab === "cycles", refetchInterval: 20_000 });
  const broadcastQ    = useQuery({ queryKey: ["broadcastMsgs"],  queryFn: api.broadcastMessages,  enabled: tab === "broadcast", refetchInterval: false });
  const subscribersQ  = useQuery({ queryKey: ["broadcastSubs"],  queryFn: api.broadcastSubscribers, enabled: tab === "broadcast" && isAdmin, refetchInterval: false });
  const engineHealthQ = useQuery({ queryKey: ["engineHealth"],   queryFn: api.engineHealth, enabled: tab === "engine", refetchInterval: tab === "engine" ? 15_000 : false });
  const resultLagQ    = useQuery({ queryKey: ["resultLagPatterns"], queryFn: api.resultLagPatterns, enabled: tab === "engine", refetchInterval: tab === "engine" ? 120_000 : false });
  const eliteStackQ   = useQuery({ queryKey: ["eliteStackAudit"], queryFn: api.eliteStackAudit, enabled: tab === "engine", refetchInterval: tab === "engine" ? 120_000 : false });
  const martingaleAuditQ = useQuery({ queryKey: ["martingaleAudit"], queryFn: api.martingaleAudit, enabled: tab === "engine", refetchInterval: tab === "engine" ? 120_000 : false });
  const truthVerificationQ = useQuery({ queryKey: ["truthVerification"], queryFn: api.truthVerification, enabled: tab === "engine", refetchInterval: tab === "engine" ? 120_000 : false });
  const systemHealthAuditQ = useQuery({ queryKey: ["systemHealthAudit"], queryFn: api.systemHealthAudit, enabled: tab === "engine", refetchInterval: tab === "engine" ? 60_000 : false });
  const trendsQ       = useQuery({ queryKey: ["trends"],         queryFn: () => api.trends(9999), enabled: tab === "dashboard", refetchInterval: 60_000 });
  const heatmapQ      = useQuery({ queryKey: ["heatmap"],        queryFn: () => api.heatmap(9999), enabled: tab === "heatmap" || tab === "dashboard", refetchInterval: 60_000 });
  const dailyStatsQ   = useQuery({ queryKey: ["dailyStats"],     queryFn: api.dailyStats,          enabled: tab === "dashboard", refetchInterval: 60_000 });
  const heatmapDowQ   = useQuery({ queryKey: ["heatmapDow"],    queryFn: () => api.heatmapDow(9999), enabled: tab === "heatmap", refetchInterval: 60_000 });
  const [selectedDow, setSelectedDow] = useState<number>(() => {
    const d = new Date(); return d.getDay(); // 0=Sun…6=Sat, matches SQLite %w
  });
  const heatmapDayHourQ = useQuery({ queryKey: ["heatmapDayHour", selectedDow], queryFn: () => api.heatmapDayHour(selectedDow, 9999), enabled: tab === "heatmap", refetchInterval: 60_000 });
  const bankrollPnlQ  = useQuery({ queryKey: ["bankrollPnl"],   queryFn: api.bankrollPnl, enabled: tab === "bankroll", refetchInterval: 60_000 });
  const bankrollTrackerQ = useQuery({ queryKey: ["bankrollTracker"], queryFn: api.bankrollTracker, enabled: tab === "bankroll", refetchInterval: 30_000 });
  const confidenceTrendsQ = useQuery({ queryKey: ["confidenceTrends"], queryFn: () => api.confidenceTrends(9999), enabled: tab === "heatmap", refetchInterval: 60_000 });
  const roomHealthQ = useQuery({ queryKey: ["roomHealth"], queryFn: api.roomHealth, enabled: tab === "leaderboard", refetchInterval: 60_000 });
  const winStreakQ = useQuery({ queryKey: ["winStreak"], queryFn: api.winStreak, enabled: tab === "live" || tab === "dashboard", refetchInterval: 10_000 });
  const correlationQ = useQuery({ queryKey: ["correlations"], queryFn: api.roomCorrelations, enabled: tab === "heatmap", refetchInterval: 120_000 });
  const martingaleQ = useQuery({
    queryKey: ["martingale", mgBankroll, mgBase],
    queryFn: () => api.martingaleCalc(parseFloat(mgBankroll) || 100, parseFloat(mgBase) || 1),
    enabled: tab === "bankroll",
    refetchInterval: false,
  });
  const colorTimelineQ = useQuery({ queryKey: ["colorTimeline"], queryFn: api.colorTimeline, enabled: tab === "live" || tab === "heatmap", refetchInterval: 30_000 });
  const simulateQ = useQuery({
    queryKey: ["simulate", simBalance, simBet, simDays],
    queryFn: () => api.simulate(parseFloat(simBalance) || 105, parseFloat(simBet) || 5, parseInt(simDays) || 7),
    enabled: tab === "bankroll",
    refetchInterval: false,
  });
  const bestPairsQ = useQuery({ queryKey: ["bestPairs"], queryFn: api.bestPairs, enabled: tab === "leaderboard", refetchInterval: 120_000 });
  const g0Q = useQuery({ queryKey: ["g0Metrics"], queryFn: api.g0Metrics, enabled: tab === "g0", refetchInterval: tab === "g0" ? 120_000 : false });
  const activityQ = useQuery({
    queryKey: ["activity", activityCategory],
    queryFn: () => api.activityFeed({ category: activityCategory === "all" ? undefined : activityCategory, limit: 200 }),
    enabled: tab === "activity",
    refetchInterval: tab === "activity" ? 5_000 : false,
  });
  const histFilteredQ = useQuery({
    queryKey: ["histFiltered", histKind, histOutcome, histFrom, histTo],
    queryFn: () => api.historyFiltered({
      kind: histKind === "all" ? undefined : histKind,
      outcome: histOutcome === "all" ? undefined : histOutcome,
      from: histFrom || undefined,
      to: histTo || undefined,
      limit: 200,
    }),
    enabled: tab === "history",
    refetchInterval: 30_000,
  });

  const addBankrollMut = useMutation({
    mutationFn: () => api.addBankrollEntry(parseFloat(brAmount), brType, brNote),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bankrollTracker"] });
      setBrAmount(""); setBrNote("");
      toast({ title: "Entry added" });
    },
    onError: (err: any) => toast({ title: "Error", description: err.message, variant: "destructive" }),
  });

  const delBankrollMut = useMutation({
    mutationFn: (id: number) => api.deleteBankrollEntry(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bankrollTracker"] });
      toast({ title: "Entry deleted" });
    },
  });

  useEffect(() => {
    if (!sessionEnd) { setSessionRemaining(null); return; }
    const id = setInterval(() => {
      const diff = sessionEnd - Date.now();
      if (diff <= 0) {
        setSessionEnd(null);
        setSessionRemaining(null);
        if (navigator.vibrate) navigator.vibrate([500, 200, 500]);
        toast({ title: "Session timer ended!" });
        return;
      }
      const m = Math.floor(diff / 60000);
      const sec = Math.floor((diff % 60000) / 1000);
      setSessionRemaining(`${m}:${sec.toString().padStart(2, "0")}`);
    }, 1000);
    return () => clearInterval(id);
  }, [sessionEnd, toast]);

  const startSession = useCallback(() => {
    setSessionEnd(Date.now() + sessionMinutes * 60000);
  }, [sessionMinutes]);

  const stopSession = useCallback(() => {
    setSessionEnd(null);
    setSessionRemaining(null);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("bacbo_auto_guard", String(autoGuardEnabled));
      localStorage.setItem("bacbo_auto_guard_limit", String(autoGuardLimit));
    } catch (err) {
      if (import.meta.env.DEV) console.warn("[localStorage] Failed to save auto-guard settings:", err);
    }
  }, [autoGuardEnabled, autoGuardLimit]);

  const [broadcastMsg,    setBroadcastMsg]   = useState("");
  const [broadcastSending, setBroadcastSending] = useState(false);
  const [broadcastDelTarget, setBroadcastDelTarget] = useState<number | null>(null);

  const outcomeMut = useMutation({
    mutationFn: (o: "win" | "loss" | "tie" | "undo") => api.outcome(o),
    onSuccess: (_, outcome) => {
      qc.invalidateQueries({ queryKey: ["status"] });
      qc.invalidateQueries({ queryKey: ["bankroll"] });
      qc.invalidateQueries({ queryKey: ["history"] });
      qc.invalidateQueries({ queryKey: ["leaderboard"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
      const msgs: Record<string, string> = {
        win:  t("toastWin"),
        loss: t("toastLoss"),
        tie:  t("toastTie"),
        undo: t("toastUndo"),
      };
      toast({ title: msgs[outcome] });
    },
    onError: (err: any) => {
      toast({ title: "⚠️ Error", description: err.message, variant: "destructive" });
    },
  });

  const addUserMut = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.addUser(email, password),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setNewEmail(""); setNewPass("");
      toast({ title: t("toastUserAdded") });
    },
    onError: (err: any) => toast({ title: t("toastError"), description: err.message, variant: "destructive" }),
  });

  const chgPassMut = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.changePassword(email, password),
    onSuccess: () => {
      setChgEmail(""); setChgPass(""); setChgPass2("");
      toast({ title: t("toastPassChanged") });
    },
    onError: (err: any) => toast({ title: t("toastError"), description: err.message, variant: "destructive" }),
  });

  const removeUserMut = useMutation({
    mutationFn: (email: string) => api.removeUser(email),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setRemoveTarget(null);
      toast({ title: t("toastUserRemoved") });
    },
    onError: (err: any) => {
      setRemoveTarget(null);
      toast({ title: t("toastError"), description: err.message, variant: "destructive" });
    },
  });

  const addRoomMut = useMutation({
    mutationFn: (handle: string) => api.addRoom(handle),
    onSuccess: (_, handle) => {
      qc.invalidateQueries({ queryKey: ["rooms"] });
      setNewRoom("");
      toast({ title: `✅ ${handle} — ${t("toastRoomAdded")}` });
    },
    onError: (err: any) => toast({ title: t("toastError"), description: err.message, variant: "destructive" }),
  });

  const removeRoomMut = useMutation({
    mutationFn: (handle: string) => api.removeRoom(handle),
    onSuccess: (_, handle) => {
      qc.invalidateQueries({ queryKey: ["rooms"] });
      setRemoveRoomTarget(null);
      toast({ title: `${handle} — ${t("toastRoomRemoved")}` });
    },
    onError: (err: any) => {
      setRemoveRoomTarget(null);
      toast({ title: t("toastError"), description: err.message, variant: "destructive" });
    },
  });

  function logout() {
    localStorage.removeItem("bacbo_token");
    setLoc("/login");
  }

  const s = statusQ.data;
  const b = bankrollQ.data;
  const cooldownActive = (s?.lossStreak ?? 0) >= LOSS_COOLDOWN_THRESHOLD;
  const tiePressure = (s?.tiePressureRounds ?? 0) >= TIE_PRESSURE_THRESHOLD;
  const todayWr = s?.accuracy?.wr ?? null;
  const sessionCutoff = analyticsQ.data?.sessionCutoff as string | null | undefined;
  const sessionLabel = analyticsQ.data?.sessionLabel as string | null | undefined;
  const sessionCutoffLabel = sessionCutoff
    ? (() => {
        const d = new Date(sessionCutoff + "Z");
        const time = d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
        const dateStr = d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
        const prefix = sessionLabel ? `${sessionLabel} baseline` : "baseline";
        return `${prefix} · ${dateStr} ${time} UTC`;
      })()
    : "resets at 00:00 UTC";
  const busy = outcomeMut.isPending;

  useEffect(() => {
    if (!autoGuardEnabled) return;
    const lossStreak = s?.lossStreak ?? 0;
    if (lossStreak >= autoGuardLimit && !autoGuardTriggered) {
      setAutoGuardTriggered(true);
      if (navigator.vibrate) navigator.vibrate([500, 200, 500, 200, 500]);
      toast({ title: t("autoSessionTriggered"), variant: "destructive" });
    }
  }, [s?.lossStreak, autoGuardEnabled, autoGuardLimit, autoGuardTriggered, toast, t]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-white">
      <header className="sticky top-0 z-10 bg-gray-900/80 backdrop-blur border-b border-gray-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">🎯</span>
          <span className="font-bold text-white">BacBo Royal</span>
          {(() => {
            const hb = s?.botLastSeen;
            if (!hb) return <span className="text-xs text-gray-500 ml-1">{t("botOffline")}</span>;
            const diffMin = Math.floor((Date.now() - new Date(hb + "Z").getTime()) / 60_000);
            if (diffMin < 2) return <span className="text-xs text-green-400 ml-1">● {t("botLive")}</span>;
            if (diffMin < 60) return <span className="text-xs text-yellow-400 ml-1">● bot {diffMin}min</span>;
            return <span className="text-xs text-red-400 ml-1">● bot {Math.floor(diffMin / 60)}h</span>;
          })()}
          {streamStatus === "connected"
            ? <span className="text-xs text-blue-400 ml-1">⚡ {t("streamLive")}</span>
            : streamStatus === "connecting"
              ? <span className="text-xs text-yellow-400 ml-1 animate-pulse">● connecting...</span>
              : streamStatus === "error"
                ? <span className="text-xs text-yellow-400 ml-1">⚠ error</span>
                : <span className="text-xs text-red-400 ml-1 animate-pulse">● {t("streamOffline")}</span>}
        </div>
        <div className="flex items-center gap-2">
          {permission === "granted" && (
            <select
              value={soundTheme}
              onChange={e => changeSoundTheme(e.target.value as any)}
              title="Alert sound theme"
              className="text-xs bg-gray-800 border border-gray-700 rounded px-1 py-0.5 text-gray-300"
            >
              <option value="default">🔊 Default</option>
              <option value="chime">🔔 Chime</option>
              <option value="arcade">🎮 Arcade</option>
              <option value="subtle">🔉 Subtle</option>
              <option value="off">🔇 Off</option>
            </select>
          )}
          {permission === "granted" && (
            <button onClick={testAlert} title="Test alert sound & vibration"
              className="text-xs text-gray-500 hover:text-yellow-400 transition-colors select-none">🔊</button>
          )}
          <button
            onClick={permission === "granted" ? undefined : requestPermission}
            title={
              permission === "granted"  ? "Alerts ON — vibration + sound + notifications enabled"
              : permission === "denied"  ? "Notifications blocked — enable in browser settings"
              : permission === "unsupported" ? "Notifications not supported on this browser"
              : "Tap to enable alerts for new signals"
            }
            className={`text-lg transition-all select-none ${
              permission === "granted" ? "opacity-100 cursor-default"
                : permission === "denied" ? "opacity-30 cursor-not-allowed"
                : "opacity-60 hover:opacity-100 cursor-pointer animate-pulse"
            }`}
          >
            {permission === "granted" ? "🔔" : "🔕"}
          </button>
          {wakeLockSupported && (
            <button onClick={toggleWakeLock}
              title={wakeLockActive ? "Screen wake lock ON — tap to disable" : "Keep screen awake — tap to enable"}
              className={`text-sm transition-all select-none ${wakeLockActive ? "opacity-100 text-yellow-400" : "opacity-50 hover:opacity-100 text-gray-400"}`}>
              {wakeLockActive ? "☀️" : "🌙"}
            </button>
          )}
          <button onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="text-sm text-gray-400 hover:text-white transition-colors select-none">
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
          <button onClick={toggleLang}
            className="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg px-2 py-1 transition-colors font-mono">
            {t("langToggle")}
          </button>
          <button onClick={logout} className="text-xs text-gray-400 hover:text-gray-200 transition-colors">
            {t("logout")}
          </button>
        </div>
      </header>

      <div className="flex border-b border-gray-800 bg-gray-900/60 sticky top-[57px] z-10 overflow-x-auto">
        {(["live", "dashboard", "feed", "battle", "activity", "leaderboard", "history", "heatmap", "bankroll", "cycles", "rooms", "g0", "floors", "guide", "users", "broadcast", "engine"] as const).map(tabKey => (
          <button
            key={tabKey}
            onClick={() => { setTab(tabKey); setRemoveTarget(null); setRemoveRoomTarget(null); if (tabKey !== "cycles") setCycleRoom(null); }}
            className={`flex-shrink-0 flex-1 py-2.5 text-xs font-medium transition-colors min-w-[55px]
              ${tab === tabKey
                ? tabKey === "live"
                  ? "text-red-400 border-b-2 border-red-400"
                  : "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-gray-200"}`}
          >
            {tabKey === "live"          ? t("tabLive")
              : tabKey === "dashboard"  ? t("tabStatus")
              : tabKey === "feed"        ? "📡 Feed"
              : tabKey === "battle"      ? "⚔️ Floors"
              : tabKey === "activity"   ? "📋"
              : tabKey === "leaderboard" ? t("tabRanking")
              : tabKey === "history"     ? t("tabHistory")
              : tabKey === "heatmap"     ? "🔥"
              : tabKey === "bankroll"    ? "💰"
              : tabKey === "cycles"      ? "Cycles"
              : tabKey === "rooms"       ? t("tabRooms")
              : tabKey === "g0"          ? "G0"
              : tabKey === "floors"      ? "🏛️ Floors"
              : tabKey === "guide"       ? "📖 Guia"
              : tabKey === "broadcast"   ? "📢"
              : tabKey === "engine"      ? "🧠"
              : t("tabAccess")}
          </button>
        ))}
      </div>

      {(!streamLive || dataStale) && (
        <div className={`${streamStatus === "error" ? "bg-yellow-900/40 border-b border-yellow-700/50" : "bg-red-900/40 border-b border-red-700/50"} px-4 py-2 flex items-center justify-center gap-2`}>
          <span className={`w-2 h-2 rounded-full ${streamStatus === "error" ? "bg-yellow-500" : "bg-red-500"} animate-pulse`} />
          <span className={`text-xs ${streamStatus === "error" ? "text-yellow-300" : "text-red-300"} font-medium`}>
            {streamStatus === "error"
              ? "Stream data error — some updates may be invalid"
              : dataStale
                ? "Data may be stale — stream disconnected for 30s+"
                : streamStatus === "connecting"
                  ? "Connecting to live stream..."
                  : "Connection lost — reconnecting..."}
          </span>
        </div>
      )}

      <main className="max-w-lg mx-auto px-4 py-4 space-y-4 pb-8">
        {s?.lastResolved && (
          <div className="bg-gray-800/70 border border-gray-700 rounded-2xl p-3 shadow-lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Last Result</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`px-3 py-1 rounded-xl border text-sm font-black ${resultColorClasses(s.lastResolved.actualColor)}`}>
                    {resultLabel(s.lastResolved.actualColor)}
                  </span>
                  <span className={`px-2 py-1 rounded-lg text-xs font-bold ${
                    s.lastResolved.outcome === "loss" ? "bg-red-900/60 text-red-300" :
                    s.lastResolved.outcome === "tie" ? "bg-yellow-900/60 text-yellow-300" :
                    "bg-emerald-900/60 text-emerald-300"
                  }`}>
                    {s.lastResolved.outcome === "win" ? "✅" : s.lastResolved.outcome === "loss" ? "❌" : "🟡"} {outcomeBadge(s.lastResolved)}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs font-semibold text-cyan-300">{formatResultSeconds(s.lastResolved)}</p>
                <p className="text-[10px] text-gray-500">
                  fired {parseUtc(s.lastResolved.firedAt)?.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) ?? "—"}
                </p>
              </div>
            </div>
            {(s.recentResults ?? []).length > 0 && (
              <div className="flex gap-1.5 overflow-x-auto mt-3 pb-1">
                {(s.recentResults ?? []).slice(0, 10).map((r: any) => (
                  <div key={r.id} className={`shrink-0 min-w-[42px] rounded-xl border px-2 py-1 text-center ${resultColorClasses(r.actualColor)}`}>
                    <p className="text-[10px] font-black leading-tight">{resultLabel(r.actualColor)[0]}</p>
                    <p className="text-[9px] leading-tight opacity-90">{outcomeBadge(r)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "live" && (
          <LiveTab
            s={s} b={b}
            analyticsData={analyticsQ.data}
            histData={histQ.data}
            winStreakData={winStreakQ.data}
            colorTimelineData={colorTimelineQ.data}
            clock={clock} streamLive={streamLive}
            sessionMinutes={sessionMinutes} setSessionMinutes={setSessionMinutes}
            sessionRemaining={sessionRemaining}
            startSession={startSession} stopSession={stopSession}
            autoGuardEnabled={autoGuardEnabled} setAutoGuardEnabled={setAutoGuardEnabled}
            autoGuardLimit={autoGuardLimit} setAutoGuardLimit={setAutoGuardLimit}
            autoGuardTriggered={autoGuardTriggered} setAutoGuardTriggered={setAutoGuardTriggered}
            outcomeMut={outcomeMut} busy={busy}
            histFetching={histQ.isFetching} analyticsFetching={analyticsQ.isFetching}
            newSignalFlash={newSignalFlash}
          />
        )}

        {tab === "dashboard" && (
          <DashboardTab
            s={s} b={b}
            analyticsData={analyticsQ.data}
            histData={histQ.data}
            trendsData={trendsQ.data}
            winStreakData={winStreakQ.data}
            heatmapData={heatmapQ.data}
            dailyStatsData={dailyStatsQ.data}
            streamLive={streamLive}
            histFetching={histQ.isFetching}
            cooldownActive={cooldownActive}
            tiePressure={tiePressure}
            todayWr={todayWr}
            sessionCutoff={sessionCutoff}
            sessionCutoffLabel={sessionCutoffLabel}
            busy={busy}
            outcomeMut={outcomeMut}
            qc={qc} api={api}
            permission={permission}
            requestPermission={requestPermission}
          />
        )}

        {tab === "feed" && (
          <SignalFeedTab />
        )}

        {tab === "battle" && (
          <FloorBattleTab />
        )}

        {tab === "leaderboard" && (
          <LeaderboardTab leaderQ={leaderQ} roomHealthQ={roomHealthQ} bestPairsQ={bestPairsQ} />
        )}

        {tab === "history" && (
          <HistoryTab
            histQ={histQ} histFilteredQ={histFilteredQ}
            histKind={histKind} setHistKind={setHistKind}
            histOutcome={histOutcome} setHistOutcome={setHistOutcome}
            histFrom={histFrom} setHistFrom={setHistFrom}
            histTo={histTo} setHistTo={setHistTo}
            qc={qc} api={api}
          />
        )}

        {tab === "rooms" && (
          <RoomsTab
            roomsQ={roomsQ} isAdmin={isAdmin}
            newRoom={newRoom} setNewRoom={setNewRoom}
            removeRoomTarget={removeRoomTarget} setRemoveRoomTarget={setRemoveRoomTarget}
            addRoomMut={addRoomMut} removeRoomMut={removeRoomMut}
            qc={qc}
          />
        )}

        {tab === "cycles" && (
          <CyclesTab
            cyclesQ={cyclesQ} cycleRoomQ={cycleRoomQ} statusQ={statusQ}
            cycleRoom={cycleRoom} setCycleRoom={setCycleRoom}
            qc={qc}
          />
        )}

        {tab === "users" && (
          <UsersTab
            usersQ={usersQ} isAdmin={isAdmin}
            newEmail={newEmail} setNewEmail={setNewEmail}
            newPass={newPass} setNewPass={setNewPass}
            chgEmail={chgEmail} setChgEmail={setChgEmail}
            chgPass={chgPass} setChgPass={setChgPass}
            chgPass2={chgPass2} setChgPass2={setChgPass2}
            removeTarget={removeTarget} setRemoveTarget={setRemoveTarget}
            addUserMut={addUserMut} chgPassMut={chgPassMut} removeUserMut={removeUserMut}
          />
        )}

        {tab === "broadcast" && (
          <BroadcastTab
            broadcastQ={broadcastQ} subscribersQ={subscribersQ} isAdmin={isAdmin}
            broadcastMsg={broadcastMsg} setBroadcastMsg={setBroadcastMsg}
            broadcastSending={broadcastSending} setBroadcastSending={setBroadcastSending}
            broadcastDelTarget={broadcastDelTarget} setBroadcastDelTarget={setBroadcastDelTarget}
            toast={toast} qc={qc} api={api}
          />
        )}

        {tab === "activity" && (
          <ActivityTab
            activityQ={activityQ}
            filterCategory={activityCategory}
            setFilterCategory={setActivityCategory}
          />
        )}

        {tab === "g0" && (
          <G0Tab g0Q={g0Q} />
        )}

        {tab === "guide" && (
          <GuideTab />
        )}

        {tab === "floors" && (
          <FloorsTab />
        )}

        {tab === "engine" && (
          <EngineTab
            engineHealthQ={engineHealthQ}
            resultLagQ={resultLagQ}
            eliteStackQ={eliteStackQ}
            martingaleAuditQ={martingaleAuditQ}
            truthVerificationQ={truthVerificationQ}
            systemHealthAuditQ={systemHealthAuditQ}
          />
        )}

        {tab === "heatmap" && (
          <HeatmapTab
            heatmapQ={heatmapQ} heatmapDowQ={heatmapDowQ}
            correlationQ={correlationQ} confidenceTrendsQ={confidenceTrendsQ}
            heatmapDayHourQ={heatmapDayHourQ}
            selectedDow={selectedDow} setSelectedDow={setSelectedDow}
          />
        )}

        {tab === "bankroll" && (
          <BankrollTab
            bankrollTrackerQ={bankrollTrackerQ} bankrollPnlQ={bankrollPnlQ} martingaleQ={martingaleQ}
            simulateQ={simulateQ}
            brAmount={brAmount} setBrAmount={setBrAmount}
            brType={brType} setBrType={setBrType}
            brNote={brNote} setBrNote={setBrNote}
            mgBankroll={mgBankroll} setMgBankroll={setMgBankroll}
            mgBase={mgBase} setMgBase={setMgBase}
            simBalance={simBalance} setSimBalance={setSimBalance}
            simBet={simBet} setSimBet={setSimBet}
            simDays={simDays} setSimDays={setSimDays}
            addBankrollMut={addBankrollMut} delBankrollMut={delBankrollMut}
            api={api}
          />
        )}

        <p className="text-center text-gray-700 text-xs">
          {(tab === "live" || tab === "dashboard") ? "Live updates · " : ""}{clock}
        </p>
      </main>
    </div>
  );
}
