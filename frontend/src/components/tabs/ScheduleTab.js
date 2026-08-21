import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { SectionTitle, Empty, Labeled, Overline, groundLabel } from "../bits";
import { CategoryPicker } from "../../pages/TournamentDetail";
import { Checkbox } from "../ui/checkbox";
import { CalendarClock, Zap, AlertTriangle, CheckCircle2, Save, Layers, Flag as Whistle } from "lucide-react";
import { toast } from "sonner";

const DEFAULTS = { start_date: "", end_date: "", earliest_time: "08:00", latest_time: "20:00", match_duration_minutes: 90, slot_gap_minutes: 30, min_rest_minutes: 60, max_matches_per_day: 0, break_start: "", break_end: "" };

export default function ScheduleTab({ tid, categories, activeCat, setActiveCat }) {
  const [cat, setCat] = useState(null);
  const [grounds, setGrounds] = useState([]);
  const [c, setC] = useState(DEFAULTS);
  const [conflicts, setConflicts] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [running, setRunning] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [assigningRefs, setAssigningRefs] = useState(false);

  const load = useCallback(() => {
    if (!activeCat) return;
    api.getCategory(activeCat).then((cc) => { setCat(cc); const merged = { ...DEFAULTS, ...(cc.constraints || {}) }; ["start_date", "end_date", "break_start", "break_end", "earliest_time", "latest_time"].forEach((k) => { if (merged[k] == null) merged[k] = ""; }); setC(merged); });
    api.listGrounds(tid).then(setGrounds);
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
    const payload = { ...c, match_duration_minutes: Number(c.match_duration_minutes), slot_gap_minutes: Number(c.slot_gap_minutes), min_rest_minutes: Number(c.min_rest_minutes), max_matches_per_day: Number(c.max_matches_per_day), break_start: c.break_start || null, break_end: c.break_end || null };
    await api.updateCategory(activeCat, { constraints: payload });
    toast.success("Constraints saved");
  };

  const run = async () => {
    setRunning(true);
    try {
      await saveConstraints();
      const r = await api.autoSchedule(activeCat);
      setConflicts(r.conflicts || []);
      setSuggestions(r.suggestions || []);
      if (r.unscheduled > 0) toast.warning(`${r.scheduled} scheduled · ${r.unscheduled} could not fit`);
      else toast.success(`All ${r.scheduled} matches scheduled`);
    } catch (e) { toast.error(e.response?.data?.detail || "Scheduling failed"); }
    setRunning(false);
  };

  const runTournament = async () => {
    setRunningAll(true);
    try {
      const r = await api.scheduleTournament(tid);
      setConflicts(r.conflicts || []);
      setSuggestions(r.suggestions || []);
      if (r.unscheduled > 0) toast.warning(`${r.scheduled} scheduled across ${r.categories} categories · ${r.unscheduled} could not fit`);
      else toast.success(`All ${r.scheduled} matches scheduled across ${r.categories} categories`);
      if (r.referees_assigned != null) toast.info(`${r.referees_assigned} referee assignment(s)${r.referees_unassigned ? ` · ${r.referees_unassigned} match(es) without an official` : ""}`);
    } catch (e) { toast.error(e.response?.data?.detail || "Scheduling failed"); }
    setRunningAll(false);
  };

  const runReferees = async () => {
    setAssigningRefs(true);
    try {
      const r = await api.assignReferees(tid);
      setConflicts((prev) => [...(r.conflicts || []), ...prev.filter((c) => !String(c.type).startsWith("referee") && c.type !== "no_referees")]);
      if (r.unassigned > 0) toast.warning(`${r.assigned} assigned · ${r.unassigned} match(es) left without an official`);
      else if (r.assigned === 0) toast.warning("Nothing to assign — schedule matches and add referees first");
      else toast.success(`${r.assigned} referee assignment(s) made`);
    } catch (e) { toast.error(e.response?.data?.detail || "Referee assignment failed"); }
    setAssigningRefs(false);
  };

  const errors = conflicts.filter((x) => x.severity === "error");
  const warnings = conflicts.filter((x) => x.severity === "warning");

  return (
    <div>
      <SectionTitle sub="The conflict-aware engine" title="Scheduling" right={
        <div className="flex gap-3 items-center"><CategoryPicker categories={categories} value={activeCat} onChange={setActiveCat} />
          <Button data-testid="run-scheduler-btn" onClick={run} disabled={running} className="rounded-none bg-zinc-800 text-zinc-100 hover:bg-zinc-700 font-bold uppercase tracking-wider gap-2"><Zap className="w-4 h-4" />{running ? "Solving…" : "This Category"}</Button>
        </div>} />

      <div className="border border-lime-400/30 bg-lime-400/5 p-6 mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <Overline className="text-lime-400 flex items-center gap-2"><Layers className="w-3.5 h-3.5" />Master Schedule · All Categories</Overline>
          <p className="text-sm text-zinc-400 mt-2 max-w-2xl">Schedules every category together on the shared grounds so parallel categories never collide. Fixtures stay untouched — only dates, times and grounds are (re)assigned. Locked matches are preserved as fixed anchors. Referees are assigned afterwards, respecting each official's daily limit and avoiding clashes.</p>
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
              <span className="font-display text-lg uppercase tracking-tight">{errors.length ? "Conflicts Found" : warnings.length ? "Warnings" : "All Clear"}</span>
            </div>
            <div className="text-xs text-zinc-400 mt-1">{errors.length} error(s) · {warnings.length} warning(s)</div>
          </div>
          <div data-testid="conflict-list" className="space-y-2">
            {conflicts.length === 0 ? <p className="text-sm text-zinc-600">No conflicts detected. Run the scheduler to assign dates, times and grounds automatically.</p> :
              conflicts.map((x, i) => (
                <div key={i} className={`border p-3 text-sm ${x.severity === "error" ? "border-red-500/40 bg-red-500/5 text-red-200" : "border-amber-500/30 bg-amber-500/5 text-amber-200"}`}>
                  <div className="text-[10px] uppercase tracking-widest opacity-70 mb-1">{x.type.replace(/_/g, " ")}</div>{x.message}
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
