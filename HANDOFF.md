# TournamentOS — Developer Handoff

A complete, fully-configurable operating system for planning, scheduling and running sporting
tournaments (football-first, but sport-agnostic). The heart of the app is a **conflict-aware
scheduling engine** that strictly separates *WHO plays WHO* (fixtures) from *WHEN/WHERE* (scheduling).

> **How to use this doc:** Paste it into ChatGPT (or any assistant) as context before asking for
> help. It describes the stack, how to run everything locally, the data model, every API endpoint,
> the scheduling engine, and the frontend structure. There is **no authentication** in this version.

---

## 1. Tech Stack

| Layer     | Tech |
|-----------|------|
| Frontend  | React 19, React Router 7, CRA + CRACO, Tailwind CSS 3, shadcn/ui (Radix), lucide-react icons, axios, sonner (toasts) |
| Backend   | FastAPI, Uvicorn, Pydantic, Motor (async MongoDB driver) |
| Database  | MongoDB (single database, collections per entity) |
| Language  | Python 3.10+ (backend), Node 18+/Yarn (frontend) |

Design theme: "Tactical Night" dark UI, Barlow Condensed / Manrope fonts, lime-400 (`#a3e635`) accent.

---

## 2. Repository Structure

```
/
├── backend/
│   ├── server.py          # FastAPI app: all CRUD + orchestration endpoints (prefix /api)
│   ├── scheduling.py       # Fixture generation + scheduling engine + standings (pure logic)
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── tests/
│   │   └── test_scheduling_engine.py   # 10 pytest cases validating the scheduler
│   └── .env
└── frontend/
    ├── src/
    │   ├── App.js                       # Routes: "/" Dashboard, "/t/:id" TournamentDetail
    │   ├── index.js
    │   ├── lib/api.js                    # Central axios API client (all endpoints wrapped)
    │   ├── lib/utils.js
    │   ├── components/
    │   │   ├── bits.js                   # Shared UI atoms (SectionTitle, Empty, Overline, Stat, Labeled, groundLabel)
    │   │   ├── tabs/                      # One component per tournament tab
    │   │   │   ├── CategoriesTab.js       # Category CRUD + format/points/constraints editor
    │   │   │   ├── TeamsTab.js            # Team CRUD + availability & scheduling rules
    │   │   │   ├── VenuesTab.js           # Grounds & Referees CRUD
    │   │   │   ├── FixturesTab.js         # Generate fixtures; knockout bracket tree (SVG); score entry
    │   │   │   ├── ScheduleTab.js         # Constraint editor + run auto-scheduler + live conflicts
    │   │   │   ├── BoardTab.js            # Drag-and-drop calendar board with live conflict check
    │   │   │   ├── StandingsTab.js        # Configurable standings tables
    │   │   │   └── ReportsTab.js          # Master schedule (By Time / By Ground views) + CSV export
    │   │   └── ui/                        # shadcn/ui primitives (do not hand-edit heavily)
    │   └── pages/
    │       ├── Dashboard.js               # Tournament list + create/delete
    │       └── TournamentDetail.js        # Tab shell; owns the tournament + categories state
    ├── package.json                       # NOTE: scripts use CRACO (craco start/build)
    └── .env
```

---

## 3. Running Locally

Start order: **MongoDB → backend → frontend**.

