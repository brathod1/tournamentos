import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Overline, Stat, Labeled } from "../components/bits";
import { Trophy, ChevronLeft, MapPin, Calendar, Pencil } from "lucide-react";
import { toast } from "sonner";
import CategoriesTab from "../components/tabs/CategoriesTab";
import TeamsTab from "../components/tabs/TeamsTab";
import VenuesTab from "../components/tabs/VenuesTab";
import FixturesTab from "../components/tabs/FixturesTab";
import ScheduleTab from "../components/tabs/ScheduleTab";
import StandingsTab from "../components/tabs/StandingsTab";
import ReportsTab from "../components/tabs/ReportsTab";
import BoardTab from "../components/tabs/BoardTab";

const TABS = ["overview", "categories", "teams", "venues", "fixtures", "schedule", "board", "standings", "reports"];
const LABELS = { overview: "Overview", categories: "Categories", teams: "Teams", venues: "Grounds & Referees", fixtures: "Fixtures", schedule: "Schedule", board: "Board", standings: "Standings", reports: "Reports" };

export function CategoryPicker({ categories, value, onChange }) {
  return (
    <Select value={value || ""} onValueChange={onChange}>
      <SelectTrigger data-testid="category-picker" className="w-64 rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400">
        <SelectValue placeholder="Select category" />
      </SelectTrigger>
      <SelectContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none">
        {categories.map((c) => <SelectItem key={c.id} value={c.id} data-testid={`cat-opt-${c.id}`}>{c.name}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export default function TournamentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [tour, setTour] = useState(null);
  const [categories, setCategories] = useState([]);
  const [tab, setTab] = useState("overview");
  const [activeCat, setActiveCat] = useState(null);
  const [editOpen, setEditOpen] = useState(false);
  const [ef, setEf] = useState({ name: "", location: "", start_date: "", end_date: "" });

  const openEdit = () => { setEf({ name: tour.name || "", location: tour.location || "", start_date: tour.start_date || "", end_date: tour.end_date || "" }); setEditOpen(true); };
  const saveEdit = async () => {
    if (!ef.name.trim()) return toast.error("Name is required");
    if (!ef.start_date) return toast.error("Start date is required");
    const payload = { ...ef, end_date: ef.end_date || ef.start_date };
    const updated = await api.updateTournament(id, payload);
    setTour(updated); setEditOpen(false); toast.success("Tournament updated");
  };

  const loadCats = useCallback(() => api.listCategories(id).then((cs) => {
    setCategories(cs);
    setActiveCat((prev) => prev && cs.find((c) => c.id === prev) ? prev : (cs[0]?.id || null));
  }), [id]);

  useEffect(() => { api.getTournament(id).then(setTour); loadCats(); }, [id, loadCats]);

  if (!tour) return <div className="p-10 text-zinc-500">Loading…</div>;
  const totalTeams = categories.reduce((s, c) => s + (c.team_count || 0), 0);
  const totalMatches = categories.reduce((s, c) => s + (c.match_count || 0), 0);

  return (
    <div className="relative z-10">
      <header className="border-b border-zinc-800 bg-zinc-900/50 sticky top-0 z-30 backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <button data-testid="back-btn" onClick={() => nav("/")} className="text-zinc-500 hover:text-lime-400 transition-colors"><ChevronLeft className="w-5 h-5" /></button>
          <div className="w-8 h-8 bg-lime-400 flex items-center justify-center"><Trophy className="w-5 h-5 text-black" /></div>
          <div className="flex-1 min-w-0">
            <h1 className="font-display text-xl font-bold uppercase tracking-tight truncate leading-none">{tour.name}</h1>
            <div className="flex items-center gap-4 mt-1 text-xs text-zinc-500">
              <span>{tour.sport}</span>
              {tour.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{tour.location}</span>}
              {tour.start_date ? <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{tour.start_date}{tour.end_date && tour.end_date !== tour.start_date ? ` → ${tour.end_date}` : ""}</span>
                : <span className="flex items-center gap-1 text-amber-400"><Calendar className="w-3 h-3" />No dates set</span>}
            </div>
          </div>
          <Button data-testid="edit-tournament-btn" onClick={openEdit} variant="ghost" className="rounded-none text-zinc-400 hover:text-lime-400 hover:bg-zinc-800 gap-2 h-9 text-xs uppercase tracking-wider shrink-0"><Pencil className="w-4 h-4" />Edit</Button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-transparent border border-zinc-800 rounded-none p-0 h-auto flex-wrap justify-start w-full mb-8">
            {TABS.map((t) => (
              <TabsTrigger key={t} value={t} data-testid={`tab-${t}`}
                className="rounded-none data-[state=active]:bg-lime-400 data-[state=active]:text-black text-zinc-400 uppercase tracking-wider text-xs font-semibold px-5 py-3 border-r border-zinc-800">
                {LABELS[t]}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="overview">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <Stat label="Categories" value={categories.length} accent />
              <Stat label="Teams" value={totalTeams} />
              <Stat label="Matches" value={totalMatches} />
              <Stat label="Status" value={tour.status} />
            </div>
            {tour.description && <div className="border border-zinc-800 bg-zinc-900/50 p-6"><Overline className="mb-2">About</Overline><p className="text-zinc-300 leading-relaxed">{tour.description}</p></div>}
            <div className="mt-8"><Overline className="mb-4">Categories</Overline>
              {categories.length === 0 ? <p className="text-zinc-500 text-sm">No categories yet. Open the Categories tab to add one.</p> :
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {categories.map((c) => <div key={c.id} className="border border-zinc-800 bg-zinc-900/50 p-5"><div className="font-display text-lg uppercase">{c.name}</div><div className="text-xs text-zinc-500 mt-1">{c.team_count} teams · {c.match_count} matches</div></div>)}
                </div>}
            </div>
          </TabsContent>

          <TabsContent value="categories"><CategoriesTab tid={id} tour={tour} categories={categories} reload={loadCats} /></TabsContent>
          <TabsContent value="teams"><TeamsTab categories={categories} activeCat={activeCat} setActiveCat={setActiveCat} reload={loadCats} /></TabsContent>
          <TabsContent value="venues"><VenuesTab tid={id} /></TabsContent>
          <TabsContent value="fixtures"><FixturesTab tid={id} categories={categories} activeCat={activeCat} setActiveCat={setActiveCat} reload={loadCats} /></TabsContent>
          <TabsContent value="schedule"><ScheduleTab tid={id} categories={categories} activeCat={activeCat} setActiveCat={setActiveCat} /></TabsContent>
          <TabsContent value="board"><BoardTab tid={id} categories={categories} /></TabsContent>
          <TabsContent value="standings"><StandingsTab categories={categories} activeCat={activeCat} setActiveCat={setActiveCat} /></TabsContent>
          <TabsContent value="reports"><ReportsTab tid={id} categories={categories} /></TabsContent>
        </Tabs>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none max-w-lg">
          <DialogHeader><DialogTitle className="font-display text-2xl uppercase tracking-tight">Edit Tournament</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-2">
            <div className="col-span-2"><Labeled label="Name"><Input data-testid="edit-name-input" value={ef.name} onChange={(e) => setEf({ ...ef, name: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
            <div className="col-span-2"><Labeled label="Location"><Input value={ef.location} onChange={(e) => setEf({ ...ef, location: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
            <Labeled label="Start Date"><Input data-testid="edit-start-date" type="date" value={ef.start_date} onChange={(e) => setEf({ ...ef, start_date: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <Labeled label="End Date (optional — 1-day)"><Input data-testid="edit-end-date" type="date" value={ef.end_date} onChange={(e) => setEf({ ...ef, end_date: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            <div className="col-span-2 -mt-2"><p className="text-xs text-zinc-600">Single-day tournament? Set the start date and leave the end date empty.</p></div>
          </div>
          <DialogFooter><Button data-testid="save-tournament-edit-btn" onClick={saveEdit} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider w-full">Save Changes</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
