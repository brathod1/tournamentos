import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { SectionTitle, Empty, Overline, groundLabel } from "../bits";
import { LayoutGrid, AlertTriangle, CheckCircle2, Coffee } from "lucide-react";
import { toast } from "sonner";

const START = 6 * 60, END = 22 * 60, STEP = 30, ROW_H = 56;
const SLOTS = [];
for (let t = START; t < END; t += STEP) SLOTS.push(t);
const fmt = (m) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const fmt12 = (m) => { let h = Math.floor(m / 60); const mm = String(m % 60).padStart(2, "0"); const ap = h >= 12 ? "pm" : "am"; h = h % 12 || 12; return `${h}:${mm}${ap}`; };
const parse = (s) => { const [a, b] = s.split(":"); return +a * 60 + +b; };
const PALETTE = ["#a3e635", "#38bdf8", "#f472b6", "#fbbf24", "#c084fc", "#34d399", "#fb7185", "#22d3ee"];

export default function BoardTab({ tid, categories }) {
  const [grounds, setGrounds] = useState([]);
  const [matches, setMatches] = useState([]);
  const [names, setNames] = useState({});
  const [durs, setDurs] = useState({});
  const [date, setDate] = useState("");
  const [dates, setDates] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [drag, setDrag] = useState(null);

  const colorFor = useCallback((cid) => PALETTE[Math.max(0, categories.findIndex((c) => c.id === cid)) % PALETTE.length], [categories]);
  const catName = useCallback((cid) => categories.find((c) => c.id === cid)?.name || "—", [categories]);

  const breakWindows = (() => {
    const seen = new Set(); const out = [];
    categories.forEach((c) => {
      const bs = c.constraints?.break_start, be = c.constraints?.break_end;
      if (bs && be) { const k = `${bs}-${be}`; if (!seen.has(k)) { seen.add(k); out.push({ s: parse(bs), e: parse(be), label: `${bs}–${be}` }); } }
    });
    return out;
  })();
  const isBreak = (t) => breakWindows.some((w) => t < w.e && w.s < t + STEP);

  const load = useCallback(async () => {
    const g = await api.listGrounds(tid);
    setGrounds(g);
    const sched = await api.schedule(tid);
    const nm = {}; g.forEach((x) => (nm[x.id] = groundLabel(x.name)));
    const dmap = {};
    for (const c of categories) {
      const ts = await api.listTeams(c.id); ts.forEach((t) => (nm[t.id] = t.short_name || t.name));
      dmap[c.id] = (c.constraints && c.constraints.match_duration_minutes) || 90;
    }
    setNames(nm); setDurs(dmap); setMatches(sched);
    const ds = [...new Set(sched.map((m) => m.date))].filter(Boolean).sort();
    setDates(ds);
    setDate((d) => (d && ds.includes(d) ? d : ds[0] || ""));
    const cf = await api.tournamentConflicts(tid).catch(() => ({ conflicts: [] }));
    setConflicts(cf.conflicts || []);
  }, [tid, categories]);
  useEffect(() => { load(); }, [load]);

  const dayMatches = matches.filter((m) => m.date === date && m.time && m.ground_id);
  const dur = (m) => durs[m.category_id] || 90;

  const bad = (() => {
    const set = new Set();
    for (let i = 0; i < dayMatches.length; i++)
      for (let j = i + 1; j < dayMatches.length; j++) {
        const a = dayMatches[i], b = dayMatches[j];
        const as = parse(a.time), ae = as + dur(a), bs = parse(b.time), be = bs + dur(b);
        if (!(as < be && bs < ae)) continue;
        if (a.ground_id === b.ground_id) { set.add(a.id); set.add(b.id); }
        const shared = [a.home_id, a.away_id].some((x) => x && (x === b.home_id || x === b.away_id));
        if (shared) { set.add(a.id); set.add(b.id); }
      }
    return set;
  })();

  const onDrop = async (gid, t) => {
    if (!drag) return;
    const id = drag; setDrag(null);
    await api.updateMatch(id, { ground_id: gid, time: fmt(t), date });
    await load();
    toast.success("Match moved");
  };
  // Calendar-style lane layout: exact positions, side-by-side lanes only when matches truly overlap.
  const laneLayout = (gid) => {
    const evs = dayMatches.filter((m) => m.ground_id === gid)
      .map((m) => ({ m, s: parse(m.time), e: parse(m.time) + dur(m) }))
      .sort((a, b) => a.s - b.s || a.e - b.e);
    const laneEnds = [];
    evs.forEach((ev) => {
      let i = laneEnds.findIndex((end) => end <= ev.s);
      if (i === -1) { i = laneEnds.length; laneEnds.push(ev.e); } else { laneEnds[i] = ev.e; }
      ev.lane = i;
    });
    evs.forEach((ev) => {
      let cols = 1;
      evs.forEach((o) => { if (o.s < ev.e && ev.s < o.e) cols = Math.max(cols, o.lane + 1); });
      ev.cols = cols;
    });
    return evs;
  };

  if (categories.length === 0) return <Empty icon={LayoutGrid} title="No categories" hint="Create categories and schedule matches first." />;

  const errors = conflicts.filter((x) => x.severity === "error");
  const warnings = conflicts.filter((x) => x.severity === "warning");
  const usedCats = [...new Set(dayMatches.map((m) => m.category_id))];

  return (
    <div>
      <SectionTitle sub="Drag matches · instant conflict check" title="Schedule Board" right={
        <div className="flex gap-2 flex-wrap justify-end">
          {dates.map((d) => (
            <button key={d} data-testid={`board-date-${d}`} onClick={() => setDate(d)}
              className={`px-3 py-2 text-xs uppercase tracking-wider border rounded-none transition-colors ${date === d ? "border-lime-400 text-lime-400 bg-lime-400/10" : "border-zinc-800 text-zinc-400 hover:border-zinc-600"}`}>
              {new Date(d).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}
            </button>
          ))}
        </div>} />

      {/* LEGEND */}
      <div className="flex items-center gap-x-6 gap-y-2 flex-wrap mb-5 border border-zinc-800 bg-zinc-900/50 px-4 py-3">
        <Overline>Legend</Overline>
        {categories.map((c) => (
          <span key={c.id} className="flex items-center gap-2 text-xs text-zinc-300" data-testid={`legend-cat-${c.id}`}>
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: colorFor(c.id) }} />{c.name}
          </span>
        ))}
        <span className="flex items-center gap-2 text-xs text-red-300"><span className="w-3 h-3 border-2 border-red-500 bg-red-500/20" />Conflict</span>
        <span className="flex items-center gap-2 text-xs text-amber-300"><span className="w-3 h-3 bg-[repeating-linear-gradient(45deg,#f59e0b33,#f59e0b33_3px,transparent_3px,transparent_6px)] border border-amber-500/40" />Break window</span>
        <span className="flex items-center gap-2 text-xs text-zinc-500"><LayoutGrid className="w-3.5 h-3.5" />Drag a match to any slot</span>
      </div>

      {dates.length === 0 ? (
        <Empty icon={LayoutGrid} title="Nothing scheduled yet" hint="Run the scheduler on the Schedule tab, then drag matches here to fine-tune slots." />
      ) : grounds.length === 0 ? (
        <Empty icon={LayoutGrid} title="No grounds" hint="Add grounds first." />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          <div className="xl:col-span-3 overflow-x-auto border border-zinc-800 bg-zinc-950">
            <div className="flex min-w-max">
              {/* time gutter */}
              <div className="w-20 shrink-0 sticky left-0 z-20 bg-zinc-950">
                <div className="h-11 border-b border-r border-zinc-800 bg-zinc-900" />
                {SLOTS.map((t) => (
                  <div key={t} className={`h-14 border-b border-r border-zinc-800/60 px-2 pt-1 text-[10px] flex items-start justify-between ${isBreak(t) ? "text-amber-400/80" : "text-zinc-500"}`}>
                    <span>{fmt12(t)}</span>{isBreak(t) && <Coffee className="w-3 h-3 opacity-70" />}
                  </div>
                ))}
              </div>
              {/* ground columns */}
              {grounds.map((g) => (
                <div key={g.id} className="flex-1 min-w-[200px] border-r border-zinc-800/60 last:border-r-0">
                  <div className="h-11 border-b border-zinc-800 bg-zinc-900 px-3 flex items-center font-display uppercase text-sm truncate sticky top-0 z-20">{groundLabel(g.name)}</div>
                  <div className="relative">
                    {/* background grid + drop targets */}
                    {SLOTS.map((t) => (
                      <div key={t} data-testid={`board-cell-${g.id}-${t}`} onDragOver={(e) => e.preventDefault()} onDrop={() => onDrop(g.id, t)}
                        className={`h-14 border-b border-zinc-800/50 transition-colors ${isBreak(t) ? "bg-[repeating-linear-gradient(45deg,rgba(245,158,11,0.10),rgba(245,158,11,0.10)_4px,transparent_4px,transparent_8px)]" : "hover:bg-zinc-900/40"}`} />
                    ))}
                    {/* match cards, positioned by exact time + duration */}
                    <div className="absolute inset-0 pointer-events-none">
                      {laneLayout(g.id).map(({ m, s, e, lane, cols }) => {
                        const col = colorFor(m.category_id);
                        const isBad = bad.has(m.id);
                        return (
                          <div key={m.id} draggable onDragStart={() => setDrag(m.id)} data-testid={`board-match-${m.id}`}
                            title={`${catName(m.category_id)} · ${m.time} (${dur(m)}m)`}
                            style={{
                              position: "absolute",
                              top: ((s - START) / STEP) * ROW_H + 2,
                              height: Math.max(((e - s) / STEP) * ROW_H - 4, 26),
                              left: `calc(${(lane / cols) * 100}% + 2px)`,
                              width: `calc(${100 / cols}% - 4px)`,
                              ...(isBad ? {} : { borderLeftColor: col }),
                            }}
                            className={`pointer-events-auto cursor-move overflow-hidden px-2 py-1 text-[11px] leading-tight border-l-4 border-y border-r rounded-sm ${isBad ? "border-red-500 bg-red-500/25 text-red-100 z-30" : "bg-zinc-900 text-zinc-100 border-zinc-800 hover:brightness-125 z-10"}`}>
                            <div className="flex items-center justify-between gap-1">
                              <span className="font-bold">{fmt12(s)}</span>
                              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: isBad ? undefined : col }}>{catName(m.category_id)}</span>
                            </div>
                            <div className="truncate">{names[m.home_id] || "?"} <span className="text-zinc-500">v</span> {names[m.away_id] || "?"}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* side panel */}
          <div className="space-y-4">
            <div className={`border p-5 ${errors.length ? "border-red-500/50 bg-red-500/10" : warnings.length ? "border-amber-500/40 bg-amber-500/5" : "border-lime-400/40 bg-lime-400/5"}`}>
              <div className="flex items-center gap-2">
                {errors.length ? <AlertTriangle className="w-5 h-5 text-red-500" /> : warnings.length ? <AlertTriangle className="w-5 h-5 text-amber-500" /> : <CheckCircle2 className="w-5 h-5 text-lime-400" />}
                <span className="font-display text-lg uppercase tracking-tight">{errors.length ? "Conflicts" : warnings.length ? "Warnings" : "All Clear"}</span>
              </div>
              <div className="text-xs text-zinc-400 mt-1">Tournament-wide · {errors.length} error(s) · {warnings.length} warning(s)</div>
            </div>

            <div className="border border-zinc-800 bg-zinc-900/50 p-4">
              <Overline className="mb-2">This Day</Overline>
              <div className="text-sm text-zinc-400 space-y-1">
                <div className="flex justify-between"><span>Matches</span><span className="text-zinc-200">{dayMatches.length}</span></div>
                <div className="flex justify-between"><span>Categories</span><span className="text-zinc-200">{usedCats.length}</span></div>
                <div className="flex justify-between"><span>Grounds</span><span className="text-zinc-200">{grounds.length}</span></div>
              </div>
            </div>

            <div data-testid="board-conflict-list" className="space-y-2 max-h-[420px] overflow-y-auto">
              {conflicts.length === 0 ? <p className="text-sm text-zinc-600">No conflicts. Drag matches to adjust — clashes highlight instantly in red.</p> :
                conflicts.map((x, i) => (
                  <div key={i} className={`border p-3 text-sm ${x.severity === "error" ? "border-red-500/40 bg-red-500/5 text-red-200" : "border-amber-500/30 bg-amber-500/5 text-amber-200"}`}>
                    <div className="text-[10px] uppercase tracking-widest opacity-70 mb-1">{x.type.replace(/_/g, " ")}</div>{x.message}
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
