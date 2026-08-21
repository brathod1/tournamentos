import React, { useState } from "react";
import { api, FORMATS, TIEBREAKERS } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "../ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../ui/dialog";
import { SectionTitle, Empty, Labeled, Overline } from "../bits";
import { Layers, Plus, Trash2, Settings2 } from "lucide-react";
import { toast } from "sonner";

const blank = { name: "", format: "league_single", seeded: false, num_groups: 2, qualifiers_per_group: 2, age_restriction: "", custom_rules: "",
  points_config: { win: 3, draw: 1, loss: 0, tiebreakers: ["points", "goal_difference", "goals_for", "wins"] } };

export default function CategoriesTab({ tid, categories, reload }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState(blank);

  const openNew = () => { setEdit(null); setForm(blank); setOpen(true); };
  const openEdit = (c) => { setEdit(c); setForm({ ...blank, ...c, points_config: { ...blank.points_config, ...(c.points_config || {}) } }); setOpen(true); };

  const save = async () => {
    if (!form.name.trim()) return toast.error("Category name required");
    const payload = { ...form, num_groups: Number(form.num_groups), qualifiers_per_group: Number(form.qualifiers_per_group),
      points_config: { ...form.points_config, win: Number(form.points_config.win), draw: Number(form.points_config.draw), loss: Number(form.points_config.loss) } };
    if (edit) { await api.updateCategory(edit.id, payload); toast.success("Category updated"); }
    else { await api.createCategory(tid, payload); toast.success("Category created"); }
    setOpen(false); reload();
  };
  const remove = async (id) => { await api.deleteCategory(id); toast.success("Category deleted"); reload(); };

  const setPC = (k) => (e) => setForm((f) => ({ ...f, points_config: { ...f.points_config, [k]: e.target.value } }));
  const toggleTB = (v) => setForm((f) => {
    const has = f.points_config.tiebreakers.includes(v);
    const tb = has ? f.points_config.tiebreakers.filter((x) => x !== v) : [...f.points_config.tiebreakers, v];
    return { ...f, points_config: { ...f.points_config, tiebreakers: tb } };
  });

  return (
    <div>
      <SectionTitle sub="Independent competitions" title="Categories" right={
        <Button data-testid="add-category-btn" onClick={openNew} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2"><Plus className="w-4 h-4" />Add Category</Button>} />
      {categories.length === 0 ? (
        <Empty icon={Layers} title="No categories" hint="Every category is fully independent — its own format, points system, teams and scheduling rules." action={<Button onClick={openNew} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider">Add Category</Button>} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {categories.map((c) => (
            <div key={c.id} data-testid={`category-card-${c.id}`} className="border border-zinc-800 bg-zinc-900/50 p-6 group hover:border-lime-400/40 transition-colors">
              <div className="flex items-start justify-between">
                <h3 className="font-display text-2xl uppercase tracking-tight leading-none">{c.name}</h3>
                <div className="flex gap-2">
                  <button data-testid={`edit-category-${c.id}`} onClick={() => openEdit(c)} className="text-zinc-600 hover:text-lime-400"><Settings2 className="w-4 h-4" /></button>
                  <button data-testid={`delete-category-${c.id}`} onClick={() => remove(c.id)} className="text-zinc-600 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              <span className="inline-block mt-3 text-[10px] uppercase tracking-widest px-2 py-1 bg-zinc-800 text-lime-400">{FORMATS.find((f) => f.value === c.format)?.label || c.format}</span>
              <div className="flex gap-4 mt-4 text-sm text-zinc-400">
                <span>{c.team_count} teams</span><span>{c.match_count} matches</span>
                <span>{c.points_config?.win}/{c.points_config?.draw}/{c.points_config?.loss} pts</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display text-2xl uppercase tracking-tight">{edit ? "Edit" : "New"} Category</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-2">
            <div className="col-span-2"><Labeled label="Name"><Input data-testid="category-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Under-16 Boys" className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
            <div className="col-span-2"><Labeled label="Competition Format">
              <Select value={form.format} onValueChange={(v) => setForm({ ...form, format: v })}>
                <SelectTrigger data-testid="format-select" className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none">{FORMATS.map((f) => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}</SelectContent>
              </Select></Labeled></div>
            {form.format === "groups_knockout" && (<>
              <Labeled label="Number of Groups"><Input type="number" min="1" value={form.num_groups} onChange={(e) => setForm({ ...form, num_groups: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Qualifiers / Group"><Input type="number" min="1" value={form.qualifiers_per_group} onChange={(e) => setForm({ ...form, qualifiers_per_group: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            </>)}
            {(form.format === "knockout" || form.format === "groups_knockout") && (
              <Labeled label="Seeding"><Select value={form.seeded ? "yes" : "no"} onValueChange={(v) => setForm({ ...form, seeded: v === "yes" })}>
                <SelectTrigger className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none"><SelectItem value="no">Random Draw</SelectItem><SelectItem value="yes">Seeded</SelectItem></SelectContent>
              </Select></Labeled>)}
            <Labeled label="Age Restriction"><Input value={form.age_restriction} onChange={(e) => setForm({ ...form, age_restriction: e.target.value })} placeholder="e.g. U-16" className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
          </div>

          <div className="border-t border-zinc-800 pt-4">
            <Overline className="mb-3">Points System</Overline>
            <div className="grid grid-cols-3 gap-4">
              <Labeled label="Win"><Input data-testid="points-win" type="number" value={form.points_config.win} onChange={setPC("win")} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Draw"><Input type="number" value={form.points_config.draw} onChange={setPC("draw")} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="Loss"><Input type="number" value={form.points_config.loss} onChange={setPC("loss")} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            </div>
            <Overline className="mb-3 mt-5">Tiebreaker Order <span className="text-zinc-600 normal-case tracking-normal">(click to toggle · order matters)</span></Overline>
            <div className="flex flex-wrap gap-2">
              {form.points_config.tiebreakers.map((tb, i) => <span key={tb} className="text-xs px-2 py-1 bg-lime-400 text-black font-semibold">{i + 1}. {TIEBREAKERS.find((t) => t.value === tb)?.label}</span>)}
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              {TIEBREAKERS.map((t) => <button key={t.value} data-testid={`tb-${t.value}`} onClick={() => toggleTB(t.value)} className={`text-xs px-2 py-1 border transition-colors ${form.points_config.tiebreakers.includes(t.value) ? "border-lime-400/50 text-lime-400" : "border-zinc-700 text-zinc-500 hover:border-zinc-500"}`}>{t.label}</button>)}
            </div>
          </div>

          <div><Labeled label="Custom Rules"><Textarea value={form.custom_rules} onChange={(e) => setForm({ ...form, custom_rules: e.target.value })} className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled></div>
          <DialogFooter><Button data-testid="save-category-btn" onClick={save} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider w-full">{edit ? "Save Changes" : "Create Category"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
