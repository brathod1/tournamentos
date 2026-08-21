# TournamentOS — Full-System QA, Stress Test & Review

**Date:** 2026-08-21 · **Backend:** localhost:8001 · **Frontend:** localhost:4000 · **DB:** local MongoDB
**Method:** full source review of backend + frontend, followed by a 129-check automated QA harness
(`qa_test.py` / `qa_test2.py`, results in `qa_results.json`) executed against the live backend, plus the
repo's own pytest suite. The harness built the real **TournamentOS Grand Championship 2026**
(2026-09-05→06, 5 grounds, 10 referees, 4 categories, 42 teams, 92 fixtures, hard constraints) — it is
still in the app for manual inspection. Live browser drag-and-drop was not executable in this session;
Board findings below are from code analysis and are marked as such.

---

## A. Executive Summary

**Verdict: READY WITH MINOR FIXES** — for a supervised organizer who understands the limits.
**NOT READY** as-is for an unattended, production, multi-organizer deployment.

The core promise of the product holds up under real testing. Fixture generation is correct in all four
formats (exact counts, no duplicates, correct brackets, correct group allocation). The scheduling
engine is genuinely conflict-aware: across 129 automated checks it never produced an invalid
schedule — no ground double-bookings, no team overlaps, no rest/window/break/date violations, locked
matches were honored twice through re-runs, knockout rounds always followed their feeders, and when
the tournament was deliberately over-constrained it degraded gracefully with named reasons and useful
suggestions instead of silently emitting garbage. Standings and every tiebreaker tested matched an
independent recomputation. It's fast: 0.13 s to place 61 matches across 4 categories.

What keeps it from full production readiness is robustness around the edges, not the engine:
`PUT /api/matches/{id}` accepts arbitrary unvalidated data (we stored `date: "not-a-date"` and
overwrote `tournament_id`), deleting a team leaves orphaned fixtures pointing at a ghost, regenerating
fixtures around a locked match produces a duplicate pairing, a category restricted to a since-deleted
ground silently falls back to *all* grounds, drawn knockout matches simply never advance anyone, and
referee assignment does not exist yet (documented backlog, but the UI hints it does).

---

## B. Test Coverage

| Layer | How tested |
|---|---|
| Backend API (all documented endpoints) | Exercised directly by harness (CRUD, fixtures, scheduling, conflicts, standings, schedule, seed-knockout) |
| Scheduling engine | 61-match global run + independent re-verification of every hard constraint; 6 infeasibility scenarios; locked matches; 2 re-runs |
| Fixture generation | All 4 formats, exact count/uniqueness/structure audits |
| Standings & tiebreakers | Full independent recompute (28 results) + crafted h2h and goals-for tie scenarios + custom points (win=2) |
| Knockout progression | Full R16→F run-through, score edits, cleared scores, half-scores, draws, TBD slots |
| Regeneration / staleness | Schedule → score → regenerate → verify no stale ids/scores/schedule rows; regen with locked match |
| Data integrity | Orphan scan, bracket-link scan, cascade deletes, junk-payload probes |
| CRUD | Tournaments, categories, teams, grounds, referees, matches (incl. invalid input, missing parents) |
| Automated tests | `pytest tests/test_scheduling_engine.py -v` → 5 passed / 5 failed (see §C) |
| Persistence | All state verified via fresh API reads after every mutation (DB-backed) |
| Frontend | Full source review of all 8 tabs + pages; UI behavioral findings are code-derived |
| Board drag-and-drop, responsive | **NOT executed live** (browser automation unavailable); code-level analysis only |
| Performance | Scheduler timing measured; realistic scale (92 fixtures, 42 teams, 5 grounds) |

---

## C. Test Results

