import React, { useEffect, useState, useCallback, useRef, useLayoutEffect } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from "../ui/alert-dialog";
import { SectionTitle, Empty, Overline } from "../bits";
import { CategoryPicker } from "../../pages/TournamentDetail";
import { CalendarDays, Zap, Lock, LockOpen, Trophy } from "lucide-react";
import { toast } from "sonner";

export default function FixturesTab({ tid, categories, activeCat, setActiveCat, reload }) {
  const [matches, setMatches] = useState([]);
  const [teams, setTeams] = useState([]);
  const [grounds, setGrounds] = useState([]);
  const cat = categories.find((c) => c.id === activeCat);

  const load = useCallback(() => {
    if (!activeCat) return;
    api.listMatches(activeCat).then(setMatches);
    api.listTeams(activeCat).then(setTeams);
    api.listGrounds(tid).then(setGrounds);
  }, [activeCat, tid]);
  useEffect(() => { load(); }, [load]);

  const tname = (id) => teams.find((t) => t.id === id)?.name || (id ? "?" : "BYE");
  const gname = (id) => grounds.find((g) => g.id === id)?.name;

  const generate = async () => {
    try { const r = await api.generateFixtures(activeCat); toast.success(`${r.generated} fixtures generated`); load(); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to generate"); }
  };

  const setScore = async (m, h, a) => {
    await api.updateMatch(m.id, { home_score: h, away_score: a, status: h != null && a != null ? "completed" : "scheduled" });
    load();
  };
  const toggleLock = async (m) => { await api.updateMatch(m.id, { locked: !m.locked }); load(); };

  if (categories.length === 0) return <Empty icon={CalendarDays} title="No categories yet" hint="Create a category and add teams to generate fixtures." />;

  const isKO = cat?.format === "knockout";
  const isGK = cat?.format === "groups_knockout";
  const koMatches = matches.filter((m) => m.stage === "knockout");
  const stageMatches = matches.filter((m) => m.stage !== "knockout");
  const grouped = stageMatches.reduce((acc, m) => { const k = m.group || `Round ${m.round}`; (acc[k] = acc[k] || []).push(m); return acc; }, {});
  const seed = async () => {
    try { const r = await api.seedKnockout(activeCat); toast.success(`Knockout seeded from group standings (${r.qualifiers} qualifiers)`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Seeding failed"); }
  };

  return (
    <div>
      <SectionTitle sub={cat ? cat.name : "Select a category"} title="Fixtures" right={
        <div className="flex gap-3 items-center">
          <CategoryPicker categories={categories} value={activeCat} onChange={setActiveCat} />
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button data-testid="generate-fixtures-btn" disabled={!activeCat} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2"><Zap className="w-4 h-4" />Generate</Button>
            </AlertDialogTrigger>
            <AlertDialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none">
              <AlertDialogHeader><AlertDialogTitle className="font-display uppercase">Generate Fixtures?</AlertDialogTitle>
                <AlertDialogDescription className="text-zinc-400">This regenerates all unlocked fixtures for <b className="text-zinc-200">{cat?.name}</b> using the <b className="text-zinc-200">{cat?.format}</b> format. Locked matches are preserved. Existing results on unlocked matches will be cleared.</AlertDialogDescription></AlertDialogHeader>
              <AlertDialogFooter><AlertDialogCancel className="rounded-none bg-zinc-800 border-zinc-700 hover:bg-zinc-700">Cancel</AlertDialogCancel><AlertDialogAction data-testid="confirm-generate-btn" onClick={generate} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase">Generate</AlertDialogAction></AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>} />

      {matches.length === 0 ? (
        <Empty icon={CalendarDays} title="No fixtures generated" hint={teams.length < 2 ? "Add at least 2 teams to this category first." : "Click Generate to build the fixture list from your chosen format."} />
      ) : isKO ? (
        <Bracket matches={matches} tname={tname} setScore={setScore} />
      ) : (
        <div className="space-y-10">
          <div className="space-y-8">
            {Object.entries(grouped).map(([g, ms]) => (
              <div key={g}>
                <Overline className="mb-3 text-lime-400 flex items-center gap-2">{g.startsWith("Group") ? <Trophy className="w-3.5 h-3.5" /> : null}{g}</Overline>
                <div className="border border-zinc-800 divide-y divide-zinc-800">
                  {ms.map((m) => <MatchRow key={m.id} m={m} tname={tname} gname={gname} setScore={setScore} toggleLock={toggleLock} />)}
                </div>
              </div>
            ))}
          </div>
          {isGK && koMatches.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                <Overline className="text-lime-400 flex items-center gap-2"><Trophy className="w-3.5 h-3.5" />Knockout Stage</Overline>
                <Button data-testid="seed-knockout-btn" onClick={seed} className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2 h-8 text-xs"><Zap className="w-3.5 h-3.5" />Seed from Group Standings</Button>
              </div>
              <Bracket matches={koMatches} tname={tname} setScore={setScore} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MatchRow({ m, tname, gname, setScore, toggleLock, ko }) {
  const bye = m.status === "bye" || !m.away_id || !m.home_id;
  const [home, setHome] = useState(m.home_score ?? "");
  const [away, setAway] = useState(m.away_score ?? "");
  useEffect(() => { setHome(m.home_score ?? ""); setAway(m.away_score ?? ""); }, [m.home_score, m.away_score]);
  const commit = () => {
    const h = home === "" ? null : Number(home);
    const a = away === "" ? null : Number(away);
    if (h === (m.home_score ?? null) && a === (m.away_score ?? null)) return;
    setScore(m, h, a);
  };
  return (
    <div data-testid={`match-row-${m.id}`} className="grid grid-cols-12 gap-2 px-4 py-3 items-center hover:bg-zinc-900/40 transition-colors">
      <div className="col-span-5 text-right font-semibold truncate">{tname(m.home_id)}</div>
      <div className="col-span-2 flex items-center justify-center gap-1">
        {bye ? <span className="text-xs text-zinc-600 uppercase tracking-widest">Bye</span> : (<>
          <Input data-testid={`home-score-${m.id}`} value={home} onChange={(e) => setHome(e.target.value)} onBlur={commit}
            className="w-11 h-9 text-center rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400 p-0" />
          <span className="text-zinc-600">:</span>
          <Input data-testid={`away-score-${m.id}`} value={away} onChange={(e) => setAway(e.target.value)} onBlur={commit}
            className="w-11 h-9 text-center rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400 p-0" />
        </>)}
      </div>
      <div className="col-span-3 font-semibold truncate">{tname(m.away_id)}</div>
      <div className="col-span-2 flex items-center justify-end gap-3 text-xs text-zinc-500">
        {m.date && <span className="hidden lg:inline">{m.date} {m.time}</span>}
        {m.ground_id && gname(m.ground_id) && <span className="hidden xl:inline text-zinc-600">{gname(m.ground_id)}</span>}
        {!bye && <button data-testid={`lock-match-${m.id}`} onClick={() => toggleLock(m)} className={m.locked ? "text-lime-400" : "text-zinc-600 hover:text-zinc-300"}>{m.locked ? <Lock className="w-4 h-4" /> : <LockOpen className="w-4 h-4" />}</button>}
      </div>
    </div>
  );
}


function Bracket({ matches, tname, setScore }) {
  const containerRef = useRef(null);
  const refs = useRef({});
  const [lines, setLines] = useState([]);
  const rounds = {};
  matches.forEach((m) => { (rounds[m.round] = rounds[m.round] || []).push(m); });
  const nums = Object.keys(rounds).map(Number).sort((a, b) => a - b);

  useLayoutEffect(() => {
    const compute = () => {
      const cont = containerRef.current; if (!cont) return;
      const cb = cont.getBoundingClientRect();
      const ls = [];
      matches.forEach((m) => {
        if (!m.next_match_id) return;
        const a = refs.current[m.id]; const b = refs.current[m.next_match_id];
        if (!a || !b) return;
        const ar = a.getBoundingClientRect(); const br = b.getBoundingClientRect();
        const x1 = ar.right - cb.left; const y1 = ar.top - cb.top + ar.height / 2;
        const x2 = br.left - cb.left; const y2 = br.top - cb.top + br.height / 2;
        const mid = (x1 + x2) / 2;
        ls.push(`M ${x1} ${y1} H ${mid} V ${y2} H ${x2}`);
      });
      setLines(ls);
    };
    const t1 = setTimeout(compute, 60);
    const t2 = setTimeout(compute, 300);
    window.addEventListener("resize", compute);
    return () => { clearTimeout(t1); clearTimeout(t2); window.removeEventListener("resize", compute); };
  }, [matches]);

  return (
    <div ref={containerRef} className="relative flex gap-16 overflow-x-auto pb-4 items-stretch" data-testid="knockout-bracket">
      <svg className="absolute inset-0 w-full h-full pointer-events-none overflow-visible" style={{ zIndex: 0 }}>
        {lines.map((d, i) => <path key={i} d={d} stroke="#71717a" strokeWidth="1.5" fill="none" />)}
      </svg>
      {nums.map((r) => (
        <div key={r} className="relative flex flex-col min-w-[236px]" style={{ zIndex: 1 }}>
          <Overline className="text-lime-400 mb-4">{rounds[r][0].label || `Round ${r}`}</Overline>
          <div className="flex flex-col justify-around flex-1 gap-6">
            {rounds[r].slice().sort((a, b) => (a.bracket_pos ?? 0) - (b.bracket_pos ?? 0)).map((m) => (
              <div key={m.id} ref={(el) => { refs.current[m.id] = el; }}>
                <BracketMatch m={m} tname={tname} setScore={setScore} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

const ORD = { 1: "1st", 2: "2nd", 3: "3rd" };
function srcLabel(s) { return s ? `${ORD[s.pos] || `${s.pos}th`} · ${s.group}` : "TBD"; }

function BracketMatch({ m, tname, setScore }) {
  const bye = m.status === "bye";
  const [home, setHome] = useState(m.home_score ?? "");
  const [away, setAway] = useState(m.away_score ?? "");
  useEffect(() => { setHome(m.home_score ?? ""); setAway(m.away_score ?? ""); }, [m.home_score, m.away_score]);
  const commit = () => {
    const h = home === "" ? null : Number(home);
    const a = away === "" ? null : Number(away);
    if (h === (m.home_score ?? null) && a === (m.away_score ?? null)) return;
    setScore(m, h, a);
  };
  const decided = m.home_score != null && m.away_score != null;
  const hw = decided && m.home_score > m.away_score;
  const aw = decided && m.away_score > m.home_score;
  const Side = ({ id, source, winner, val, onCh, isBye }) => (
    <div className={`flex items-center justify-between px-3 py-2.5 gap-2 ${winner ? "text-lime-400 font-bold" : id ? "text-zinc-200" : "text-zinc-600"}`}>
      <span className="truncate text-sm">{id ? tname(id) : (isBye ? "BYE" : srcLabel(source))}</span>
      {!bye && id && (
        <input value={val} onChange={onCh} onBlur={commit}
          className="w-9 h-7 text-center bg-zinc-950 border border-zinc-800 focus:border-lime-400 outline-none text-sm text-zinc-100" />
      )}
    </div>
  );
  return (
    <div data-testid={`bracket-match-${m.id}`} className="border border-zinc-800 bg-zinc-900 divide-y divide-zinc-800 hover:border-lime-400/40 transition-colors">
      <Side id={m.home_id} source={m.home_source} winner={hw} val={home} onCh={(e) => setHome(e.target.value)} />
      <Side id={m.away_id} source={m.away_source} winner={aw} val={away} onCh={(e) => setAway(e.target.value)} isBye={bye} />
    </div>
  );
}