### 3.0 Fastest path — Docker (one command)
If you have Docker Desktop, from the project root:
```bash
docker compose up --build
```
This starts MongoDB, the backend (http://localhost:8001) and the frontend (http://localhost:3000)
together. Open http://localhost:3000. Stop with `Ctrl+C`; remove with `docker compose down`
(add `-v` to also wipe the database volume). Files: `docker-compose.yml`, `backend/Dockerfile`,
`frontend/Dockerfile`. You do NOT need to edit any `.env` for the Docker path — compose sets them.

The manual (non-Docker) steps below are equivalent if you prefer running each service yourself.

### 3.1 MongoDB
Install MongoDB Community, or run via Docker:
```bash
docker run -d -p 27017:27017 --name mongo mongo:7
```

### 3.2 Backend (FastAPI on port 8001)
```bash
cd backend
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```
`backend/.env` (already set for local Mongo):
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
CORS_ORIGINS="*"
```
- The FastAPI app object is `server:app`. All routes are under the `/api` prefix.
- Quick check: `curl http://localhost:8001/api/` → `{"message": ...}`.

### 3.3 Frontend (React on port 3000)
Point the frontend at your local backend by editing `frontend/.env`:
```
REACT_APP_BACKEND_URL=http://localhost:8001
WDS_SOCKET_PORT=0
ENABLE_HEALTH_CHECK=false
```
Then:
```bash
cd frontend
yarn install
yarn start
```
Open http://localhost:3000. The DB starts empty — create a tournament from the dashboard.

### Conventions that MUST be preserved
- **All backend routes are prefixed with `/api`.** The frontend calls `${REACT_APP_BACKEND_URL}/api/...`.
- Frontend must always use `process.env.REACT_APP_BACKEND_URL` (never hardcode URLs).
- Backend must always read Mongo config from env (`MONGO_URL`, `DB_NAME`).
- IDs are UUID strings (not Mongo ObjectIds); documents are stored/returned with `_id` excluded.

---

## 4. Data Model (MongoDB collections)

All timestamps are ISO strings. All ids are UUID strings. Times are `"HH:MM"` (24h). Dates are `"YYYY-MM-DD"`.

### `tournaments`
`{ id, name, sport="Football", organizer?, location?, start_date?, end_date?, description?, status="planning", created_at }`

### `categories` (belongs to a tournament; fully independent config)
```
{ id, tournament_id, name,
  format: "league_single" | "league_double" | "knockout" | "groups_knockout",
  seeded: bool, num_groups: int, qualifiers_per_group: int,
  age_restriction?, custom_rules?,
  points_config: { win:3, draw:1, loss:0, tiebreakers:["points","goal_difference","goals_for","wins","head_to_head"] },
  constraints: { ...see below },
  ground_ids: [groundId]          # empty = all tournament grounds allowed
}
```
`constraints` (merged over defaults):
```
{ start_date?, end_date?,             # falls back to tournament dates
  earliest_time:"08:00", latest_time:"20:00",
  match_duration_minutes:90, slot_gap_minutes:30,   # slot_gap = buffer between matches
  min_rest_minutes:60, max_matches_per_day:0,       # 0 = unlimited
  break_start?, break_end?,           # one protected mid-day break window
  unavailable_dates:[] }
```

### `teams` (belongs to a category)
```
{ id, tournament_id, category_id, name, short_name?, coach?, manager?, contact?, city?, country?, association?, seed?,
  available_from?, available_to?,     # daily playable window "HH:MM"
  no_back_to_back: bool,              # needs a full match-length gap between its matches
  available_dates:[], unavailable_dates:[],
  day_preference: "any" | "weekday" | "weekend",
  max_matches_per_day?: int }
```

### `grounds` (belongs to a tournament)
```
{ id, tournament_id, name, capacity?, surface?, lighting: bool,
  open_time?, close_time?, priority:1, notes? }
```

### `referees` (belongs to a tournament) — auto-assigned after scheduling
`{ id, tournament_id, name, certification?, experience_years?, max_matches_per_day:3, phone? }`

### `matches` (generated by fixture generation; scheduled by the engine)
```
{ id, tournament_id, category_id,
  stage: "league" | "group" | "knockout",
  round: int, group?: "Group A", order: int, label?: "Final"|"Semi-Final"|...,
  home_id?, away_id?,                 # null = BYE or TBD (knockout slot not yet resolved)
  bracket_pos?, next_match_id?, next_slot?: "home"|"away",   # knockout progression links
  home_source?, away_source?,         # groups_knockout: {group, pos} feeding a KO slot
  is_bye?: bool,
  # scheduling fields (set by the engine / drag board):
  date?, time?, ground_id?,
  # results:
  home_score?, away_score?, status: "scheduled"|"completed"|"bye", locked: bool }
```

---

## 5. API Endpoints (all prefixed with `/api`)

**Tournaments**
- `POST /tournaments` · `GET /tournaments` · `GET /tournaments/{tid}` · `PUT /tournaments/{tid}` · `DELETE /tournaments/{tid}`

**Categories**
- `POST /tournaments/{tid}/categories` · `GET /tournaments/{tid}/categories`
- `GET /categories/{cid}` · `PUT /categories/{cid}` · `DELETE /categories/{cid}`

**Teams**
- `POST /categories/{cid}/teams` · `GET /categories/{cid}/teams` · `PUT /teams/{tid}` · `DELETE /teams/{tid}`

**Grounds & Referees**
- `POST /tournaments/{tid}/grounds` · `GET /tournaments/{tid}/grounds` · `PUT /grounds/{gid}` · `DELETE /grounds/{gid}`
- `POST /tournaments/{tid}/referees` · `GET /tournaments/{tid}/referees` · `PUT /referees/{rid}` · `DELETE /referees/{rid}`

**Fixtures & Matches**
- `POST /categories/{cid}/generate-fixtures`  — (re)generate all matches for a category from its format. Replaces existing matches.
- `GET  /categories/{cid}/matches`
- `PUT  /matches/{mid}`  — used by the drag board to set `{date,time,ground_id}`, enter scores, toggle `locked`, advance knockout winners.
- `DELETE /categories/{cid}/matches`
- `POST /categories/{cid}/seed-knockout`  — seed group qualifiers into the knockout bracket.

**Scheduling** (returns `{scheduled, unscheduled, conflicts, suggestions, referees_assigned, ...}`)
- `POST /categories/{cid}/auto-schedule`      — schedule one category.
- `POST /tournaments/{tid}/auto-schedule`     — schedule ALL categories together on shared grounds (recommended).
- `POST /tournaments/{tid}/assign-referees`   — re-run referee assignment only (never touches date/time/ground).
- `GET  /categories/{cid}/conflicts` · `GET /tournaments/{tid}/conflicts`  — live conflict lists (used by the Board).
- `GET  /tournaments/{tid}/schedule`          — flat list of all placed matches for reports/board.

**Standings**
- `GET /categories/{cid}/standings`  — grouped (for group stages) or single table; honours `points_config` + ordered tiebreakers.

Frontend wrappers for all of these live in `frontend/src/lib/api.js`.

---

## 6. The Scheduling Engine (`backend/scheduling.py`)

This is the core intelligence. Two independent concerns are kept strictly separate:

- **Fixture generation** — `generate_matches(category, teams)` decides WHO plays WHO. Supports
  `league_single`, `league_double` (circle-method round robin), `knockout` (power-of-two bracket
  with byes + optional seeding, `next_match_id` progression links), and `groups_knockout`
  (snake-allocated groups + a bracket skeleton fed by `home_source`/`away_source`). It never
  touches time/place.

- **Scheduling** — `schedule_matches(items, grounds, tour_dates)` decides WHEN/WHERE. It only ever
  assigns `date`, `time`, `ground_id`; it never changes opponents/fixtures.

### How `schedule_matches` works (global, quality-first best-slot)
`items` is a list of `{cat_id, constraints, matches, team_info, ground_ids, locked}`. Returns
`(scheduled, unscheduled, conflicts, suggestions)` and mutates each match in place with date/time/ground.

1. **Pre-book locked / already-placed matches** as fixed anchors the scheduler works around.
2. **Ordering** (most-constrained / dependency-first): group/league before knockout (feeders first),
   earlier rounds first, tighter-window categories first, then stable order.
3. **Chronological progression**: a knockout match may only start after all its feeder matches finish
   (a Final lands after the Semi-Finals; KO after the group stage), tracked via `next_match_id`
   and per-category group→KO dependency.
4. **Best-slot placement**: for each match it finds the *earliest feasible day*, gathers **all**
   feasible slots on that day (every eligible ground × candidate times at block edges), scores each
   with `_score_slot`, and commits the lowest-cost one — not the first that fits.
5. **`_score_slot` (modular multi-objective, lower = better):**
   - `W_GROUND_BALANCE` (dominant) — prefer the least-loaded ground that day → parallelism + balanced usage + earliest finish.
   - `W_TIME` — prefer earlier starts (finals prefer *later*, to close the event).
   - `W_IDLE` — prefer starting right after an existing match → minimise unused ground time (packing).
   - `W_SOFT_B2B` — penalise creating a near back-to-back for a team even when allowed.
   - `W_REST` — penalise rest below a comfortable margin over the hard minimum.
   Add new soft goals by adding terms here. Add new hard constraints in the placement loop.
6. **Hard constraints enforced**: ground availability + open/close, match duration, buffer
   (`slot_gap_minutes`), protected break window, team availability windows, category playing hours,
   minimum rest, max-matches-per-day (team + category), team available/unavailable dates,
   weekday/weekend preference, and locked matches.
7. **Validation**: after committing, `detect_conflicts` + a cross-category ground-overlap check
   re-verify the schedule. Nothing invalid is committed silently.
8. **Graceful infeasibility**: when a match can't be placed, it records the dominant blocking reason
   and returns a `capacity` conflict + per-match `unplaced_match` messages naming the reason +
   targeted `suggestions` (add grounds/days, widen windows, raise max/day, reduce rest, etc.).

### Referees — `assign_referees(placed, referees)`
A strictly post-scheduling pass: it only ever writes `referee_id` and never touches fixtures or
date/time/ground. Hard constraints: no referee officiates two overlapping matches, and each
referee's own `max_matches_per_day` is respected. Soft objective: even workload (least-loaded
official first, experience breaking ties). Referees already pinned on locked matches are kept.
If officials run out, the uncovered matches are reported as a `referee_capacity` warning — never
left silently blank.