| Area | Status | Findings |
|---|---|---|
| Fixture generation — league_single | PASS | 28/28 matches, every pair exactly once, 7 per team |
| Fixture generation — league_double | PASS | 30/30, every pair twice, legs home/away-reversed |
| Fixture generation — knockout (16) | PASS | 15 matches, 4 rounds, links resolve, one Final, 0 byes |
| Fixture generation — groups_knockout | PASS | 4 groups × 3 teams, 12 group + 7 KO, sources = top-2 × 4 groups |
| Fixture/scheduling separation | PASS | Pairings/rounds/links byte-identical through 3 scheduler runs |
| Global auto-schedule validity | PASS | 61 placed, zero hard-constraint violations (independently verified) |
| Infeasibility handling (A,B,C,E,F) | PASS | 200 + capacity + per-match reason + suggestions; placed subset stays valid |
| Infeasibility D (inaccessible ground) | **FAIL** | Silent fallback to all grounds — see Bug 4 |
| Locked matches | PASS | Survived two re-runs, scheduler packed around the anchor |
| Standings + tiebreakers | PASS | Values & order match independent recompute; h2h→GD and GF ties resolved correctly; custom win=2 honored |
| Group → KO seeding | PASS | Correct teams in correct slots; KO R1 scheduled strictly after group stage ends |
| Knockout progression | PASS | Winners advance; edits re-propagate; cleared scores withdraw team and reset next match to pending |
| KO edge: draw | PARTIAL | No winner advances, bracket stalls silently — see Bug 6 |
| KO edge: half-entered score | PARTIAL | `{home:2}` OK, but `{home:2, away:null}` marks match **completed** — see Bug 5 |
| Regeneration | PASS | Old ids, scores, schedule rows, standings all cleanly reset |
| Regen + locked match | **FAIL** | Duplicate pairing left behind — see Bug 3 |
| Team deletion | **FAIL** | Orphaned fixtures — see Bug 2 |
| Match update validation | **FAIL** | Arbitrary/protected/malformed fields accepted — see Bug 1 |
| Referee CRUD | PASS | Create/update/delete/list all correct |
| Referee auto-assignment | NOT IMPLEMENTED | 0/44 scheduled matches have a referee — documented backlog (not counted as a bug) |
| Data consistency scan | PASS | No broken bracket links, cascades work (tournament + category) |
| Board drag-and-drop | NOT TESTABLE (live) | Code analysis: locked matches draggable — see Bug 7 |
| Repo pytest suite | PARTIAL | 5/10 pass; 5 fail on hardcoded dev-server tournament IDs — environment defect in the *tests*, see Bug 8 |

---

## D. Bugs

### Bug 1 — `PUT /api/matches/{id}` accepts arbitrary, unvalidated data
**Severity: P1**
**Repro:** `PUT /api/matches/{mid}` with `{"tournament_id": "HIJACKED", "junk_field": 1, "date": "not-a-date"}` → all three stored verbatim (verified).
**Expected:** Unknown fields rejected; `tournament_id`/`category_id`/`id` immutable; `date`/`time` format-validated.
**Actual:** Anything `$set`s straight into Mongo. A malformed `date` breaks date grouping in Reports/Board; an overwritten `tournament_id` detaches the match from its tournament (it vanishes from the master schedule but still counts in category queries).
**Root cause:** `server.py :: update_match` takes `data: Dict[str, Any]` — the handoff itself lists the missing `MatchUpdate` Pydantic model as tech debt. Same pattern exists on `PUT` for tournaments/categories/teams/grounds/referees.
**Fix:** Add a `MatchUpdate` model with optional whitelisted fields (`date`, `time`, `ground_id`, `home_score`, `away_score`, `status`, `locked`, `notes`, `home_id`, `away_id`) + regex validation for date/time; apply the same whitelist idea to the other PUT endpoints.

### Bug 2 — Deleting a team leaves orphaned fixtures
**Severity: P1**
**Repro:** 4 teams → generate fixtures → `DELETE /api/teams/{tid}` → 3 matches still reference the deleted id (verified).
**Expected:** Either block deletion while fixtures exist ("regenerate fixtures first") or cascade-remove/regenerate the affected matches.
**Actual:** Matches keep a dangling `home_id`/`away_id`; UI renders "?"; the scheduler will happily schedule the ghost team; standings silently drop those matches.
**Root cause:** `server.py :: delete_team` deletes only the team document.
**Fix (minimal):** In `delete_team`, 409 if `db.matches` contains the team in this category (message: regenerate fixtures after roster changes), or delete the category's non-locked matches.

### Bug 3 — Regenerating fixtures around a locked match creates a duplicate pairing
**Severity: P2**
**Repro:** Generate → lock one match → generate again → 31 matches; the locked pairing exists twice (old locked + new copy) (verified).
**Expected:** Generation should account for preserved locked pairings (skip re-creating them) or refuse regeneration while locked matches exist.
**Actual:** `gen_fixtures` deletes `locked != true` then inserts a *complete* fresh set. The confirm dialog even advertises "Locked matches are preserved" — preserved *and duplicated*.
**Root cause:** `server.py :: gen_fixtures` never inspects surviving locked matches.
**Fix:** After generating, drop new matches whose (pair, round/leg) duplicates a surviving locked match — or simplest robust behavior: 409 with "unlock N matches before regenerating".

