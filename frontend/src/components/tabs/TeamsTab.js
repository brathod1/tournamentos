import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../ui/dialog";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "../ui/select";
import { SectionTitle, Empty, Labeled, Overline } from "../bits";
import { CategoryPicker } from "../../pages/TournamentDetail";
import { Users, Plus, Trash2, UserCog, Clock, Ban, Settings2 } from "lucide-react";
import { toast } from "sonner";

const blank = { name: "", short_name: "", coach: "", city: "", association: "", seed: "",
  available_from: "", available_to: "", no_back_to_back: false,
  day_preference: "any", max_matches_per_day: "", unavailable_dates: "" };

export default function TeamsTab({ categories, activeCat, setActiveCat, reload }) {
  const [teams, setTeams] = useState([]);
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState(blank);

  const load = useCallback(() => { if (activeCat) api.listTeams(activeCat).then(setTeams); }, [activeCat]);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEdit(null); setForm(blank); setOpen(true); };
  const openEdit = (t) => {
    setEdit(t);
    setForm({ ...blank, ...t, seed: t.seed ?? "", available_from: t.available_from || "", available_to: t.available_to || "", day_preference: t.day_preference || "any", max_matches_per_day: t.max_matches_per_day ?? "", unavailable_dates: (t.unavailable_dates || []).join(", ") });
    setOpen(true);
  };

  const save = async () => {
    if (!form.name.trim()) return toast.error("Team name required");
    const payload = { ...form, seed: form.seed ? Number(form.seed) : null,
      available_from: form.available_from || null, available_to: form.available_to || null,
      max_matches_per_day: form.max_matches_per_day ? Number(form.max_matches_per_day) : null,
      unavailable_dates: form.unavailable_dates ? form.unavailable_dates.split(",").map((s) => s.trim()).filter(Boolean) : [] };
    if (edit) { await api.updateTeam(edit.id, payload); toast.success("Team updated"); }
    else { await api.createTeam(activeCat, payload); toast.success("Team added"); }
    setOpen(false); load(); reload();
  };
  const remove = async (id) => {
    try { await api.deleteTeam(id); toast.success("Team removed"); load(); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not delete team"); }
  };

  if (categories.length === 0) return <Empty icon={Users} title="No categories yet" hint="Create a category first — teams belong to a category." />;

  return (
    <div>
      <SectionTitle sub="Participants" title="Teams" right={
        <div className="flex gap-3 items-center">
          <CategoryPicker categories={categories} value={activeCat} onChange={setActiveCat} />
          <Button data-testid="add-team-btn" onClick={openNew} disabled={!activeCat} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2"><Plus className="w-4 h-4" />Add Team</Button>
        </div>} />
      {teams.length === 0 ? (
        <Empty icon={Users} title="No teams in this category" hint="Add teams — any number, odd or even. Set each team's playable hours and back-to-back rule so the scheduler respects them." />
      ) : (
        <div className="border border-zinc-800">
          <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-zinc-800 text-[10px] uppercase tracking-widest text-zinc-500 bg-zinc-900/50">
            <div className="col-span-1">#</div><div className="col-span-3">Team</div><div className="col-span-2">Coach</div><div className="col-span-2">City / Assoc.</div><div className="col-span-3">Availability</div><div className="col-span-1"></div>
          </div>
          {teams.map((t, i) => (
            <div key={t.id} data-testid={`team-row-${t.id}`} className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-zinc-800/60 items-center hover:bg-zinc-900/40 transition-colors">
              <div className="col-span-1 text-zinc-500 font-display">{t.seed || i + 1}</div>
              <div className="col-span-3 font-semibold truncate">{t.name}{t.short_name && <span className="text-zinc-600 ml-2 text-xs">{t.short_name}</span>}</div>
              <div className="col-span-2 text-sm text-zinc-400 flex items-center gap-1.5 truncate">{t.coach && <UserCog className="w-3.5 h-3.5 text-zinc-600 shrink-0" />}{t.coach || "—"}</div>
              <div className="col-span-2 text-sm text-zinc-400 truncate">{[t.city, t.association].filter(Boolean).join(" · ") || "—"}</div>
              <div className="col-span-3 flex items-center gap-2 flex-wrap">
                {(t.available_from || t.available_to) ? (
                  <span className="text-xs text-lime-400 flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{t.available_from || "…"}–{t.available_to || "…"}</span>
                ) : <span className="text-xs text-zinc-600 flex items-center gap-1"><Clock className="w-3.5 h-3.5" />Any time</span>}
                {t.no_back_to_back && <span className="text-xs text-amber-400 flex items-center gap-1"><Ban className="w-3.5 h-3.5" />No B2B</span>}
                {t.day_preference && t.day_preference !== "any" && <span className="text-xs text-sky-400">{t.day_preference === "weekend" ? "Weekend" : "Weekday"}</span>}
              </div>
              <div className="col-span-1 text-right flex justify-end gap-2">
                <button data-testid={`edit-team-${t.id}`} onClick={() => openEdit(t)} className="text-zinc-600 hover:text-lime-400"><Settings2 className="w-4 h-4" /></button>
                <button data-testid={`delete-team-${t.id}`} onClick={() => remove(t.id)} className="text-zinc-600 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display text-2xl uppercase tracking-tight">{edit ? "Edit" : "Add"} Team</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-2">
            <div className="col-span-2"><Labeled label="Team Name"><Input data-testid="team-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
            <Labeled label="Short Name"><Input value={form.short_name} onChange={(e) => setForm({ ...form, short_name: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Seed (optional)"><Input type="number" value={form.seed} onChange={(e) => setForm({ ...form, seed: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="Coach"><Input value={form.coach} onChange={(e) => setForm({ ...form, coach: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="City"><Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <div className="col-span-2"><Labeled label="Association / School"><Input value={form.association} onChange={(e) => setForm({ ...form, association: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
          </div>
          <div className="border-t border-zinc-800 pt-4">
            <Overline className="mb-3">Availability &amp; Scheduling Rules</Overline>
            <div className="grid grid-cols-2 gap-4">
              <Labeled label="Playable From"><Input data-testid="team-available-from" type="time" value={form.available_from} onChange={(e) => setForm({ ...form, available_from: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Playable Until"><Input data-testid="team-available-to" type="time" value={form.available_to} onChange={(e) => setForm({ ...form, available_to: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            </div>
            <div className="mt-4">
              <Labeled label="No back-to-back matches">
                <Button type="button" data-testid="team-no-b2b-toggle" onClick={() => setForm({ ...form, no_back_to_back: !form.no_back_to_back })}
                  className={`rounded-none w-full gap-2 ${form.no_back_to_back ? "bg-lime-400 text-black hover:bg-lime-500" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}>
                  <Ban className="w-4 h-4" />{form.no_back_to_back ? "Enabled — needs a break between matches" : "Off — may play consecutive slots"}
                </Button>
              </Labeled>
            </div>
            <p className="text-xs text-zinc-600 mt-3">Leave times blank for no restriction. The scheduler will keep this team inside its playable window and, if enabled, avoid consecutive matches.</p>
            <div className="grid grid-cols-2 gap-4 mt-4">
              <Labeled label="Day Preference">
                <Select value={form.day_preference} onValueChange={(v) => setForm({ ...form, day_preference: v })}>
                  <SelectTrigger data-testid="team-day-pref" className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none">
                    <SelectItem value="any">Any day</SelectItem>
                    <SelectItem value="weekday">Weekdays only</SelectItem>
                    <SelectItem value="weekend">Weekends only</SelectItem>
                  </SelectContent>
                </Select>
              </Labeled>
              <Labeled label="Max Matches / Day"><Input data-testid="team-max-per-day" type="number" value={form.max_matches_per_day} onChange={(e) => setForm({ ...form, max_matches_per_day: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            </div>
            <div className="mt-4"><Labeled label="Unavailable Dates (comma-separated, YYYY-MM-DD)"><Input data-testid="team-unavailable-dates" value={form.unavailable_dates} onChange={(e) => setForm({ ...form, unavailable_dates: e.target.value })} placeholder="2026-07-04, 2026-07-05" className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
          </div>
          <DialogFooter><Button data-testid="save-team-btn" onClick={save} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider w-full">{edit ? "Save Changes" : "Add Team"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
