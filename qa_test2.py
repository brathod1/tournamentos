"""TournamentOS QA Harness — Part 2.
Locked matches, standings/tiebreakers, group->KO seeding, knockout progression,
regeneration/staleness, intentional infeasibility A-F, CRUD & data integrity.
Invoked by qa_test.py; do not run directly.
"""
import json
from collections import defaultdict


def run(GC, RESULTS, check, info, api, jget, parse_t,
        mk_tour, mk_ground, mk_cat, mk_team, CREATED_TOURS, collect_items):

    tid = GC["tid"]

    # ============================================================ 4. LOCKED MATCHES
    sec = "4-locked"
    u13_ms = jget(f"/categories/{GC['u13']}/matches")
    placed = [m for m in u13_ms if m.get("date")]
    if check(sec, "have a placed U-13 match to lock", bool(placed)):
        m0 = placed[0]
        lock_slot = {"date": "2026-09-06", "time": "15:00", "ground_id": GC["g"][1], "locked": True}
        r = api("PUT", f"/matches/{m0['id']}", json=lock_slot)
        check(sec, "manual place + lock accepted", r.status_code == 200, r.text[:200])
        r = api("POST", f"/tournaments/{tid}/auto-schedule")
        check(sec, "re-run scheduler ok", r.status_code == 200)
        after = {m["id"]: m for m in jget(f"/categories/{GC['u13']}/matches")}
        ma = after[m0["id"]]
        check(sec, "locked match did not move",
              (ma["date"], ma["time"], ma["ground_id"], ma["locked"]) ==
              ("2026-09-06", "15:00", GC["g"][1], True),
              (ma["date"], ma["time"], ma.get("ground_id"), ma.get("locked")))
        # nothing else overlaps the locked slot on that ground
        _, grounds, data = collect_items()
        clash = []
        for cid, d in data.items():
            dur = int((d["cat"].get("constraints") or {}).get("match_duration_minutes", 90))
            for m in d["matches"]:
                if m["id"] == m0["id"] or not m.get("date"):
                    continue
                if m["date"] == "2026-09-06" and m.get("ground_id") == GC["g"][1]:
                    s = parse_t(m["time"])
                    if s < 16 * 60 and 15 * 60 < s + dur:
                        clash.append((d["cat"]["name"], m["id"], m["time"]))
        check(sec, "scheduler worked around the locked anchor", not clash, clash)
        GC["locked_id"] = m0["id"]

    # ============================================================ 5. U-13 RESULTS + STANDINGS RECOMPUTE
    sec = "5-standings-u13"
    u13_ms = jget(f"/categories/{GC['u13']}/matches")
    for i, m in enumerate(sorted(u13_ms, key=lambda x: x["order"])):
        h, a = (i * 3 + 1) % 5, (i * 2) % 4        # deterministic pseudo-scores incl. draws
        api("PUT", f"/matches/{m['id']}", json={"home_score": h, "away_score": a, "status": "completed"})
    api_st = jget(f"/categories/{GC['u13']}/standings")
    check(sec, "standings endpoint returns flat table", api_st.get("grouped") is False)
    rows = api_st["standings"]
    # independent recompute (3/1/0; tiebreakers points, gd, gf, wins, then name)
    ms = jget(f"/categories/{GC['u13']}/matches")
    teams = {t["id"]: t["name"] for t in jget(f"/categories/{GC['u13']}/teams")}
    tb = defaultdict(lambda: dict(p=0, w=0, d=0, l=0, gf=0, ga=0, pts=0))
    for m in ms:
        if m.get("status") != "completed" or m.get("home_score") is None:
            continue
        h, a = m["home_score"], m["away_score"]
        H, A = tb[m["home_id"]], tb[m["away_id"]]
        H["p"] += 1; A["p"] += 1; H["gf"] += h; H["ga"] += a; A["gf"] += a; A["ga"] += h
        if h > a: H["w"] += 1; A["l"] += 1; H["pts"] += 3
        elif a > h: A["w"] += 1; H["l"] += 1; A["pts"] += 3
        else: H["d"] += 1; A["d"] += 1; H["pts"] += 1; A["pts"] += 1
    exp = sorted(tb.items(), key=lambda kv: (-kv[1]["pts"], -(kv[1]["gf"] - kv[1]["ga"]),
                                             -kv[1]["gf"], -kv[1]["w"], teams[kv[0]]))
    ok_vals = all(
        (r["played"], r["won"], r["drawn"], r["lost"], r["gf"], r["ga"], r["points"]) ==
        (tb[r["team_id"]]["p"], tb[r["team_id"]]["w"], tb[r["team_id"]]["d"], tb[r["team_id"]]["l"],
         tb[r["team_id"]]["gf"], tb[r["team_id"]]["ga"], tb[r["team_id"]]["pts"]) for r in rows)
    check(sec, "P/W/D/L/GF/GA/Pts all match independent recompute", ok_vals)
    check(sec, "ranking order matches independent recompute",
          [r["team_id"] for r in rows] == [k for k, _ in exp],
          [(teams[r['team_id']], r['points']) for r in rows])

    # ---- explicit tiebreaker scenarios in a throwaway tournament ----
    sec = "5-tiebreakers"
    tt = mk_tour("TEST_QA_tiebreak", "2026-10-01", "2026-10-02")
    g = mk_ground(tt, "TG")
    # h2h before gd: custom order
    cid = mk_cat(tt, "TB", "league_single",
                 {"start_date": "2026-10-01", "end_date": "2026-10-02"}, [g],
                 points={"win": 3, "draw": 1, "loss": 0,
                         "tiebreakers": ["points", "head_to_head", "goal_difference", "goals_for", "wins"]})
    A = mk_team(cid, "TB-A"); B = mk_team(cid, "TB-B"); C = mk_team(cid, "TB-C")
    api("POST", f"/categories/{cid}/generate-fixtures")
    ms = jget(f"/categories/{cid}/matches")
    def by_pair(x, y):
        for m in ms:
            if {m["home_id"], m["away_id"]} == {x, y}:
                return m
        return None
    # A beats C 1-0; B beats C 5-0; B beats A 1-0  => A,B both 3? no: A 3pts, B 6. Make:
    # A beats B 2-1 ; B beats C 4-0 ; C beats A 1-0  -> all on 3 pts, GD: A +0? A: +1,-1=0. B: -1+4=+3. C: -4+1=-3
    # with h2h FIRST all three tied on 3pts -> h2h among the trio == same 3pts each -> falls to GD -> B, A, C
    for (x, y, hs, as_) in [(A, B, 2, 1), (B, C, 4, 0), (C, A, 1, 0)]:
        m = by_pair(x, y)
        home_first = m["home_id"] == x
        api("PUT", f"/matches/{m['id']}", json={
            "home_score": hs if home_first else as_, "away_score": as_ if home_first else hs,
            "status": "completed"})
    st = jget(f"/categories/{cid}/standings")["standings"]
    check(sec, "3-way tie on points falls through h2h to GD (B,A,C)",
          [r["team_name"] for r in st] == ["TB-B", "TB-A", "TB-C"],
          [(r['team_name'], r['points'], r['gd']) for r in st])
    # goals_for tiebreak: equal pts & GD
    cid2 = mk_cat(tt, "TB2", "league_single",
                  {"start_date": "2026-10-01", "end_date": "2026-10-02"}, [g])
    D = mk_team(cid2, "TB-D"); E = mk_team(cid2, "TB-E"); F = mk_team(cid2, "TB-F"); Gt = mk_team(cid2, "TB-G")
    api("POST", f"/categories/{cid2}/generate-fixtures")
    ms = jget(f"/categories/{cid2}/matches")
    def set_pair(x, y, hs, as_):
        for m in ms:
            if {m["home_id"], m["away_id"]} == {x, y}:
                hf = m["home_id"] == x
                api("PUT", f"/matches/{m['id']}", json={
                    "home_score": hs if hf else as_, "away_score": as_ if hf else hs,
                    "status": "completed"})
                return
    # D: beats F 3-2, beats G 1-0, loses E 0-1 -> 6pts GF4 GA3 GD+1
    # E: beats D 1-0, beats G 1-0, loses F 0-1 -> 6pts GF2 GA1 GD+1  => D above E on GF
    set_pair(D, F, 3, 2); set_pair(D, Gt, 1, 0); set_pair(E, D, 1, 0)
    set_pair(E, Gt, 1, 0); set_pair(F, E, 1, 0); set_pair(F, Gt, 0, 1)
    st = jget(f"/categories/{cid2}/standings")["standings"]
    top2 = [r["team_name"] for r in st[:2]]
    check(sec, "equal pts+GD resolved by goals_for (D above E)", top2 == ["TB-D", "TB-E"],
          [(r['team_name'], r['points'], r['gd'], r['gf']) for r in st])

    # ============================================================ 6. OPEN BOYS: GROUPS -> KO
    sec = "6-groups-ko"
    ob = GC["ob"]
    ms = jget(f"/categories/{ob}/matches")
    grp_ms = [m for m in ms if m["stage"] == "group"]
    # winner = lexicographically-smaller team id, margin varies -> deterministic + verifiable
    for i, m in enumerate(sorted(grp_ms, key=lambda x: x["order"])):
        hs = 2 + (i % 2); as_ = i % 2   # home always wins or wins by 2
        api("PUT", f"/matches/{m['id']}", json={"home_score": hs, "away_score": as_, "status": "completed"})
    st = jget(f"/categories/{ob}/standings")
    check(sec, "OB standings grouped", st.get("grouped") is True and len(st["standings"]) == 4)
    # custom points config (win=2) honored?
    any_group = next(iter(st["standings"].values()))
    max_pts = max(r["points"] for r in any_group)
    check(sec, "custom points config (win=2) honored in standings", max_pts <= 4, f"max pts {max_pts} (2 games)")
    expected_slot = {}
    for gname, rows in st["standings"].items():
        expected_slot[(gname, 1)] = rows[0]["team_id"]
        expected_slot[(gname, 2)] = rows[1]["team_id"]
    r = api("POST", f"/categories/{ob}/seed-knockout")
    check(sec, "seed-knockout ok", r.status_code == 200, r.text[:200])
    ms = jget(f"/categories/{ob}/matches")
    ko1 = [m for m in ms if m["stage"] == "knockout" and m["round"] == 1]
    ok = True; det = []
    for m in ko1:
        for side in ("home", "away"):
            src = m.get(f"{side}_source")
            want = expected_slot.get((src["group"], src["pos"])) if src else None
            got = m.get(f"{side}_id")
            if want != got:
                ok = False; det.append((m["id"], side, src, "want", want, "got", got))
    check(sec, "correct teams seeded into correct KO slots", ok, det[:4])

    # reschedule so KO R1 gets slots; groups keep results
    r = api("POST", f"/tournaments/{tid}/auto-schedule")
    check(sec, "re-schedule after seeding ok", r.status_code == 200)
    ms = jget(f"/categories/{ob}/matches")
    grp_end = max((m["date"], parse_t(m["time"]) + 45) for m in ms if m["stage"] == "group" and m.get("date"))
    ko1_placed = [m for m in ms if m["stage"] == "knockout" and m["round"] == 1 and m.get("date")]
    info(sec, "KO R1 placed", f"{len(ko1_placed)}/4")
    if ko1_placed:
        ko_start = min((m["date"], parse_t(m["time"])) for m in ko1_placed)
        check(sec, "KO round 1 starts after the whole group stage ends", ko_start >= grp_end,
              f"group end {grp_end} vs ko start {ko_start}")
    # locked match still where we put it?
    if GC.get("locked_id"):
        ml = next(m for m in jget(f"/categories/{GC['u13']}/matches") if m["id"] == GC["locked_id"])
        check(sec, "locked match survived second re-schedule",
              (ml["date"], ml["time"]) == ("2026-09-06", "15:00"), (ml["date"], ml["time"]))
    # score entered on group match survived rescheduling?
    g0 = next(m for m in ms if m["stage"] == "group")
    check(sec, "group results survived re-schedule", g0.get("home_score") is not None)

    # play out the OB knockout: QF -> SF -> F using next_match_id
    by_id = {m["id"]: m for m in ms}
    def play(m, hs, as_):
        api("PUT", f"/matches/{m['id']}", json={"home_score": hs, "away_score": as_, "status": "completed"})
    for m in ko1:
        play(by_id[m["id"]], 1, 0)   # home advances
    ms = {m["id"]: m for m in jget(f"/categories/{ob}/matches")}
    ok = True; det = []
    for m in ko1:
        nm = ms.get(m["next_match_id"])
        winner = ms[m["id"]]["home_id"]
        if not nm or nm.get(f"{m['next_slot']}_id") != winner:
            ok = False; det.append((m["id"], "->", m["next_match_id"]))
    check(sec, "QF winners advanced into SF slots", ok, det)
    sfs = [m for m in ms.values() if m["stage"] == "knockout" and m["round"] == 2]
    check(sec, "SF matches now have both teams & status scheduled",
          all(m.get("home_id") and m.get("away_id") and m["status"] == "scheduled" for m in sfs),
          [(m['id'], m['status']) for m in sfs])
    for m in sfs:
        play(m, 2, 1)
    ms = {m["id"]: m for m in jget(f"/categories/{ob}/matches")}
    final = next(m for m in ms.values() if m["stage"] == "knockout" and m.get("label") == "Final")
    check(sec, "Final received both SF winners",
          final.get("home_id") and final.get("away_id"), (final.get("home_id"), final.get("away_id")))
    play(final, 3, 1)

    # ============================================================ 7. U-23 KNOCKOUT PROGRESSION + EDITS
    sec = "7-ko-edge"
    ms = jget(f"/categories/{GC['u23']}/matches")
    r1 = sorted([m for m in ms if m["round"] == 1], key=lambda m: m["bracket_pos"])
    by_id = {m["id"]: m for m in ms}
    m0 = r1[0]
    # missing-away-score edge: send home only
    api("PUT", f"/matches/{m0['id']}", json={"home_score": 2})
    mm = next(m for m in jget(f"/categories/{GC['u23']}/matches") if m["id"] == m0["id"])
    check(sec, "half-entered score does NOT mark match completed", mm["status"] != "completed", mm["status"])
    # explicit None away with home set (frontend never does this; API allows it?)
    api("PUT", f"/matches/{m0['id']}", json={"home_score": 2, "away_score": None})
    mm = next(m for m in jget(f"/categories/{GC['u23']}/matches") if m["id"] == m0["id"])
    info(sec, "home=2 away=None => status", mm["status"] + " (completed here would be a validation gap)")
    # proper result
    api("PUT", f"/matches/{m0['id']}", json={"home_score": 2, "away_score": 0, "status": "completed"})
    nm = next(m for m in jget(f"/categories/{GC['u23']}/matches") if m["id"] == m0["next_match_id"])
    check(sec, "winner advanced", nm.get(f"{m0['next_slot']}_id") == m0["home_id"])
    # edit result to flip winner -> propagation
    api("PUT", f"/matches/{m0['id']}", json={"home_score": 0, "away_score": 3, "status": "completed"})
    nm = next(m for m in jget(f"/categories/{GC['u23']}/matches") if m["id"] == m0["next_match_id"])
    check(sec, "edited result re-propagates new winner", nm.get(f"{m0['next_slot']}_id") == m0["away_id"],
          nm.get(f"{m0['next_slot']}_id"))
    # clear the result -> slot resets, next match pending
    api("PUT", f"/matches/{m0['id']}", json={"home_score": None, "away_score": None, "status": "scheduled"})
    nm = next(m for m in jget(f"/categories/{GC['u23']}/matches") if m["id"] == m0["next_match_id"])
    check(sec, "cleared result withdraws team from next round; next is pending",
          nm.get(f"{m0['next_slot']}_id") is None and nm["status"] == "pending",
          (nm.get(f"{m0['next_slot']}_id"), nm["status"]))
    # draw in knockout: what happens?
    api("PUT", f"/matches/{m0['id']}", json={"home_score": 1, "away_score": 1, "status": "completed"})
    nm = next(m for m in jget(f"/categories/{GC['u23']}/matches") if m["id"] == m0["next_match_id"])
    slot_key = m0["next_slot"] + "_id"
    info(sec, "KO draw handling", f"next slot = {nm.get(slot_key)} "
         "(None = no winner advanced; app has no tiebreak/penalties concept)")
    # full run-through R16->QF->SF->F
    api("PUT", f"/matches/{m0['id']}", json={"home_score": 2, "away_score": 0, "status": "completed"})
    ms = jget(f"/categories/{GC['u23']}/matches")
    for rnd in (1, 2, 3, 4):
        for m in [x for x in ms if x["round"] == rnd]:
            cur = next(y for y in jget(f"/categories/{GC['u23']}/matches") if y["id"] == m["id"])
            if cur.get("home_id") and cur.get("away_id") and cur.get("home_score") is None:
                api("PUT", f"/matches/{cur['id']}", json={"home_score": 1, "away_score": 0, "status": "completed"})
    final = next(m for m in jget(f"/categories/{GC['u23']}/matches") if m.get("label") == "Final")
    check(sec, "Final resolved after full progressive entry",
          final.get("home_id") and final.get("away_id") and final.get("home_score") is not None,
          (final.get("home_id"), final.get("away_id"), final.get("status")))

    # ============================================================ 8. REGENERATION / STALENESS
    sec = "8-regen"
    vet = GC["vet"]
    before = jget(f"/categories/{vet}/matches")
    before_ids = {m["id"] for m in before}
    m0 = next((m for m in before if m.get("date")), before[0])
    api("PUT", f"/matches/{m0['id']}", json={"home_score": 4, "away_score": 2, "status": "completed"})
    r = api("POST", f"/categories/{vet}/generate-fixtures")
    check(sec, "regenerate ok", r.status_code == 200)
    after = jget(f"/categories/{vet}/matches")
    check(sec, "old matches replaced (no stale ids)", not (before_ids & {m["id"] for m in after}))
    check(sec, "regenerated fixtures are unscheduled", all(not m.get("date") for m in after))
    check(sec, "regenerated fixtures have no scores", all(m.get("home_score") is None for m in after))
    st = jget(f"/categories/{vet}/standings")["standings"]
    check(sec, "standings reset after regeneration", all(r["played"] == 0 for r in st))
    sched = jget(f"/tournaments/{tid}/schedule")
    check(sec, "master schedule contains no stale Veterans rows",
          not any(m["category_id"] == vet for m in sched))
    # regen with a locked match: lock one, regen, see what remains
    api("PUT", f"/matches/{after[0]['id']}", json={"locked": True})
    api("POST", f"/categories/{vet}/generate-fixtures")
    after2 = jget(f"/categories/{vet}/matches")
    dup_pairs = defaultdict(int)
    for m in after2:
        dup_pairs[tuple(sorted([m["home_id"], m["away_id"]]))] += 1
    dups = {k: v for k, v in dup_pairs.items() if v > 2}   # double league: each pair twice is normal
    info(sec, "regen with a locked match kept", f"{len(after2)} matches after regen (30 fresh + kept locked)")
    check(sec, "regen with locked match: no pairing appears more often than the format allows",
          not dups, f"{len(dups)} pairings duplicated — locked old fixture kept alongside a full new set")
    # unlock whatever is locked and regenerate clean for UI use
    for m in after2:
        if m.get("locked"):
            api("PUT", f"/matches/{m['id']}", json={"locked": False})
    api("POST", f"/categories/{vet}/generate-fixtures")

    # ============================================================ 9. INTENTIONAL INFEASIBILITY A-F
    sec = "9-infeasible"
    def expect_unscheduled(name, build):
        t = mk_tour(f"TEST_QA_{name}", "2026-11-01", "2026-11-01")
        try:
            cid = build(t)
            api("POST", f"/categories/{cid}/generate-fixtures")
            r = api("POST", f"/tournaments/{t}/auto-schedule")
            if not check(sec, f"{name}: scheduler returns 200 (no crash)", r.status_code == 200, r.text[:200]):
                return
            d = r.json()
            check(sec, f"{name}: reports unscheduled matches", d["unscheduled"] > 0,
                  f"scheduled={d['scheduled']}")
            types = {c["type"] for c in d["conflicts"]}
            check(sec, f"{name}: capacity + per-match diagnostics",
                  "capacity" in types and "unplaced_match" in types, types)
            check(sec, f"{name}: suggestions offered", len(d.get("suggestions", [])) > 0)
            info(sec, f"{name}: sample reason",
                 next((c["message"] for c in d["conflicts"] if c["type"] == "unplaced_match"), "-"))
            # whatever WAS scheduled must still be valid (no silent invalid schedule)
            ms = jget(f"/tournaments/{t}/schedule")
            by_gd = defaultdict(list)
            bad = []
            for m in ms:
                s = parse_t(m["time"])
                for (s2, id2) in by_gd[(m["date"], m["ground_id"])]:
                    if abs(s - s2) < 30:
                        bad.append((m["id"], id2))
                by_gd[(m["date"], m["ground_id"])].append((s, m["id"]))
            check(sec, f"{name}: placed matches remain conflict-free", not bad, bad)
        finally:
            pass  # cleaned centrally

    def build_A(t):
        g = mk_ground(t, "onlyg")
        cid = mk_cat(t, "A", "league_single",
                     {"start_date": "2026-11-01", "end_date": "2026-11-01",
                      "earliest_time": "09:00", "latest_time": "11:00",
                      "match_duration_minutes": 60, "slot_gap_minutes": 15}, [g])
        for i in range(4):
            mk_team(cid, f"A{i}")
        return cid
    expect_unscheduled("A-ground-capacity", build_A)

    def build_B(t):
        g = mk_ground(t, "gB")
        cid = mk_cat(t, "B", "league_single",
                     {"start_date": "2026-11-01", "end_date": "2026-11-01",
                      "match_duration_minutes": 60, "slot_gap_minutes": 0,
                      "min_rest_minutes": 0}, [g])
        mk_team(cid, "B-narrow", available_from="10:00", available_to="11:00")
        for i in range(3):
            mk_team(cid, f"B{i}")
        return cid
    expect_unscheduled("B-team-1hr-window", build_B)

    def build_C(t):
        g = mk_ground(t, "gC")
        cid = mk_cat(t, "C", "league_single",
                     {"start_date": "2026-11-01", "end_date": "2026-11-01",
                      "match_duration_minutes": 60, "slot_gap_minutes": 15,
                      "min_rest_minutes": 600}, [g])
        for i in range(4):
            mk_team(cid, f"C{i}")
        return cid
    expect_unscheduled("C-impossible-rest", build_C)

    def build_E(t):
        g = mk_ground(t, "gE")
        cid = mk_cat(t, "E", "league_single",
                     {"start_date": "2026-11-01", "end_date": "2026-11-01",
                      "match_duration_minutes": 60, "slot_gap_minutes": 15,
                      "max_matches_per_day": 2}, [g])
        for i in range(4):
            mk_team(cid, f"E{i}")
        return cid
    expect_unscheduled("E-max-per-day", build_E)

    def build_F(t):
        g = mk_ground(t, "gF")
        cid = mk_cat(t, "F", "league_double",
                     {"start_date": "2026-11-01", "end_date": "2026-11-01",
                      "match_duration_minutes": 90, "slot_gap_minutes": 30}, [g])
        for i in range(6):
            mk_team(cid, f"F{i}")
        return cid
    expect_unscheduled("F-insufficient-days", build_F)

    # D: category restricted to a ground id that doesn't exist
    tD = mk_tour("TEST_QA_D-bad-ground", "2026-11-01", "2026-11-01")
    gD = mk_ground(tD, "realg")
    cidD = mk_cat(tD, "D", "league_single",
                  {"start_date": "2026-11-01", "end_date": "2026-11-01",
                   "match_duration_minutes": 60, "slot_gap_minutes": 15}, ["no-such-ground-id"])
    for i in range(4):
        mk_team(cidD, f"D{i}")
    api("POST", f"/categories/{cidD}/generate-fixtures")
    r = api("POST", f"/tournaments/{tD}/auto-schedule")
    d = r.json()
    placedD = jget(f"/tournaments/{tD}/schedule")
    if placedD:
        info(sec, "D-inaccessible-ground",
             f"category restricted to a NONEXISTENT ground silently fell back to all grounds "
             f"({len(placedD)} matches placed on '{placedD[0]['ground_id']}') — silent fallback, no warning")
        check(sec, "D: restricting to unavailable ground should not silently use other grounds", False,
              "engine falls back to all tournament grounds when ground_ids resolve to nothing")
    else:
        check(sec, "D: unschedulable + diagnostics", d["unscheduled"] > 0 and d.get("suggestions"))

    # ============================================================ 10. CRUD & DATA INTEGRITY
    sec = "10-integrity"
    t = mk_tour("TEST_QA_crud", "2026-12-01", "2026-12-02")
    g = mk_ground(t, "gX")
    cid = mk_cat(t, "X", "league_single",
                 {"start_date": "2026-12-01", "end_date": "2026-12-02"}, [g])
    ids = [mk_team(cid, f"X{i}") for i in range(4)]
    r = api("POST", f"/categories/{cid}/generate-fixtures")
    check(sec, "fixtures ok", r.status_code == 200)
    # delete a team that has fixtures
    api("DELETE", f"/teams/{ids[0]}")
    ms = jget(f"/categories/{cid}/matches")
    orphan = [m["id"] for m in ms if ids[0] in (m.get("home_id"), m.get("away_id"))]
    check(sec, "deleting a team does not leave orphaned fixtures", not orphan,
          f"{len(orphan)} matches still reference the deleted team (dangling team_id)")
    # <2 teams guard
    cid2 = mk_cat(t, "X2", "league_single", {}, [g])
    mk_team(cid2, "lonely")
    r = api("POST", f"/categories/{cid2}/generate-fixtures")
    check(sec, "generate with <2 teams rejected with 400", r.status_code == 400, r.status_code)
    # team into nonexistent category
    r = api("POST", "/categories/does-not-exist/teams", json={"name": "ghost"})
    check(sec, "team into missing category -> 404", r.status_code == 404, r.status_code)
    # arbitrary junk into match update (no validation model)
    ms = jget(f"/categories/{cid}/matches")
    r = api("PUT", f"/matches/{ms[0]['id']}", json={"tournament_id": "HIJACKED", "junk_field": 1,
                                                    "date": "not-a-date"})
    m = next(x for x in jget(f"/categories/{cid}/matches") if x["id"] == ms[0]["id"])
    check(sec, "PUT /matches rejects junk / protected fields", not (
        m.get("tournament_id") == "HIJACKED" or "junk_field" in m or m.get("date") == "not-a-date"),
        f"stored: tournament_id={m.get('tournament_id')}, junk_field={'junk_field' in m}, date={m.get('date')}")
    # delete category cascades matches+teams
    api("DELETE", f"/categories/{cid}")
    left = jget(f"/categories/{cid}/matches")
    check(sec, "category delete cascades matches", left == [], len(left))
    # delete tournament cascades everything
    api("DELETE", f"/tournaments/{t}")
    check(sec, "tournament delete cascades grounds",
          jget(f"/tournaments/{t}/grounds") == [])
    # referee CRUD
    sec = "10-referees"
    rid = GC["refs"][0]
    r = api("PUT", f"/referees/{rid}", json={"max_matches_per_day": 1, "certification": "FIFA Elite"})
    check(sec, "referee update ok", r.status_code == 200 and r.json()["max_matches_per_day"] == 1)
    r = api("DELETE", f"/referees/{GC['refs'][-1]}")
    check(sec, "referee delete ok", r.status_code == 200)
    check(sec, "referee list reflects delete", len(jget(f"/tournaments/{tid}/referees")) == 9)
    all_ms = jget(f"/tournaments/{tid}/schedule")
    assigned = [m for m in all_ms if m.get("referee_id")]
    info(sec, "referee auto-assignment classification",
         f"{len(assigned)}/{len(all_ms)} scheduled matches have a referee -> "
         + ("IMPLEMENTED" if assigned else "NOT IMPLEMENTED (matches handoff backlog P1)"))

    # broken bracket links across the whole grand tournament
    sec = "10-links"
    bad_links = []
    for c in jget(f"/tournaments/{tid}/categories"):
        ms = jget(f"/categories/{c['id']}/matches")
        by_id = {m["id"] for m in ms}
        for m in ms:
            if m.get("next_match_id") and m["next_match_id"] not in by_id:
                bad_links.append((c["name"], m["id"]))
    check(sec, "no bracket links point to missing matches", not bad_links, bad_links[:5])