### Bug 4 — Category restricted to a nonexistent/deleted ground silently uses ALL grounds
**Severity: P2**
**Repro:** Category with `ground_ids: ["no-such-id"]` → auto-schedule → matches placed on unrestricted grounds, no warning (verified).
**Expected:** A `no_grounds`-style error/conflict: "this category's grounds no longer exist".
**Actual:** Silent fallback. Real-world path: organizer restricts U-13 to Ground 3, later deletes Ground 3, reschedules — U-13 lands on any ground with no hint the restriction was ignored. (Ground deletion also leaves scheduled matches pointing at the deleted ground — same family of missing referential checks.)
**Root cause:** `scheduling.py :: schedule_matches`: `cat_grounds = [gmap[g] for g in gids if g in gmap] or grounds`.
**Fix:** If `gids` is non-empty but resolves to zero grounds, emit an error conflict for that category instead of falling back.

### Bug 5 — `{home_score: X, away_score: null}` marks a match completed
**Severity: P2**
**Repro:** `PUT /api/matches/{mid}` `{"home_score": 2, "away_score": null}` → `status: "completed"` (verified).
**Expected:** Completed only when both scores are present.
**Actual:** Condition in `update_match` only checks `home_score is not None`. Standings ignore the half-scored match (they filter both-scores), so the table and the match list disagree about whether it was played.
**Fix:** Require both non-None: `data["home_score"] is not None and data["away_score"] is not None`.

### Bug 6 — Drawn knockout match advances nobody, silently
**Severity: P2 (product gap)**
**Repro:** Enter 1–1 in a KO match → next round slot stays `None`, no error, no prompt (verified).
**Expected:** KO formats need a winner: block equal scores in knockout matches, or support a decider (penalties/extra-time flag).
**Actual:** Bracket stalls; the organizer discovers it only when the next round never becomes schedulable.
**Fix (minimal):** Reject equal scores on `stage == "knockout"` with a clear message; UI hint in the bracket score inputs.

### Bug 7 — Board allows dragging locked matches (code-level, not live-verified)
**Severity: P1 (pending live confirmation)**
**Evidence:** `BoardTab.js` — every card gets `draggable` and `onDrop` calls `api.updateMatch(id, {ground_id, time, date})` with no `locked` check; the backend accepts it (Bug 1 — no validation). So the "fixed anchor" guarantee holds against the *scheduler* but not against a stray drag on the Board.
**Fix:** Skip `draggable` when `m.locked` (and show the lock icon on the card); belt-and-braces: backend rejects date/time/ground changes on locked matches unless `locked` is being cleared in the same request.

### Bug 8 — Shipped test suite depends on a dev server's data
**Severity: P2 (test debt, not app code)**
**Evidence:** 5/10 pytest failures — `SEEDED_LEAGUE`/`SEEDED_MULTI` are hardcoded UUIDs of tournaments that only existed on the original preview backend; `test_tournament_api.py` even defaults `BASE_URL` to the remote preview URL. The 5 self-contained tests (locked matches, KO progression, infeasibility, ground balancing, overlap invariants) all pass.
**Fix:** Rewrite the seeded-ID tests to build their own fixtures (the file already has `_mk_tour` helpers); default `BASE_URL` to `http://localhost:8001`.

### Minor (P3)
- **Deletes without confirmation:** tournament (Dashboard), category, team, ground, referee — one misclick on the trash icon destroys data with no undo. Matches the "Undo on the Board" backlog spirit; add confirm dialogs.
- **Board renders 06:00–22:00 only** (`BoardTab.js` `START`/`END` constants): a match at a ground open past 22:00 (Ground 4 here closes 22:00) placed at 21:30 renders clipped/outside the grid.
- **`/categories/{cid}/conflicts` builds a reduced team_info** (no dates/day-preference/max-per-day) unlike `build_team_info`, so the category conflict check is blind to date-level violations the scheduler itself enforces.
- **`detect_conflicts` rates rest violations as warnings** while the scheduler enforces them as hard — already on the handoff's tech-debt list; harmless today but confusing on the Board after manual drags.
- **Knockout "seeding" is insertion-order, not the `seed` field:** `generate_matches` uses team list order (Mongo insertion order); the `seed` number an organizer types is never consulted for bracket placement. Our harness check passed only because teams were created in seed order. Enter teams out of order and "Seeded" produces the wrong bracket. Fix: sort by `seed` (nulls last) when `category.seeded`.
- **UI implies referee assignment exists:** Venues tab empty-state says referees are tracked "for conflict-free assignment", and referee cards show max-matches/day — but nothing ever assigns them (backlog P1). Add a "coming soon" hint or ship the feature.

