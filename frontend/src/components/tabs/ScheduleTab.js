import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { SectionTitle, Empty, Labeled, Overline, groundLabel } from "../bits";
import { CategoryPicker } from "../../pages/TournamentDetail";
import { Checkbox } from "../ui/checkbox";
import { CalendarClock, Zap, AlertTriangle, CheckCircle2, Save, Layers, Flag as Whistle } from "lucide-react";
import { toast } from "sonner";

const DEFAULTS = { start_date: "", end_date: "", earliest_time: "08:00", latest_time: "20:00", match_duration_minutes: 90, slot_gap_minutes: 30, min_rest_minutes: 60, max_matches_per_day: 0, break_start: "", break_end: "", date_windows: {}, knockout_start_date: "", knockout_earliest_time: "" };

/** Every date in [start, end] inclusive, as YYYY-MM-DD. */
const datesBetween = (start, end) => {
  if (!start) return [];
  const out = [];
  const d = new Date(`${start}T00:00:00`);
  const last = new Date(`${end || start}T00:00:00`);
  while (d <= last && out.length < 120) {
    out.push(d.toISOString().slice(0, 10));
    d.setDate(d.getDate() + 1);
  }
  return out;
};

const dayName = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });

export default function ScheduleTab({ tid, categories, activeCat, setActiveCat }) {
  const [cat, setCat] = useState(null);
  const [tour, setTour] = useState(null);
  const [grounds, setGrounds] = useState([]);
  const [c, setC] = useState(DEFAULTS);
  const [conflicts, setConflicts] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [running, setRunning] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [assigningRefs, setAssigningRefs] = useState(false);
  const [replan, setReplan] = useState(false);

  const load = useCallback(() => {
    if (!activeCat) return;
    api.getCategory(activeCat).then((cc) => { setCat(cc); const merged = { ...DEFAULTS, ...(cc.constraints || {}) }; ["start_date", "end_date", "break_start", "break_end", "earliest_time", "latest_time", "knockout_start_date", "knockout_earliest_time"].forEach((k) => { if (merged[k] == null) merged[k] = ""; }); if (!merged.date_windows) merged.date_windows = {}; setC(merged); });
    api.listGrounds(tid).then(setGrounds);
    api.getTournament(tid).then(setTour).catch(() => {});
    api.conflicts(activeCat).then((r) => setConflicts(r.conflicts)).catch(() => {});
  }, [activeCat, tid]);
  useEffect(() => { load(); }, [load]);

  if (categories.length === 0) return <Empty icon={CalendarClock} title="No categories" hint="Create a category to configure scheduling." />;

  const set = (k, v) => setC((p) => ({ ...p, [k]: v }));
  const catGrounds = cat?.ground_ids || [];
  const toggleGround = async (gid) => {
    const next = catGrounds.includes(gid) ? catGrounds.filter((x) => x !== gid) : [...catGrounds, gid];
    await api.updateCategory(activeCat, { ground_ids: next });
    setCat((p) => ({ ...p, ground_ids: next }));
  };

  const saveConstraints = async () => {
    const payload = { ...c, match_duration_minutes: Number(c.match_duration_minutes), slot_gap_minutes: Number(c.slot_gap_minutes), min_rest_minutes: Number(c.min_rest_minutes), max_matches_per_day: Number(c.max_matches_per_day), break_start: c.break_start || null, break_end: c.break_end || null, date_windows: c.date_windows || {},
      knockout_start_date: c.knockout_start_date || null, knockout_earliest_time: c.knockout_earliest_time || null };
    await api.updateCategory(activeCat, { constraints: payload });
    toast.success("Constraints saved");
  };

  // Per-date playing hours: a date left blank simply uses the default window above.
  const tourDates = datesBetween(c.start_date || tour?.start_date, c.end_date || tour?.end_date);
  const setDateWindow = (iso, field, value) => setC((p) => {
    const dw = { ...(p.date_windows || {}) };
    const entry = { ...(dw[iso] || {}), [field]: value };
    if (!entry.earliest && !entry.latest) delete dw[iso];
    else dw[iso] = entry;
    return { ...p, date_windows: dw };
  });
  const clearDateWindow = (iso) => setC((p) => {
    const dw = { ...(p.date_windows || {}) };
    delete dw[iso];
    return { ...p, date_windows: dw };
  });

  const run = async () => {
    setRunning(true);
    try {
      await saveConstraints();
      const r = await api.autoSchedule(activeCat, replan);
      setConflicts(r.conflicts || []);
      setSuggestions(r.suggestions || []);
      if (r.message) toast.info(r.message);
      else if (r.unscheduled > 0) toast.warning(`${r.scheduled} scheduled · ${r.unscheduled} could not fit`);
      else toast.success(`All ${r.scheduled} matches scheduled`);
    } catch (e) { toast.error(e.response?.data?.detail || "Scheduling failed"); }
    setRunning(false);
  };

  const runTournament = async () => {
    setRunningAll(true);
    try {
      const r = await api.scheduleTournament(tid, replan);
      if (r.message) toast.info(r.message);
      setConflicts(r.conflicts || []);
      setSuggestions(r.suggestions || []);
      if (r.unscheduled > 0) toast.warning(`${r.scheduled} scheduled across ${r.categories} categories · ${r.unscheduled} could not fit`);
      else toast.success(`All ${r.scheduled} matches scheduled across ${r.categories} categories`);
      // Referees are optional — only mention them if the organizer is actually using them.
      if (r.referees_assigned > 0 || r.referees_unassigned > 0)
        toast.info(`${r.referees_assigned} referee assignment(s)${r.referees_unassigned ? ` · ${r.referees_unassigned} match(es) without an official` : ""}`);
    } catch (e) { toast.error(e.response?.data?.detail || "Scheduling failed"); }
    setRunningAll(false);
  };

  const runReferees = async () => {
    setAssigningRefs(true);
    try {
      const r = await api.assignReferees(tid);
      setConflicts((prev) => [...(r.conflicts || []), ...prev.filter((c) => !String(c.type).startsWith("referee") && c.type !== "no_referees")]);
      if (r.unassigned > 0) toast.warning(`${r.assigned} assigned · ${r.unassigned} match(es) left without an official`);
      else if (r.assigned === 0) toast.info("No referees to assign — add them in Grounds & Referees if you want officials on the schedule");
      else toast.success(`${r.assigned} referee assignment(s) made`);
    } catch (e) { toast.error(e.response?.data?.detail || "Referee assignment failed"); }
    setAssigningRefs(false);
  };

  const errors = conflicts.filter((x) => x.severity === "error");
  const warnings = conflicts.filter((x) => x.severity === "warning");
  // "Doesn't fit" is a configuration problem, not a broken schedule — say so plainly,
  // and lead with the settings-level explanations rather than per-match noise.
  const FIT_TYPES = ["capacity", "impossible_config", "unplaced_match", "no_grounds"];
  const fitOnly = errors.length > 0 && errors.every((x) => FIT_TYPES.includes(x.type));
  const headline = errors.length === 0 ? (warnings.length ? "Warnings" : "All Clear")
    : fitOnly ? "Doesn't Fit Yet" : "Conflicts Found";
  const rank = (x) => (x.type === "impossible_config" ? 0 : x.type === "no_grounds" ? 1
    : x.type === "capacity" ? 2 : x.severity === "error" ? 3 : 4);
  const ordered = [...conflicts].sort((a, b) => rank(a) - rank(b));

  return (
    <div>
      <SectionTitle sub="The conflict-aware engine" title="Scheduling" right={
        <div className="flex gap-3 items-center"><CategoryPicker categories={categories} value={activeCat} onChange={setActiveCat} />
          <Button data-testid="run-scheduler-btn" onClick={run} disabled={running} className="rounded-none bg-zinc-800 text-zinc-100 hover:bg-zinc-700 font-bold uppercase tracking-wider gap-2"><Zap className="w-4 h-4" />{running ? "Solving…" : "This Category"}</Button>
        </div>} />

      <div className="border border-lime-400/30 bg-lime-400/5 p-6 mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <Overline className="text-lime-400 flex items-center gap-2"><Layers className="w-3.5 h-3.5" />Master Schedule · All Categories</Overline>
          <p className="text-sm text-zinc-400 mt-2 max-w-2xl">Schedules every category together on the shared grounds so parallel categories never collide. Fixtures stay untouched — only dates, times and grounds are (re)assigned. Referees are assigned afterwards, respecting each official's daily limit and avoiding clashes.</p>
          <label className="flex items-start gap-2.5 mt-4 cursor-pointer max-w-2xl" data-testid="replan-toggle">
            <input type="checkbox" checked={replan} onChange={(e) => setReplan(e.target.checked)}
              className="mt-0.5 accent-lime-400" />
            <span className="text-sm text-zinc-400">
              <b className="text-zinc-200">Re-plan everything</b> — rebuild the entire schedule from scratch.
              <span className="block text-xs text-zinc-600 mt-0.5">
                Leave this off to keep matches that already have a slot and just fill in the rest.
                Locked matches never move either way.
              </span>
            </span>
          </label>
        </div>
        <div className="flex gap-3 shrink-0 flex-wrap">
          <Button data-testid="assign-referees-btn" onClick={runReferees} disabled={assigningRefs} className="rounded-none bg-zinc-800 text-zinc-100 hover:bg-zinc-700 font-bold uppercase tracking-wider gap-2"><Whistle className="w-4 h-4" />{assigningRefs ? "Assigning…" : "Assign Referees"}</Button>
          <Button data-testid="run-tournament-scheduler-btn" onClick={runTournament} disabled={runningAll} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2"><Zap className="w-4 h-4" />{runningAll ? "Solving…" : "Schedule Whole Tournament"}</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="border border-zinc-800 bg-zinc-900/50 p-6">
            <div className="flex items-center justify-between mb-5"><Overline>Constraints</Overline>
              <Button data-testid="save-constraints-btn" onClick={saveConstraints} variant="ghost" className="rounded-none text-lime-400 hover:bg-zinc-800 hover:text-lime-400 gap-2 h-8 text-xs uppercase tracking-wider"><Save className="w-3.5 h-3.5" />Save</Button></div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <Labeled label="Start Date"><Input data-testid="sched-start" type="date" value={c.start_date || ""} onChange={(e) => set("start_date", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="End Date"><Input data-testid="sched-end" type="date" value={c.end_date || ""} onChange={(e) => set("end_date", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Max Matches/Day"><Input type="number" value={c.max_matches_per_day} onChange={(e) => set("max_matches_per_day", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Earliest Time"><Input type="time" value={c.earliest_time} onChange={(e) => set("earliest_time", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Latest Time"><Input type="time" value={c.latest_time} onChange={(e) => set("latest_time", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Match Duration (min)"><Input type="number" value={c.match_duration_minutes} onChange={(e) => set("match_duration_minutes", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Gap Between Slots (min)"><Input type="number" value={c.slot_gap_minutes} onChange={(e) => set("slot_gap_minutes", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Min Rest per Team (min)"><Input type="number" value={c.min_rest_minutes} onChange={(e) => set("min_rest_minutes", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Break Start"><Input data-testid="break-start" type="time" value={c.break_start} onChange={(e) => set("break_start", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Break End"><Input data-testid="break-end" type="time" value={c.break_end} onChange={(e) => set("break_end", e.target.value)} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            </div>
            <p className="text-xs text-zinc-600 mt-4">Leave dates blank to inherit the tournament dates. Max matches/day = 0 means unlimited.</p>

            {(cat?.format === "knockout" || cat?.format === "groups_knockout") && (
              <div className="mt-6 border-t border-zinc-800 pt-5">
                <Overline className="mb-1">Knockout Stage <span className="normal-case tracking-normal text-zinc-600">(optional)</span></Overline>
                <p className="text-xs text-zinc-600 mb-4">
                  By default the knockout is scheduled as soon as the matches feeding it are finished.
                  Set these to hold it back — for example a finals day, or afternoon-only finals.
                </p>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <Labeled label="Not Before Date">
                    <Input data-testid="ko-start-date" type="date" value={c.knockout_start_date || ""}
                      onChange={(e) => set("knockout_start_date", e.target.value)}
                      className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" />
                  </Labeled>
                  <Labeled label="Not Before Time">
                    <Input data-testid="ko-earliest-time" type="time" value={c.knockout_earliest_time || ""}
                      onChange={(e) => set("knockout_earliest_time", e.target.value)}
                      className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" />
                  </Labeled>
                </div>
              </div>
            )}

            {tourDates.length > 0 && (
              <div className="mt-6 border-t border-zinc-800 pt-5">
                <Overline className="mb-1">Playing Hours Per Day <span className="normal-case tracking-normal text-zinc-600">(optional)</span></Overline>
                <p className="text-xs text-zinc-600 mb-4">
                  Different hours on different days — a Friday evening session, full days at the weekend.
                  Leave a day blank and it uses the {c.earliest_time}–{c.latest_time} window above.
                </p>
                <div className="space-y-2">
                  {tourDates.map((iso) => {
                    const dw = (c.date_windows || {})[iso] || {};
                    const custom = !!(dw.earliest || dw.latest);
                    return (
                      <div key={iso} data-testid={`date-window-${iso}`}
                        className={`grid grid-cols-12 gap-3 items-center px-3 py-2 border ${custom ? "border-lime-400/30 bg-lime-400/5" : "border-zinc-800"}`}>
                        <div className="col-span-5 sm:col-span-4 text-sm">
                          <div className="text-zinc-200">{dayName(iso)}</div>
                          <div className="text-[10px] text-zinc-600">{iso}</div>
                        </div>
                        <div className="col-span-3">
                          <Input type="time" aria-label={`${iso} from`} value={dw.earliest || ""}
                            onChange={(e) => setDateWindow(iso, "earliest", e.target.value)}
                            className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400 h-9 text-sm" />
                        </div>
                        <div className="col-span-3">
                          <Input type="time" aria-label={`${iso} to`} value={dw.latest || ""}
                            onChange={(e) => setDateWindow(iso, "latest", e.target.value)}
                            className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400 h-9 text-sm" />
                        </div>
                        <div className="col-span-1 text-right">
                          {custom && (
                            <button onClick={() => clearDateWindow(iso)} title="Use the default window"
                              className="text-zinc-600 hover:text-red-400 text-xs uppercase tracking-wider">Reset</button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <p className="text-xs text-zinc-600 mt-3">Remember to Save — then re-run the scheduler.</p>
              </div>
            )}
          </div>

          <div className="border border-zinc-800 bg-zinc-900/50 p-6">
            <Overline className="mb-4">Grounds for this category <span className="normal-case tracking-normal text-zinc-600">(none selected = all grounds)</span></Overline>
            {grounds.length === 0 ? <p className="text-sm text-zinc-500">No grounds added yet — add them in Grounds & Referees.</p> :
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {grounds.map((g) => (
                  <label key={g.id} data-testid={`ground-toggle-${g.id}`} className="flex items-center gap-2 border border-zinc-800 p-3 cursor-pointer hover:border-zinc-600">
                    <Checkbox checked={catGrounds.includes(g.id)} onCheckedChange={() => toggleGround(g.id)} className="rounded-none border-zinc-600 data-[state=checked]:bg-lime-400 data-[state=checked]:text-black" />
                    <span className="text-sm">{groundLabel(g.name)}</span>
                  </label>
                ))}
              </div>}
          </div>
        </div>

        <div className="space-y-4">
          <div className={`border p-5 ${errors.length ? "border-red-500/50 bg-red-500/10" : warnings.length ? "border-amber-500/40 bg-amber-500/5" : "border-lime-400/40 bg-lime-400/5"}`}>
            <div className="flex items-center gap-2">
              {errors.length ? <AlertTriangle className="w-5 h-5 text-red-500" /> : warnings.length ? <AlertTriangle className="w-5 h-5 text-amber-500" /> : <CheckCircle2 className="w-5 h-5 text-lime-400" />}
              <span className="font-display text-lg uppercase tracking-tight">{headline}</span>
            </div>
            <div className="text-xs text-zinc-400 mt-1">
              {fitOnly
                ? "The schedule that was produced is valid — these matches simply have nowhere left to go. Change a setting below and run it again."
                : `${errors.length} error(s) · ${warnings.length} warning(s)`}
            </div>
          </div>
          <div data-testid="conflict-list" className="space-y-2">
            {conflicts.length === 0 ? <p className="text-sm text-zinc-600">No conflicts detected. Run the scheduler to assign dates, times and grounds automatically.</p> :
              ordered.map((x, i) => (
                <div key={i} className={`border p-3 text-sm ${x.type === "impossible_config" ? "border-orange-500/50 bg-orange-500/10 text-orange-100" : x.severity === "error" ? "border-red-500/40 bg-red-500/5 text-red-200" : "border-amber-500/30 bg-amber-500/5 text-amber-200"}`}>
                  <div className="text-[10px] uppercase tracking-widest opacity-70 mb-1">
                    {x.type === "impossible_config" ? "Setting needs changing" : x.type.replace(/_/g, " ")}
                  </div>{x.message}
                </div>
              ))}
          </div>
          {suggestions.length > 0 && (
            <div className="border border-amber-500/30 bg-amber-500/5 p-4" data-testid="suggestions-list">
              <Overline className="text-amber-400 mb-2">How to fix</Overline>
              <ul className="text-sm text-amber-100/80 space-y-1.5 list-disc pl-4">
                {suggestions.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
