# TournamentOS — PRD

## Original Problem Statement
Build TournamentOS: a complete, fully-configurable operating system for planning, organizing, scheduling and running sporting tournaments of any size. Nothing hardcoded; the organizer adapts the software to the tournament. Heart of the system is a conflict-aware scheduling engine that separates WHO-plays-WHO (fixtures) from WHEN/WHERE (scheduling).

## Architecture
- **Backend:** FastAPI + MongoDB (motor). `server.py` (CRUD + orchestration) + `scheduling.py` (fixture generation, scheduling engine, standings). UUID string ids; sport-agnostic, config-driven.
- **Frontend:** React (CRA/craco) + Tailwind + shadcn/ui. "Tactical Night" dark theme, Barlow Condensed / Manrope fonts, lime-400 accent.
- **Preview URL:** https://schedule-engine-10.preview.emergentagent.com
- No authentication in v1 (endpoints open).

## Core Requirements (static)
- Any number of tournaments, categories, teams. Each category independent (format, points, constraints, grounds).
- Formats: single/double round robin league, knockout (byes + seeding), groups + knockout.
- Configurable points + ordered tiebreakers.
- Conflict-aware auto-scheduler with configurable constraints; human-readable conflict + infeasibility explanations.
- Standings (grouped + single), master schedule report + CSV export.

## Scheduling Engine (rewritten 2026-08-04 — global best-slot)
`scheduling.py :: schedule_matches(items, grounds, tour_dates)` — quality-first, globally-aware scheduler.
- Only assigns date/time/ground; never touches fixtures/opponents.
- Ordering: group/league before knockout (feeders first), earlier rounds first, tightest-window categories first.
- Chronological progression: knockout rounds start only after their feeders finish; groups' KO after all group matches.
- For each match, evaluates ALL feasible slots and commits the lowest-cost one (`_score_slot`): ground-balance/parallelism (dominant → finish early), earliest time (finals prefer late), packing (min idle ground time), comfortable rest, avoid soft back-to-back.
- Hard constraints honoured: ground availability + open/close, match duration, buffer, tournament breaks, team availability windows, category hours, min rest, max/day (team+category), locked/already-scheduled matches.
- Validates committed schedule (no ground/team clashes). On infeasibility: returns unscheduled list + 'capacity' conflict + per-match 'unplaced_match' diagnostics (naming the dominant blocking reason) + targeted suggestions. Never silent-fails.
- Modular: add hard checks in the placement loop, add soft goals as terms in `_score_slot`.
- Verified by 10 backend pytest cases (100% pass) in `/app/backend/tests/test_scheduling_engine.py`.

## Changelog
- 2026-08-04: Fixed Team dialog scrolling (max-h + overflow).
- 2026-08-04: Reports — 12-hour times, category shown per match, numeric ground names shown as "Ground N" (shared `groundLabel` in bits.js). Added "By Time" / "By Ground" view toggle; CSV export adapts to the active view.
- 2026-08-04: Rewrote the core Scheduling Engine to a global best-slot optimizer (see above). Added team name to `build_team_info` for diagnostics.

## Backlog (P1/P2/P3)
- P1: Best-3rd qualification ("best N third-placed teams advance").
- P1: Referee auto-assignment into schedule (daily limits, no clashes).
- P2: Multiple protected break windows per day.
- P2: Undo button on drag-and-drop Board.
- P2: Tournament duplicate/clone for next season.
- P2 (from code review): allow scheduling knockout bracket slots with unresolved teams up-front; MatchUpdate Pydantic model for update_match; align rest-violation severity to 'error'.
- P3: Role-based permissions, public tournament pages, notifications, PDF exports, mobile.