---

## E. Scheduling Engine Audit

Tested against a genuinely hostile configuration (two-day window, 5 grounds with differing hours,
4 formats in parallel, per-team windows/dates/no-b2b/max-per-day, protected breaks, restricted grounds,
90-min rest in U-23). Every claim below was verified by independent recomputation, not by trusting the
API's own conflict report:

- **Ground conflicts:** none, including cross-category on shared grounds. ✔
- **Team conflicts:** no overlaps anywhere. ✔
- **Minimum rest / no-back-to-back:** respected, including Baroda FC's b2b rule and U-23's 90-min rest. ✔
- **Max matches/day:** team-level (U-23: 2/day) and category-level (scenario E) both enforced. ✔
- **Team availability:** daily windows (10:00-start, 17:00-end teams) and date restrictions (Saturday-only, not-Sunday teams) all honored. ✔
- **Category windows & ground hours:** every placement inside both. ✔
- **Protected break 12:30–14:00:** zero overlaps in both categories that declared it. ✔
- **Locked matches:** honored across two full re-schedules; neighbors packed around the anchor. ✔
- **Knockout dependencies:** OB knockout refused to schedule before seeding; after seeding, KO R1 began strictly after the last group match ended. ✔
- **Cross-category coordination:** 61 matches interleaved on shared grounds with zero clashes. ✔
- **Infeasibility:** all six sabotage scenarios returned 200 with named dominant reasons ("rest / no-back-to-back rules blocked every open slot", "max-matches-per-day limit reached every day") and actionable suggestions; the partial schedule remained valid every time. ✔
- **Performance:** 0.13 s for the full multi-category solve. ✔

**Situations where the engine can still produce a *wrong* (not invalid) outcome:**
1. Bug 4 — vanished ground restrictions silently widen to all grounds.
2. Bug 7 path — a Board drag can violate anything (the Board flags it in red, but the write commits first; conflicts are advisory after the fact, which is by design but worth knowing).
3. Draws in knockout (Bug 6) stall dependent scheduling.

## F. Fixture Generation Audit

| Format | Expected | Actual | Verdict |
|---|---|---|---|
| league_single (8 teams) | 28, each pair 1×, 7/team | 28 ✔ | PASS |
| league_double (6 teams) | 30, each pair 2× reversed | 30 ✔ | PASS |
| knockout (16 teams) | 15 (8+4+2+1), linked, 1 Final, 0 byes | 15 ✔ | PASS |
| groups_knockout (12 teams, 4 groups, top 2) | 12 group + 7 KO, 8 sources | 19 ✔ | PASS |

Fixture generation never touched date/time/ground (all generated null), and three scheduler runs never
touched a pairing. The separation is real. Caveat: "seeded" order comes from insertion order, not the
`seed` field (see Minor findings).

## G. Standings Audit

Full 28-result table recomputed independently — every P/W/D/L/GF/GA/GD/Pts value and the final
ranking matched. Custom points (win=2) honored. Tiebreakers: a crafted 3-way points tie with
`head_to_head` ranked first correctly fell through (h2h all equal) to goal difference; a crafted
equal-points+GD pair correctly resolved on goals-for. Head-to-head note: it compares h2h points among
*all* teams on the same points total, which is a reasonable interpretation but differs from
FIFA-style "records among tied teams only after prior tiebreaks" in exotic cases.

## H. Data Integrity Audit

- No broken bracket links anywhere (all `next_match_id` resolve). ✔
- Cascade deletes: tournament → categories/teams/grounds/referees/matches ✔; category → teams+matches ✔.
- Regeneration: no stale ids, scores, schedule rows, or standings. ✔
- **Orphans found:** team deletion (Bug 2); ground deletion leaves `ground_id` references (renders "?").
- **Duplicates found:** regen-with-locked-match (Bug 3).
- **Unprotected writes:** Bug 1 lets any client corrupt any record field-by-field.

## I. UX Review (code-level; scores 1–10)

