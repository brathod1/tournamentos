import React, { useEffect, useState, useCallback } from "react";
import { api, TIEBREAKERS } from "../../lib/api";
import { SectionTitle, Empty, Overline } from "../bits";
import { CategoryPicker } from "../../pages/TournamentDetail";
import { BarChart3 } from "lucide-react";

export default function StandingsTab({ categories, activeCat, setActiveCat }) {
  const [data, setData] = useState(null);
  const [cat, setCat] = useState(null);

  const load = useCallback(() => {
    if (!activeCat) return;
    api.standings(activeCat).then(setData).catch(() => setData(null));
    api.getCategory(activeCat).then(setCat);
  }, [activeCat]);
  useEffect(() => { load(); }, [load]);

  if (categories.length === 0) return <Empty icon={BarChart3} title="No categories" hint="Create a category to view standings." />;

  const tbs = (cat?.points_config?.tiebreakers || []).map((t) => TIEBREAKERS.find((x) => x.value === t)?.label).filter(Boolean);

  return (
    <div>
      <SectionTitle sub="Live table" title="Standings" right={<CategoryPicker categories={categories} value={activeCat} onChange={setActiveCat} />} />
      {cat && <div className="mb-6 text-xs text-zinc-500 flex flex-wrap gap-4">
        <span>Win <b className="text-lime-400">{cat.points_config?.win}</b></span>
        <span>Draw <b className="text-lime-400">{cat.points_config?.draw}</b></span>
        <span>Loss <b className="text-lime-400">{cat.points_config?.loss}</b></span>
        {tbs.length > 0 && <span>Tiebreakers: {tbs.join(" → ")}</span>}
      </div>}
      {!data ? <Empty icon={BarChart3} title="No data" /> :
        data.grouped ? (
          <div className="space-y-8">{Object.entries(data.standings).map(([g, rows]) => (
            <div key={g}><Overline className="mb-3 text-lime-400">{g}</Overline><Table rows={rows} /></div>
          ))}</div>
        ) : <Table rows={data.standings} />}
    </div>
  );
}

function Table({ rows }) {
  if (!rows || rows.length === 0) return <Empty icon={BarChart3} title="No teams" hint="Add teams and record results to populate the table." />;
  const cols = [["P", "played"], ["W", "won"], ["D", "drawn"], ["L", "lost"], ["GF", "gf"], ["GA", "ga"], ["GD", "gd"]];
  return (
    <div className="border border-zinc-800 overflow-x-auto">
      <div className="grid grid-cols-[40px_1fr_repeat(7,44px)_60px] gap-0 px-4 py-3 border-b border-zinc-800 text-[10px] uppercase tracking-widest text-zinc-500 bg-zinc-900/50 min-w-[560px]">
        <div>#</div><div>Team</div>{cols.map(([l]) => <div key={l} className="text-center">{l}</div>)}<div className="text-center text-lime-400">Pts</div>
      </div>
      {rows.map((r) => (
        <div key={r.team_id} data-testid={`standing-row-${r.team_id}`} className="grid grid-cols-[40px_1fr_repeat(7,44px)_60px] gap-0 px-4 py-3 border-b border-zinc-800/60 items-center hover:bg-zinc-900/40 transition-colors min-w-[560px]">
          <div className="font-display text-lg text-zinc-500">{r.rank}</div>
          <div className="font-semibold truncate pr-2">{r.team_name}</div>
          {cols.map(([l, k]) => <div key={l} className="text-center text-sm text-zinc-400">{r[k]}</div>)}
          <div className="text-center font-display text-xl font-bold text-lime-400">{r.points}</div>
        </div>
      ))}
    </div>
  );
}
