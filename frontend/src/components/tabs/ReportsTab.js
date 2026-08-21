import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { SectionTitle, Empty, Overline, groundLabel } from "../bits";
import { Button } from "../ui/button";
import { FileText, Download, Clock, MapPin } from "lucide-react";

export default function ReportsTab({ tid, categories }) {
  const [schedule, setSchedule] = useState([]);
  const [names, setNames] = useState({});
  const [view, setView] = useState("time");

  const load = useCallback(async () => {
    const sched = await api.schedule(tid);
    setSchedule(sched);
    const grounds = await api.listGrounds(tid);
    const gmap = {}; grounds.forEach((g) => (gmap[g.id] = groundLabel(g.name)));
    const tmap = {};
    for (const c of categories) { const ts = await api.listTeams(c.id); ts.forEach((t) => (tmap[t.id] = t.name)); }
    setNames({ ...gmap, ...tmap });
  }, [tid, categories]);
  useEffect(() => { load(); }, [load]);

  const n = (id) => names[id] || (id ? "?" : "BYE");
  const catMap = {}; (categories || []).forEach((c) => (catMap[c.id] = c.name));
  const cat = (id) => catMap[id] || "—";
  const fmtTime = (t) => {
    if (!t) return "";
    const [hStr, mStr] = t.split(":");
    let h = parseInt(hStr, 10);
    const m = mStr ?? "00";
    const ampm = h >= 12 ? "pm" : "am";
    h = h % 12; if (h === 0) h = 12;
    return `${h}:${m}${ampm}`;
  };
  const cmpTime = (a, b) => `${a.date || ""} ${a.time || ""}`.localeCompare(`${b.date || ""} ${b.time || ""}`);

  const byDate = schedule.reduce((a, m) => { (a[m.date] = a[m.date] || []).push(m); return a; }, {});

  const byGround = schedule.reduce((a, m) => { (a[m.ground_id] = a[m.ground_id] || []).push(m); return a; }, {});
  const groundKeys = Object.keys(byGround).sort((a, b) =>
    n(a).localeCompare(n(b), undefined, { numeric: true, sensitivity: "base" }));

  const exportCSV = () => {
    const rows = [["Date", "Time", "Category", "Home", "Away", "Ground", "Score", "Status"]];
    let ordered;
    if (view === "ground") {
      ordered = groundKeys.flatMap((gid) => [...byGround[gid]].sort(cmpTime));
    } else {
      ordered = [...schedule].sort(cmpTime);
    }
    ordered.forEach((m) => rows.push([m.date, fmtTime(m.time), cat(m.category_id), n(m.home_id), n(m.away_id), n(m.ground_id), m.home_score != null ? `${m.home_score}-${m.away_score}` : "", m.status]));
    const csv = rows.map((r) => r.map((c) => `"${c ?? ""}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = view === "ground" ? "schedule-by-ground.csv" : "schedule-by-time.csv"; a.click();
  };

  const Row = ({ m, showDate }) => (
    <div className="grid grid-cols-12 gap-2 px-4 py-3 items-center text-sm">
      <div className="col-span-2 text-zinc-500 font-display" data-testid={`report-time-${m.id}`}>
        {fmtTime(m.time)}{showDate && <span className="block text-xs text-zinc-500 mt-0.5">{m.date}</span>}
      </div>
      <div className="col-span-4 text-right font-semibold truncate">{n(m.home_id)}</div>
      <div className="col-span-1 text-center text-zinc-500">{m.home_score != null ? `${m.home_score}-${m.away_score}` : "v"}</div>
      <div className="col-span-3 font-semibold truncate">{n(m.away_id)}</div>
      <div className="col-span-2 text-right text-xs text-zinc-600 truncate flex flex-col items-end gap-0.5">
        <span className="text-lime-400 uppercase tracking-wider" data-testid={`report-cat-${m.id}`}>{cat(m.category_id)}</span>
        {view !== "ground" && <span>{n(m.ground_id)}</span>}
      </div>
    </div>
  );

  const ToggleBtn = ({ id, icon: Icon, label }) => (
    <button data-testid={`report-view-${id}`} onClick={() => setView(id)}
      className={`flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-wider font-bold border transition-colors ${view === id ? "bg-lime-400 text-black border-lime-400" : "bg-transparent text-zinc-400 border-zinc-800 hover:border-zinc-600"}`}>
      <Icon className="w-3.5 h-3.5" />{label}
    </button>
  );

  return (
    <div>
      <SectionTitle sub="Master schedule & exports" title="Reports" right={
        <Button data-testid="export-csv-btn" onClick={exportCSV} disabled={schedule.length === 0} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2"><Download className="w-4 h-4" />Export CSV</Button>} />

      {schedule.length === 0 ? <Empty icon={FileText} title="Nothing scheduled yet" hint="Generate fixtures and run the scheduler to build the master schedule across all categories." /> : (
        <>
          <div className="flex gap-2 mb-6">
            <ToggleBtn id="time" icon={Clock} label="By Time" />
            <ToggleBtn id="ground" icon={MapPin} label="By Ground" />
          </div>

          {view === "time" ? (
            <div className="space-y-8">
              {Object.entries(byDate).map(([d, ms]) => (
                <div key={d}>
                  <Overline className="mb-3 text-lime-400">{d} · {ms.length} matches</Overline>
                  <div className="border border-zinc-800 divide-y divide-zinc-800">
                    {[...ms].sort(cmpTime).map((m) => <Row key={m.id} m={m} />)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-8">
              {groundKeys.map((gid) => (
                <div key={gid}>
                  <Overline className="mb-3 text-lime-400">{n(gid)} · {byGround[gid].length} matches</Overline>
                  <div className="border border-zinc-800 divide-y divide-zinc-800">
                    {[...byGround[gid]].sort(cmpTime).map((m) => <Row key={m.id} m={m} showDate />)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
