import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../ui/dialog";
import { SectionTitle, Empty, Labeled, Overline, groundLabel } from "../bits";
import { MapPin, Plus, Trash2, Flag as Whistle, Clock, Zap } from "lucide-react";
import { toast } from "sonner";

const gBlank = { name: "", capacity: "", surface: "Grass", lighting: false, open_time: "", close_time: "", priority: 1 };
const rBlank = { name: "", certification: "", experience_years: "", max_matches_per_day: 3, phone: "" };

export default function VenuesTab({ tid }) {
  const [grounds, setGrounds] = useState([]);
  const [refs, setRefs] = useState([]);
  const [gOpen, setGOpen] = useState(false);
  const [rOpen, setROpen] = useState(false);
  const [gForm, setGForm] = useState(gBlank);
  const [rForm, setRForm] = useState(rBlank);

  const load = useCallback(() => { api.listGrounds(tid).then(setGrounds); api.listReferees(tid).then(setRefs); }, [tid]);
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
                <div className="flex justify-between items-start"><h4 className="font-display text-xl uppercase">{groundLabel(g.name)}</h4><button data-testid={`delete-ground-${g.id}`} onClick={async () => { await api.deleteGround(g.id); load(); }} className="text-zinc-600 hover:text-red-500"><Trash2 className="w-4 h-4" /></button></div>
                <div className="text-sm text-zinc-400 mt-3 space-y-1">
                  <div>{g.surface} {g.lighting && <span className="text-lime-400 ml-1 inline-flex items-center gap-1"><Zap className="w-3 h-3" />Floodlit</span>}</div>
                  {(g.open_time || g.close_time) && <div className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-zinc-600" />{g.open_time || "—"} – {g.close_time || "—"}</div>}
                  {g.capacity && <div>Capacity {g.capacity}</div>}
                  <div className="text-zinc-600 text-xs">Priority {g.priority}</div>
                </div>
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
                <div className="flex justify-between items-start"><h4 className="font-display text-xl uppercase">{r.name}</h4><button data-testid={`delete-referee-${r.id}`} onClick={async () => { await api.deleteReferee(r.id); load(); }} className="text-zinc-600 hover:text-red-500"><Trash2 className="w-4 h-4" /></button></div>
                <div className="text-sm text-zinc-400 mt-3 space-y-1">
                  {r.certification && <div className="text-lime-400 text-xs uppercase tracking-wider">{r.certification}</div>}
                  {r.experience_years != null && <div>{r.experience_years} yrs experience</div>}
                  <div className="text-zinc-600 text-xs">Max {r.max_matches_per_day} matches/day</div>
                </div>
              </div>
            ))}
          </div>}
      </div>

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