- **Usability 7** — clear tab flow (Categories → Teams → Fixtures → Schedule → Board), consistent CRUD dialogs, good `data-testid` discipline. Deducted: no confirmations on destructive actions, no undo.
- **Clarity 7** — "none selected = all grounds", "0 = unlimited", single-day hints are genuinely helpful. Deducted: nothing tells you KO matches need seeding + a re-run of the scheduler after group results.
- **Scheduling UX 8** — the standout. Named per-match failure reasons and a "How to fix" panel are better than most commercial tools. Deducted: unscheduled matches aren't listed as a workable queue anywhere outside the conflict text.
- **Error handling 5** — backend errors surface as toasts, good; but silent fallbacks (Bug 4), silent KO stalls (Bug 6), and unvalidated writes (Bug 1) mean errors that *should* exist don't.
- **Visual design 8** — coherent Tactical Night system, readable board with lane-splitting, sensible legend.
- **Information architecture 7** — Overview/Reports give good rollups; referee data is collected but never appears where it matters (matches).
- **Operator-friendliness 6** — for the happy path, strong. For tournament day: no undo, no audit trail, draws stall brackets, roster changes corrupt fixtures, and one accidental drag can move a locked anchor.

## J. Deployment Readiness

- **Env/config:** backend fully env-driven ✔; frontend uses `REACT_APP_BACKEND_URL` ✔ (was still pointing at the defunct Emergent preview URL — fixed during setup; keep an eye on `.env` in deploys). Docker compose is coherent.
- **Removed local blocker:** `emergentintegrations==0.2.0` (private, unused) commented out of `requirements.txt` to make installs work off-platform.
- **CORS `*` + no auth:** by design for this version — but that means anyone who can reach port 8001 can delete every tournament. Do not expose publicly.
- **DB:** name `test_database`; no credentials committed (local dev assumption); no indexes defined (fine at this scale).
- **Frontend build:** CRA/CRACO standard; no hardcoded URLs found in source.
- **Logging:** basicConfig only; no request logging or error tracking.
- **Tests in CI:** would fail today (Bug 8) — must be made self-contained first.
- **Deprecation:** `@app.on_event("shutdown")` is deprecated on modern FastAPI (use lifespan) — cosmetic for now.

## K. Prioritized Fix List

**Fix immediately (P0/P1):** none P0. P1: Bug 1 (validate `PUT /matches` + protect immutable fields), Bug 2 (team deletion guard), Bug 7 (locked matches undraggable + backend enforcement).
**Fix before production (P2):** Bug 3 (regen vs locked duplicates), Bug 4 (ground-restriction fallback), Bug 5 (half-score completed), Bug 6 (KO draws), Bug 8 (self-contained tests), seeded-bracket uses `seed` field, delete confirmations.
**Fix later (P3):** Board 06:00–22:00 clamp, category-conflicts reduced team_info, rest-severity alignment, lifespan migration, ground-deletion dangling refs surfaced in UI.
**Enhancements:** unscheduled-match work queue in the UI, undo on Board, penalties/extra-time result model, audit log.
**Existing backlog (not bugs):** referee auto-assignment (P1 backlog — currently 0 matches have referees; hide or caveat the implying UI until shipped), best-N-third qualification, multiple break windows, clone tournament.

---

## The Final Question

> *"If this application were being used tomorrow to run a real multi-category football tournament with 40+ teams, 5 grounds and hundreds of scheduling decisions, what are the top 5 things I would be worried about?"*

1. **Capacity truth-telling, not capacity failure.** In our realistic 2-day setup, 17 of 78 matches simply did not fit, and the engine was right — the tournament as configured was impossible. The scary version on match day: an organizer who doesn't read the conflict panel, sees a full-looking Board, and doesn't notice Round 6 doesn't exist. There is no big red "17 MATCHES UNPLACED" banner that persists after the toast fades.
2. **One accidental action can quietly corrupt the event.** Deleting a team with fixtures leaves ghost matches; a drag on a locked anchor moves it; there is no confirmation, undo, or audit trail on anything. Under match-day stress with multiple people on the same open (auth-less) backend, this is the most likely real-world failure.
3. **Knockout draws.** Youth football ends level all the time. The first 1–1 quarter-final stalls the bracket with no message, and the semi-final becomes unschedulable while the organizer hunts for why.
4. **Referees are a spreadsheet on the side.** The app collects certifications and per-day limits and then assigns nobody to anything. Tomorrow's tournament still runs referee allocation on paper, with all the double-booking risk the app was supposed to remove.
5. **Mid-tournament changes are the weak flank.** The engine's *initial* solve is excellent, but real tournaments mutate: a team withdraws (orphan bug), rain closes Ground 3 (restriction silently widens to all grounds), a round gets regenerated around a locked final (duplicate fixture). Every failure we found lives on this mutation path, not the happy path.

**Bottom line:** the scheduling core is legitimately good — tested hard, it never produced an invalid
schedule and it fails loudly and helpfully. The wrapper around it still trusts its users and its data
too much. Fix the five P1/P2 mutation-path bugs and this is a tool I'd trust to run a real tournament.
