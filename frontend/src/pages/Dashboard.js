import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Overline, Empty, Labeled, ConfirmDelete } from "../components/bits";
import { CanEdit } from "../lib/auth";
import AccountMenu from "../components/AccountMenu";
import { Trophy, Plus, MapPin, Users, Layers, Calendar, ArrowRight, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function Dashboard() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", sport: "Football", location: "", organizer: "", start_date: "", end_date: "", description: "" });

  const load = () => api.listTournaments().then(setItems);
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name.trim()) return toast.error("Tournament name is required");
    const payload = { ...form, end_date: form.end_date || form.start_date };
    await api.createTournament(payload);
    toast.success("Tournament created");
    setOpen(false);
    setForm({ name: "", sport: "Football", location: "", organizer: "", start_date: "", end_date: "", description: "" });
    load();
  };

  const remove = async (id) => {
    await api.deleteTournament(id);
    toast.success("Tournament deleted");
    load();
  };

  return (
    <div className="relative z-10 max-w-7xl mx-auto px-6 py-10">
      <header className="flex items-center justify-between mb-12">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-lime-400 flex items-center justify-center">
            <Trophy className="w-6 h-6 text-black" strokeWidth={2.2} />
          </div>
          <div>
            <div className="font-display text-2xl font-bold uppercase tracking-tight leading-none">Tournament<span className="text-lime-400">OS</span></div>
            <Overline className="mt-1">Operating System for Sport</Overline>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <AccountMenu />
          <CanEdit><NewTournamentDialog open={open} setOpen={setOpen} form={form} setForm={setForm} create={create} /></CanEdit>
        </div>
      </header>

      <div className="relative overflow-hidden border border-zinc-800 mb-12">
        <img src="https://images.unsplash.com/photo-1676746424139-77f8bd8922a8" alt="stadium" className="absolute inset-0 w-full h-full object-cover opacity-25" />
        <div className="absolute inset-0 bg-gradient-to-r from-zinc-950 via-zinc-950/80 to-zinc-950/30" />
        <div className="relative p-10 sm:p-16 max-w-2xl">
          <Overline className="mb-4 text-lime-400">Plan · Schedule · Compete</Overline>
          <h1 className="font-display text-5xl sm:text-6xl font-black uppercase tracking-tighter leading-[0.9]">Run any tournament,<br />from kickoff to <span className="text-lime-400">crown</span></h1>
          <p className="text-zinc-400 mt-5 max-w-lg leading-relaxed">Fully configurable formats, a conflict-aware scheduling engine, and standings that follow your rules — not ours.</p>
        </div>
      </div>

      <div className="flex items-center justify-between mb-6">
        <Overline>Your Tournaments · {items.length}</Overline>
      </div>

      {items.length === 0 ? (
        <Empty icon={Trophy} title="No tournaments yet" hint="Create your first tournament to start setting up categories, teams, grounds and the scheduling engine." action={<Button data-testid="empty-create-tournament-btn" onClick={() => setOpen(true)} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider">Create Tournament</Button>} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((t) => (
            <div key={t.id} data-testid={`tournament-card-${t.id}`} onClick={() => nav(`/t/${t.id}`)}
              className="group border border-zinc-800 bg-zinc-900/50 p-6 cursor-pointer transition-[transform,border-color] duration-200 hover:-translate-y-1 hover:border-lime-400/50">
              <div className="flex items-start justify-between">
                <span className="text-[10px] uppercase tracking-[0.2em] px-2 py-1 bg-zinc-800 text-lime-400">{t.sport}</span>
                <CanEdit>
                  <span onClick={(e) => e.stopPropagation()}>
                    <ConfirmDelete title="Delete tournament?" testId={`confirm-delete-tournament-${t.id}`}
                      description={`This permanently deletes "${t.name}" and every category, team, ground, referee and match inside it. This cannot be undone.`}
                      onConfirm={() => remove(t.id)}>
                      <button data-testid={`delete-tournament-${t.id}`} className="text-zinc-600 hover:text-red-500 transition-colors"><Trash2 className="w-4 h-4" /></button>
                    </ConfirmDelete>
                  </span>
                </CanEdit>
              </div>
              <h3 className="font-display text-2xl font-bold uppercase tracking-tight mt-4 leading-tight group-hover:text-lime-400 transition-colors">{t.name}</h3>
              {t.location && <div className="flex items-center gap-1.5 text-sm text-zinc-500 mt-2"><MapPin className="w-3.5 h-3.5" />{t.location}</div>}
              <div className="flex items-center gap-5 mt-6 text-sm text-zinc-400">
                <span className="flex items-center gap-1.5"><Layers className="w-4 h-4 text-zinc-600" />{t.category_count} cat</span>
                <span className="flex items-center gap-1.5"><Users className="w-4 h-4 text-zinc-600" />{t.team_count} teams</span>
                {t.start_date && <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4 text-zinc-600" />{t.start_date}</span>}
              </div>
              <div className="flex items-center gap-1 text-lime-400 text-xs uppercase tracking-widest mt-6 opacity-0 group-hover:opacity-100 transition-opacity">Open <ArrowRight className="w-3.5 h-3.5" /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function NewTournamentDialog({ open, setOpen, form, setForm, create }) {
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button data-testid="create-tournament-btn" className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2"><Plus className="w-4 h-4" />New Tournament</Button>
      </DialogTrigger>
      <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none max-w-lg">
        <DialogHeader><DialogTitle className="font-display text-2xl uppercase tracking-tight">Create Tournament</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-4 py-2">
          <div className="col-span-2"><Labeled label="Name"><Input data-testid="tournament-name-input" value={form.name} onChange={set("name")} placeholder="City Cup 2026" className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
          <Labeled label="Sport"><Input value={form.sport} onChange={set("sport")} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
          <Labeled label="Location"><Input value={form.location} onChange={set("location")} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
          <Labeled label="Organizer"><Input value={form.organizer} onChange={set("organizer")} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
          <div />
          <Labeled label="Start Date"><Input type="date" value={form.start_date} onChange={set("start_date")} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
          <Labeled label="End Date (optional — 1-day)"><Input type="date" value={form.end_date} onChange={set("end_date")} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
          <div className="col-span-2 -mt-2"><p className="text-xs text-zinc-600">Running a single-day tournament? Just set the start date and leave the end date empty — everything will be scheduled on that one day.</p></div>
          <div className="col-span-2"><Labeled label="Description"><Textarea value={form.description} onChange={set("description")} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
        </div>
        <DialogFooter>
          <Button data-testid="submit-tournament-btn" onClick={create} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider w-full">Create</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