### Standings — `compute_standings(teams, matches, points_config)`
Computes P/W/D/L/GF/GA/GD/Pts from completed matches and ranks by the configured ordered
tiebreakers (`points`, `goal_difference`, `goals_for`, `wins`, `head_to_head`).

### Tests
`cd backend && pytest tests/test_scheduling_engine.py -v` — 10 cases covering: no ground/team
overlaps, min-rest respected, fixtures untouched, locked preserved, knockout progression, graceful
infeasibility, per-category endpoint, and ground balancing. (They hit a running backend via
`REACT_APP_BACKEND_URL`, defaulting to the frontend `.env`.)

---

## 7. Frontend Notes
- `TournamentDetail.js` is the tab shell (Overview, Categories, Teams, Grounds & Referees, Fixtures,
  Schedule, Board, Standings, Reports). It loads the tournament + its categories and passes them down.
- `BoardTab.js` is a **pixel-accurate calendar**: background 30-min cells are drop targets; match
  cards are absolutely positioned by exact start time and duration, with automatic side-by-side lane
  splitting when matches truly overlap. Times display in 12-hour am/pm. Dragging a card calls
  `PUT /matches/{mid}` then re-checks conflicts live.
- `ReportsTab.js` has **By Time** and **By Ground** views; CSV export adapts to the active view.
- `bits.js :: groundLabel(name)` renders purely-numeric ground names ("1","2") as "Ground 1", "Ground 2".
- Every interactive/important element has a `data-testid` (kebab-case) — keep this convention.
- Build/serve uses **CRACO** (`yarn start` / `yarn build`), not raw react-scripts.

