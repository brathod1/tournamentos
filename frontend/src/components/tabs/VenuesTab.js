import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../ui/dialog";
import { SectionTitle, Empty, Labeled, Overline, groundLabel, ConfirmDelete } from "../bits";
import { MapPin, Plus, Trash2, Flag as Whistle, Clock, Zap } from "lucide-react";
import { toast } from "sonner";

const gBlank = { name: "", capacity: "", surface: "Grass", lighting: false, open_time: "", close_time: "", priority: 1 };
const rBlank = { name: "", certification: "", experience_years: "", max_matches_per_day: 3, phone: "" };

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
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });

export default function VenuesTab({ tid }) {
  const [grounds, setGrounds] = useState([]);
  const [refs, setRefs] = useState([]);
  const [tour, setTour] = useState(null);
  const [gOpen, setGOpen] = useState(false);
  const [rOpen, setROpen] = useState(false);
  const [gForm, setGForm] = useState(gBlank);
  const [rForm, setRForm] = useState(rBlank);
  const [hoursFor, setHoursFor] = useState(null);   // ground whose per-day hours we're editing

  const load = useCallback(() => {
    api.listGrounds(tid).then(setGrounds);
    api.listReferees(tid).then(setRefs);
    api.getTournament(tid).then(setTour).catch(() => {});
  }, [tid]);
  useEffect(() => { load(); }, [load]);

  const saveG = async () => {
    if (!gForm.name.trim()) return toast.error("Ground name required");
    await api.createGround(tid, { ...gForm, capacity: gForm.capacity ? Number(gForm.capacity) : null, priority: Number(gForm.priority), open_time: gForm.open_time || null, close_time: gForm.close_time || null });
    toast.success("Ground added"); setGOpen(false); setGForm(gBlank); load();
  };
  const saveR = async () => {
    if (!rForm.name.trim()) return toast.error("Referee name required");
    await api.createReferee(tid, { ...rForm, experience_years: rForm.experience_years ? Number(rForm.experience_years) : null, max_matches_per_day: Number(rForm.max_matches_per_day) });
    toast.success("Referee added"); setROpen(false); setRForm(rBlank); load();
  };

  return (
    <div className="space-y-12">
      <div>
        <SectionTitle sub="Where matches happen" title="Grounds" right={
          <Button data-testid="add-ground-btn" onClick={() => setGOpen(true)} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2"><Plus className="w-4 h-4" />Add Ground</Button>} />
        {grounds.length === 0 ? <Empty icon={MapPin} title="No grounds" hint="Grounds carry availability windows, surface, lighting and priority — the scheduler uses these." /> :
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {grounds.map((g) => (
              <div key={g.id} data-testid={`ground-card-${g.id}`} className="border border-zinc-800 bg-zinc-900/50 p-5">
                <div className="flex justify-between items-start"><h4 className="font-display text-xl uppercase">{groundLabel(g.name)}</h4>
                  <ConfirmDelete title="Delete ground?" testId={`confirm-delete-ground-${g.id}`}
                    description={`Deleting "${groundLabel(g.name)}" affects any matches already scheduled on it and any category restricted to it — you'll need to reschedule.`}
                    onConfirm={async () => { await api.deleteGround(g.id); load(); }}>
                    <button data-testid={`delete-ground-${g.id}`} className="text-zinc-600 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
                  </ConfirmDelete></div>
                <div className="text-sm text-zinc-400 mt-3 space-y-1">
                  <div>{g.surface} {g.lighting && <span className="text-lime-400 ml-1 inline-flex items-center gap-1"><Zap className="w-3 h-3" />Floodlit</span>}</div>
                  {(g.open_time || g.close_time) && <div className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-zinc-600" />{g.open_time || "—"} – {g.close_time || "—"}</div>}
                  {g.capacity && <div>Capacity {g.capacity}</div>}
                  <div className="text-zinc-600 text-xs">Priority {g.priority}</div>
                  {Object.keys(g.date_hours || {}).length > 0 && (
                    <div className="text-lime-400 text-xs">{Object.keys(g.date_hours).length} day-specific hour(s)</div>
                  )}
                </div>
                <button data-testid={`ground-hours-${g.id}`} onClick={() => setHoursFor(g)}
                  className="mt-4 text-xs uppercase tracking-wider text-zinc-500 hover:text-lime-400 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />Hours per day
                </button>
              </div>
            ))}
          </div>}
      </div>

      <div>
        <SectionTitle sub="Match officials" title="Referees" right={
          <Button data-testid="add-referee-btn" onClick={() => setROpen(true)} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2"><Plus className="w-4 h-4" />Add Referee</Button>} />
        {refs.length === 0 ? <Empty icon={Whistle} title="No referees" hint="Track certification, experience and per-day limits for conflict-free assignment." /> :
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {refs.map((r) => (
              <div key={r.id} data-testid={`referee-card-${r.id}`} className="border border-zinc-800 bg-zinc-900/50 p-5">
                <div className="flex justify-between items-start"><h4 className="font-display text-xl uppercase">{r.name}</h4>
                  <ConfirmDelete title="Delete referee?" testId={`confirm-delete-referee-${r.id}`}
                    description={`This removes "${r.name}" from the tournament and unassigns them from any matches.`}
                    onConfirm={async () => { await api.deleteReferee(r.id); load(); }}>
                    <button data-testid={`delete-referee-${r.id}`} className="text-zinc-600 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
                  </ConfirmDelete></div>
                <div className="text-sm text-zinc-400 mt-3 space-y-1">
                  {r.certification && <div className="text-lime-400 text-xs uppercase tracking-wider">{r.certification}</div>}
                  {r.experience_years != null && <div>{r.experience_years} yrs experience</div>}
                  <div className="text-zinc-600 text-xs">Max {r.max_matches_per_day} matches/day</div>
                </div>
              </div>
            ))}
          </div>}
      </div>

      <GroundHoursDialog ground={hoursFor} tour={tour} onClose={() => setHoursFor(null)} reload={load} />

      <Dialog open={gOpen} onOpenChange={setGOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none max-w-lg">
          <DialogHeader><DialogTitle className="font-display text-2xl uppercase tracking-tight">Add Ground</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-2">
            <div className="col-span-2"><Labeled label="Name"><Input data-testid="ground-name-input" value={gForm.name} onChange={(e) => setGForm({ ...gForm, name: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
            <Labeled label="Surface"><Input value={gForm.surface} onChange={(e) => setGForm({ ...gForm, surface: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Capacity"><Input type="number" value={gForm.capacity} onChange={(e) => setGForm({ ...gForm, capacity: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Opens"><Input type="time" value={gForm.open_time} onChange={(e) => setGForm({ ...gForm, open_time: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Closes"><Input type="time" value={gForm.close_time} onChange={(e) => setGForm({ ...gForm, close_time: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Priority"><Input type="number" value={gForm.priority} onChange={(e) => setGForm({ ...gForm, priority: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Floodlights"><Button type="button" onClick={() => setGForm({ ...gForm, lighting: !gForm.lighting })} className={`rounded-none w-full ${gForm.lighting ? "bg-lime-400 text-black hover:bg-lime-500" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}>{gForm.lighting ? "Yes" : "No"}</Button></Labeled>
          </div>
          <DialogFooter><Button data-testid="save-ground-btn" onClick={saveG} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider w-full">Add Ground</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={rOpen} onOpenChange={setROpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none max-w-lg">
          <DialogHeader><DialogTitle className="font-display text-2xl uppercase tracking-tight">Add Referee</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-2">
            <div className="col-span-2"><Labeled label="Name"><Input data-testid="referee-name-input" value={rForm.name} onChange={(e) => setRForm({ ...rForm, name: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
            <Labeled label="Certification"><Input value={rForm.certification} onChange={(e) => setRForm({ ...rForm, certification: e.target.value })} placeholder="FIFA / National" className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Experience (yrs)"><Input type="number" value={rForm.experience_years} onChange={(e) => setRForm({ ...rForm, experience_years: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Max Matches/Day"><Input type="number" value={rForm.max_matches_per_day} onChange={(e) => setRForm({ ...rForm, max_matches_per_day: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Phone"><Input value={rForm.phone} onChange={(e) => setRForm({ ...rForm, phone: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
          </div>
          <DialogFooter><Button data-testid="save-referee-btn" onClick={saveR} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider w-full">Add Referee</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Per-date opening hours for one ground — for venues that are only free some evenings,
 *  or closed entirely on a given day. Blank rows fall back to the ground's normal hours. */
function GroundHoursDialog({ ground, tour, onClose, reload }) {
  const [hours, setHours] = useState({});
  useEffect(() => { setHours(ground?.date_hours || {}); }, [ground]);
  if (!ground) return null;

  const dates = datesBetween(tour?.start_date, tour?.end_date);
  const set = (iso, field, value) => setHours((p) => {
    const entry = { ...(p[iso] || {}), [field]: value };
    if (field !== "closed" && !value) delete entry[field];
    if (!entry.open && !entry.close && !entry.closed) { const n = { ...p }; delete n[iso]; return n; }
    return { ...p, [iso]: entry };
  });
  const clear = (iso) => setHours((p) => { const n = { ...p }; delete n[iso]; return n; });

  const save = async () => {
    try {
      await api.updateGround(ground.id, { date_hours: hours });
      toast.success("Ground hours saved");
      reload(); onClose();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save hours"); }
  };

  return (
    <Dialog open={!!ground} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display text-2xl uppercase tracking-tight">
          {groundLabel(ground.name)} · Hours Per Day
        </DialogTitle></DialogHeader>

        {dates.length === 0 ? (
          <p className="text-sm text-zinc-400">Set the tournament start and end dates first — then you can give this ground different hours on each day.</p>
        ) : (<>
          <p className="text-xs text-zinc-500">
            Leave a day blank to use this ground's normal hours ({ground.open_time || "—"} – {ground.close_time || "—"}).
            Tick <b className="text-zinc-300">Closed</b> to take the ground out of use for that day entirely.
          </p>
          <div className="space-y-2">
            {dates.map((iso) => {
              const h = hours[iso] || {};
              const custom = !!(h.open || h.close || h.closed);
              return (
                <div key={iso} data-testid={`ground-date-${iso}`}
                  className={`grid grid-cols-12 gap-3 items-center px-3 py-2 border ${custom ? "border-lime-400/30 bg-lime-400/5" : "border-zinc-800"}`}>
                  <div className="col-span-4 sm:col-span-3 text-sm">
                    <div className="text-zinc-200">{dayName(iso)}</div>
                    <div className="text-[10px] text-zinc-600">{iso}</div>
                  </div>
                  <div className="col-span-3">
                    <Input type="time" aria-label={`${iso} open`} disabled={!!h.closed} value={h.open || ""}
                      onChange={(e) => set(iso, "open", e.target.value)}
                      className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400 h-9 text-sm disabled:opacity-40" />
                  </div>
                  <div className="col-span-3">
                    <Input type="time" aria-label={`${iso} close`} disabled={!!h.closed} value={h.close || ""}
                      onChange={(e) => set(iso, "close", e.target.value)}
                      className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400 h-9 text-sm disabled:opacity-40" />
                  </div>
                  <label className="col-span-2 flex items-center gap-1.5 text-xs text-zinc-400 cursor-pointer">
                    <input type="checkbox" checked={!!h.closed}
                      onChange={(e) => (e.target.checked ? set(iso, "closed", true) : clear(iso))}
                      className="accent-red-500" />
                    Closed
                  </label>
                </div>
              );
            })}
          </div>
        </>)}

        <DialogFooter className="gap-2">
          <Button onClick={onClose} className="rounded-none bg-zinc-800 hover:bg-zinc-700 text-zinc-100 uppercase tracking-wider">Cancel</Button>
          <Button data-testid="save-ground-hours-btn" onClick={save} disabled={dates.length === 0}
            className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider">Save Hours</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
