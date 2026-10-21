interface EngineTabProps {
  engineHealthQ: any;
  resultLagQ?: any;
  eliteStackQ?: any;
  martingaleAuditQ?: any;
  truthVerificationQ?: any;
  systemHealthAuditQ?: any;
}

function pctColor(v: number | null | undefined, good = 70): string {
  if (v == null) return "text-gray-500";
  if (v >= good + 15) return "text-emerald-400 font-bold";
  if (v >= good) return "text-green-400";
  if (v >= good - 10) return "text-yellow-400";
  return "text-red-400";
}

export default function EngineTab({
  engineHealthQ,
  resultLagQ,
  eliteStackQ,
  martingaleAuditQ,
  truthVerificationQ,
  systemHealthAuditQ,
}: EngineTabProps) {
  const lagData = resultLagQ?.data;
  const lag5 = lagData?.lag5;
  const bestLag = lagData?.best_lag;
  const elite = eliteStackQ?.data;
  const martingale = martingaleAuditQ?.data;
  const truth = truthVerificationQ?.data;
  const systemHealth = systemHealthAuditQ?.data;

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">🧠 Engine Health</h2>

      <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">🩺 Whole App Doctor</p>
          {systemHealth?.generated_at && <span className="text-[10px] text-gray-600">{new Date(systemHealth.generated_at).toLocaleString()}</span>}
        </div>
        {systemHealthAuditQ?.isLoading ? (
          <p className="text-gray-500 text-sm">Loading system health audit…</p>
        ) : systemHealth?.missing ? (
          <p className="text-yellow-400 text-xs">Report missing. Run <code>python3 -u bot/system_health_audit.py --db bot/bacbo.db</code>.</p>
        ) : systemHealth ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center">
              <div className="bg-gray-900/60 rounded-xl p-2">
                <p className={`text-lg font-black ${
                  systemHealth.summary?.verdict === "OK" ? "text-emerald-400" :
                  systemHealth.summary?.verdict === "WATCH" ? "text-yellow-400" : "text-red-400"
                }`}>{systemHealth.summary?.verdict ?? "—"}</p>
                <p className="text-xs text-gray-500">verdict</p>
              </div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className="text-lg font-bold text-emerald-400">{systemHealth.summary?.counts?.OK ?? 0}</p><p className="text-xs text-gray-500">OK</p></div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className="text-lg font-bold text-yellow-400">{systemHealth.summary?.counts?.WARN ?? 0}</p><p className="text-xs text-gray-500">warn</p></div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className="text-lg font-bold text-red-400">{systemHealth.summary?.counts?.FAIL ?? 0}</p><p className="text-xs text-gray-500">fail</p></div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className="text-lg font-bold text-cyan-300">{systemHealth.metrics?.signals_recent_24h ?? 0}</p><p className="text-xs text-gray-500">24h signals</p></div>
            </div>
            {(systemHealth.priority_fixes ?? []).length > 0 ? (
              <div className="space-y-1.5 max-h-52 overflow-y-auto">
                {(systemHealth.priority_fixes ?? []).slice(0, 12).map((c: any, i: number) => (
                  <div key={`${c.area}-${c.name}-${i}`} className="bg-gray-900/50 rounded-lg px-3 py-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span className={`font-black ${c.status === "FAIL" ? "text-red-400" : "text-yellow-400"}`}>{c.status}</span>
                      <span className="text-gray-400">{c.area}</span>
                      <span className="text-gray-200 font-semibold">{c.name}</span>
                    </div>
                    <p className="text-gray-500 mt-0.5">{c.detail}</p>
                    {c.fix && <p className="text-cyan-300 mt-0.5">Fix: {c.fix}</p>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-emerald-400 text-xs">No priority fixes detected.</p>
            )}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No system health report yet.</p>
        )}
      </div>

      <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">✅ Truth Verification</p>
          {truth?.generated_at && <span className="text-[10px] text-gray-600">{new Date(truth.generated_at).toLocaleString()}</span>}
        </div>
        {truthVerificationQ?.isLoading ? (
          <p className="text-gray-500 text-sm">Loading truth status…</p>
        ) : truth?.missing ? (
          <p className="text-yellow-400 text-xs">Report missing. Run <code>cd bot && python elite_stack_audit.py</code>.</p>
        ) : truth ? (
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="bg-gray-900/60 rounded-xl p-3">
              <p className="text-xs text-gray-500 uppercase">Current truth level</p>
              <p className={`text-sm font-black ${truth.verdict === "DIRECT_CASINO_VERIFIED" ? "text-emerald-400" : "text-yellow-400"}`}>
                {truth.verdict === "DIRECT_CASINO_VERIFIED" ? "Direct casino" : "DB inferred only"}
              </p>
            </div>
            <div className="bg-gray-900/60 rounded-xl p-3">
              <p className="text-xs text-gray-500 uppercase">Direct rows</p>
              <p className="text-xl font-black text-cyan-300">{truth.truth_levels?.direct_casino_rows_recent ?? 0}</p>
              <p className="text-[10px] text-gray-600">recent Twin225 rows</p>
            </div>
            <div className="bg-gray-900/60 rounded-xl p-3">
              <p className="text-xs text-gray-500 uppercase">Inferred rows</p>
              <p className="text-xl font-black text-blue-300">{truth.truth_levels?.inferred_from_bot_db_recent ?? 0}</p>
              <p className="text-[10px] text-gray-600">from bot/Telegram DB</p>
            </div>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No truth report yet.</p>
        )}
      </div>

      <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">♻️ Martingale / Gale Audit</p>
          {martingale?.generated_at && <span className="text-[10px] text-gray-600">{new Date(martingale.generated_at).toLocaleString()}</span>}
        </div>
        {martingaleAuditQ?.isLoading ? (
          <p className="text-gray-500 text-sm">Loading martingale audit…</p>
        ) : martingale?.missing ? (
          <p className="text-yellow-400 text-xs">Report missing. Run <code>cd bot && python elite_stack_audit.py</code>.</p>
        ) : martingale?.overall ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
              <div className="bg-gray-900/60 rounded-xl p-2"><p className={`text-lg font-bold ${pctColor(martingale.overall.g0_wr, 70)}`}>{martingale.overall.g0_wr}%</p><p className="text-xs text-gray-500">G0 WR</p></div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className={`text-lg font-bold ${pctColor(martingale.overall.final_wr, 75)}`}>{martingale.overall.final_wr}%</p><p className="text-xs text-gray-500">Final WR</p></div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className={`text-lg font-bold ${pctColor(martingale.overall.recovery_wr, 40)}`}>{martingale.overall.recovery_wr}%</p><p className="text-xs text-gray-500">Recovery WR</p></div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className="text-lg font-bold text-white">{martingale.overall.total}</p><p className="text-xs text-gray-500">signals</p></div>
            </div>
            <p className={`text-xs font-semibold ${martingale.overall.verdict === "ALLOW_MARTINGALE" ? "text-green-400" : martingale.overall.verdict === "SHADOW_MARTINGALE" ? "text-yellow-400" : "text-red-400"}`}>
              Verdict: {martingale.overall.verdict}
            </p>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No martingale report yet.</p>
        )}
      </div>

      <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">🔁 Lag Pattern Miner</p>
          {lagData?.generated_at && <span className="text-[10px] text-gray-600">{new Date(lagData.generated_at).toLocaleString()}</span>}
        </div>
        {resultLagQ?.isLoading ? (
          <p className="text-gray-500 text-sm">Loading lag patterns…</p>
        ) : lagData?.missing ? (
          <p className="text-yellow-400 text-xs">Report missing. Run <code>cd bot && python elite_stack_audit.py</code>.</p>
        ) : lag5 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="bg-gray-900/60 rounded-xl p-3">
              <p className="text-xs text-gray-500 uppercase">Your lag-5 hypothesis</p>
              <p className={`text-2xl font-black ${pctColor(lag5.repeat_pct, 55)}`}>{lag5.repeat_pct}%</p>
              <p className="text-xs text-gray-400">{lag5.repeat_count}/{lag5.samples} repeated same color after 5 rounds</p>
              <p className={`text-sm mt-2 ${pctColor(lag5.opposite_before_repeat_pct, 50)}`}>
                {lag5.opposite_before_repeat_pct}% had opposite color right before repeat
              </p>
            </div>
            <div className="bg-gray-900/60 rounded-xl p-3">
              <p className="text-xs text-gray-500 uppercase">Best lag found</p>
              <p className="text-2xl font-black text-blue-300">L{bestLag?.lag ?? "—"}</p>
              <p className={`text-xs ${pctColor(bestLag?.repeat_pct, 55)}`}>repeat {bestLag?.repeat_pct ?? "—"}%</p>
              <p className={`text-xs ${pctColor(bestLag?.opposite_before_repeat_pct, 50)}`}>opposite-before {bestLag?.opposite_before_repeat_pct ?? "—"}%</p>
              <p className="text-[10px] text-gray-600 mt-1">stream n={lagData?.stream_n ?? 0}</p>
            </div>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No lag pattern data yet.</p>
        )}
      </div>

      <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">🏛️ Elite Stack Audit</p>
          {elite?.generated_at && <span className="text-[10px] text-gray-600">{new Date(elite.generated_at).toLocaleString()}</span>}
        </div>
        {eliteStackQ?.isLoading ? (
          <p className="text-gray-500 text-sm">Loading elite stack…</p>
        ) : elite?.missing ? (
          <p className="text-yellow-400 text-xs">Report missing. Run <code>cd bot && python elite_stack_audit.py</code>.</p>
        ) : elite ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
              <div className="bg-gray-900/60 rounded-xl p-2"><p className="text-lg font-bold text-white">{elite.room_summary?.total_rooms ?? 0}</p><p className="text-xs text-gray-500">rooms</p></div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className="text-lg font-bold text-red-300">{elite.cleanup_actions?.length ?? 0}</p><p className="text-xs text-gray-500">cleanup</p></div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className="text-lg font-bold text-green-300">{elite.strongest_rooms?.length ?? 0}</p><p className="text-xs text-gray-500">strong rooms</p></div>
              <div className="bg-gray-900/60 rounded-xl p-2"><p className="text-lg font-bold text-cyan-300">{elite.omni_summary?.verdict_counts?.FIRE ?? 0}</p><p className="text-xs text-gray-500">omni fire</p></div>
            </div>
            {(elite.strongest_rooms ?? []).length > 0 && (
              <div>
                <p className="text-xs text-gray-500 uppercase mb-1">Top rooms now</p>
                <div className="flex flex-wrap gap-1.5">
                  {(elite.strongest_rooms ?? []).slice(0, 10).map((r: any) => (
                    <span key={r.handle} className="text-xs bg-green-900/40 text-green-300 rounded-full px-2 py-1">
                      {r.handle} · {r.fired_wr7}% ({r.fired_n7})
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No elite-stack report yet.</p>
        )}
      </div>

      {engineHealthQ.isLoading && <p className="text-gray-500 text-sm text-center py-8">Loading…</p>}
      {engineHealthQ.isError && <p className="text-red-400 text-sm text-center py-8">Failed to load engine health data.</p>}

      {engineHealthQ.data && (() => {
        const h = engineHealthQ.data;
        return (
          <div className="space-y-3">
            <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Bot Startup</p>
              <p className="text-sm text-gray-200">{h.startup ? new Date(h.startup + (h.startup?.includes("Z") ? "" : "Z")).toLocaleString() : "—"}</p>
            </div>

            <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Outcome History</p>
              <div className="grid grid-cols-4 gap-2 text-center mb-3">
                <div><p className="text-lg font-bold text-white">{h.outcomeStats?.total ?? 0}</p><p className="text-xs text-gray-500">Total</p></div>
                <div><p className="text-lg font-bold text-emerald-400">{h.outcomeStats?.wins ?? 0}</p><p className="text-xs text-gray-500">Wins</p></div>
                <div><p className="text-lg font-bold text-red-400">{h.outcomeStats?.losses ?? 0}</p><p className="text-xs text-gray-500">Losses</p></div>
                <div><p className="text-lg font-bold text-yellow-400">{h.outcomeStats?.ties ?? 0}</p><p className="text-xs text-gray-500">Ties</p></div>
              </div>
              {h.outcomeStats?.winRate != null && (
                <div className="mb-2">
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>Win Rate</span><span className="font-semibold text-white">{h.outcomeStats.winRate}%</span>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all ${h.outcomeStats.winRate >= 70 ? "bg-emerald-500" : h.outcomeStats.winRate >= 55 ? "bg-yellow-500" : "bg-red-500"}`}
                      style={{ width: `${h.outcomeStats.winRate}%` }} />
                  </div>
                </div>
              )}
              <div className="flex flex-wrap gap-1 mt-2">
                {(h.outcomeStats?.recent ?? []).map((r: any, i: number) => (
                  <span key={i} className={`text-xs px-1.5 py-0.5 rounded font-mono
                    ${r.outcome === "win" ? "bg-emerald-900/60 text-emerald-300" :
                      r.outcome === "loss" ? "bg-red-900/60 text-red-300" :
                      "bg-yellow-900/60 text-yellow-300"}`}>
                    {r.outcome[0].toUpperCase()}{r.gale > 0 ? `G${r.gale}` : ""}
                  </span>
                ))}
              </div>
            </div>

            <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Markov Chain</p>
              <div className="flex items-center gap-3">
                <span className={`text-lg font-bold ${h.markov?.sufficient ? "text-emerald-400" : "text-yellow-400"}`}>
                  {h.markov?.samples ?? 0}
                </span>
                <span className="text-xs text-gray-400">samples</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${h.markov?.sufficient ? "bg-emerald-900/60 text-emerald-300" : "bg-yellow-900/60 text-yellow-300"}`}>
                  {h.markov?.sufficient ? "Active" : "Warming up (need 30)"}
                </span>
              </div>
            </div>

            <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Platt Calibrator</p>
              {h.platt?.trained ? (
                <div className="space-y-1">
                  <div className="flex gap-4 text-xs text-gray-300">
                    <span>a = <span className="font-mono text-blue-300">{h.platt.coefA?.toFixed(4)}</span></span>
                    <span>b = <span className="font-mono text-blue-300">{h.platt.coefB?.toFixed(4)}</span></span>
                    <span>n = <span className="font-mono text-blue-300">{h.platt.nSamples}</span></span>
                  </div>
                  <p className="text-xs text-gray-500">Updated: {h.platt.updatedAt ? new Date(h.platt.updatedAt + (h.platt.updatedAt?.includes("Z") ? "" : "Z")).toLocaleString() : "—"}</p>
                </div>
              ) : (
                <p className="text-xs text-yellow-400">Not yet trained — needs ≥20 score/outcome pairs</p>
              )}
            </div>

            <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Kelly Threshold</p>
              {h.kelly ? (
                <div className="space-y-1">
                  <p className="text-lg font-bold text-white">{h.kelly.threshold}</p>
                  <p className="text-xs text-gray-500">Updated: {h.kelly.updatedAt ? new Date(h.kelly.updatedAt + (h.kelly.updatedAt?.includes("Z") ? "" : "Z")).toLocaleString() : "—"}</p>
                </div>
              ) : (
                <p className="text-xs text-gray-500">Using default — auto-calibrates after 50 outcomes</p>
              )}
            </div>

            <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-4">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Recent Engine Events</p>
              {(h.engineEvents ?? []).length === 0 ? (
                <p className="text-xs text-gray-600">No events yet.</p>
              ) : (
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {(h.engineEvents as any[]).map((ev: any, i: number) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span className="font-mono text-gray-500 shrink-0">
                        {ev.created_at ? new Date(ev.created_at + (ev.created_at?.includes("Z") ? "" : "Z")).toLocaleTimeString() : "—"}
                      </span>
                      <span className={`font-semibold shrink-0 ${
                        ev.event_type?.includes("FAIL") || ev.event_type?.includes("ERROR") ? "text-red-400" :
                        ev.event_type?.includes("SUCCESS") || ev.event_type?.includes("DONE") ? "text-emerald-400" :
                        "text-blue-300"}`}>{ev.event_type}</span>
                      <span className="text-gray-400 truncate">{ev.detail}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