---

## 8. Current State & Backlog

**Done:** Tournament/category/team/ground/referee CRUD; fixture generation for all 4 formats;
knockout bracket tree; group→knockout seeding; the global scheduling engine; drag-and-drop board with
live conflicts; configurable standings; reports + CSV; single-day tournaments; edit tournament dates.

**Also done (post-QA hardening, see `QA_REPORT.md`):** referee auto-assignment; `MatchUpdate`
validation on `PUT /matches`; team-deletion guard; regeneration blocked over locked matches;
loud failure when a category's grounds no longer exist; knockout draws rejected; locked matches
undraggable; seeded brackets honour the `seed` field; delete confirmations; self-contained tests.

**Backlog (suggested next):**
- P1 — **Best-3rd qualification** ("best N third-placed teams advance").
- P2 — Multiple protected break windows per day; Undo on the Board; clone a tournament for next season.
- P2 — Authentication (none today — do not expose the backend publicly).
- Tech debt — align rest-violation severity in `detect_conflicts` with the hard enforcement in the
  scheduler; migrate `@app.on_event("shutdown")` to FastAPI lifespan; apply the `MatchUpdate`
  whitelist pattern to the other `PUT` endpoints.

**Golden rules for future work**
1. Never mix fixtures and scheduling. Fixtures = match-ups; scheduling = time/place only.
2. Nothing hardcoded — every rule is configurable per category or per team.
3. No auth in this version.
4. Keep the `/api` prefix and env-var driven config intact.
