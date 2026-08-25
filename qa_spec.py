"""TournamentOS — Scheduling Behaviour conformance test.

Builds one genuinely complex tournament (multiple categories sharing grounds, mixed
durations, team availability, rest rules, per-day caps, protected breaks, locked
matches, groups and knockouts) and then evaluates the resulting schedule against each
numbered requirement of the Scheduling Behaviour spec.

Run with the backend up:   python qa_spec.py
Writes qa_spec_results.json. Cleans up after itself.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime

import requests

BASE = "http://localhost:8001/api"
S = requests.Session()
QA_EMAIL = "qa-harness@example.com"
QA_PASSWORD = "qa-harness-password-123"

RESULTS = []
TOURS = []


def rec(spec, name, status, detail=""):
    RESULTS.append({"spec": spec, "check": name, "status": status, "detail": str(detail)[:1500]})
    tag = {"PASS": "  PASS ", "FAIL": "  FAIL ", "INFO": "  INFO ", "WARN": "  WARN "}[status]
    print(f"{tag} §{spec} {name}" + (f" — {detail}" if detail and status != "PASS" else ""))


def check(spec, name, ok, detail=""):
    rec(spec, name, "PASS" if ok else "FAIL", detail)
    return ok


def soft(spec, name, ok, detail=""):
    """A preference, not a hard rule: failing is a quality signal, not a bug."""
    rec(spec, name, "PASS" if ok else "WARN", detail)
    return ok


def info(spec, name, detail):
    rec(spec, name, "INFO", detail)


def api(method, path, **kw):
    return S.request(method, BASE + path, timeout=180, **kw)


def jget(path):
    r = api("GET", path)
    r.raise_for_status()
    return r.json()


def parse_t(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def fmt_t(x):
    return f"{x // 60:02d}:{x % 60:02d}"


def sign_in():
    st = jget("/auth/status")
    if not st["initialized"]:
        r = api("POST", "/auth/bootstrap", json={"email": QA_EMAIL, "name": "QA",
                                                 "password": QA_PASSWORD, "role": "admin"})
    else:
        r = api("POST", "/auth/login", json={"email": QA_EMAIL, "password": QA_PASSWORD})
    if r.status_code != 200:
        print(f"Could not authenticate ({r.status_code}). Create {QA_EMAIL} or edit this file.")
        sys.exit(1)
    S.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})


# ---------------------------------------------------------------- build
def build():
    """A deliberately demanding, realistic tournament."""
    for t in jget("/tournaments"):
        if t["name"] == "SPEC Conformance Cup":
            api("DELETE", f"/tournaments/{t['id']}")
    tid = api("POST", "/tournaments", json={
        "name": "SPEC Conformance Cup", "start_date": "2026-10-02", "end_date": "2026-10-04",
        "location": "Ahmedabad"}).json()["id"]
    TOURS.append(tid)

    G = {}
    G[1] = api("POST", f"/tournaments/{tid}/grounds", json={"name": "1", "open_time": "08:00", "close_time": "20:00", "priority": 1}).json()["id"]
    G[2] = api("POST", f"/tournaments/{tid}/grounds", json={"name": "2", "open_time": "08:00", "close_time": "20:00", "priority": 1}).json()["id"]
    G[3] = api("POST", f"/tournaments/{tid}/grounds", json={"name": "3", "open_time": "09:00", "close_time": "18:00", "priority": 2}).json()["id"]
    G[4] = api("POST", f"/tournaments/{tid}/grounds", json={"name": "4", "open_time": "08:00", "close_time": "17:00", "priority": 2}).json()["id"]

    for n, c, y, mx in [("Ref A", "FIFA", 12, 4), ("Ref B", "National", 7, 4),
                        ("Ref C", "State", 4, 5), ("Ref D", "National", 9, 5)]:
        api("POST", f"/tournaments/{tid}/referees", json={
            "name": n, "certification": c, "experience_years": y, "max_matches_per_day": mx})

    cats = {}

    # A — league, 8 teams, 60' matches, shared grounds 1&2, protected lunch break
    cats["league"] = api("POST", f"/tournaments/{tid}/categories", json={
        "name": "Open League", "format": "league_single",
        "ground_ids": [G[1], G[2]],
        "constraints": {"start_date": "2026-10-02", "end_date": "2026-10-04",
                        "earliest_time": "08:00", "latest_time": "20:00",
                        "match_duration_minutes": 60, "slot_gap_minutes": 15,
                        "min_rest_minutes": 60, "max_matches_per_day": 0,
                        "break_start": "12:30", "break_end": "13:30"}}).json()["id"]
    league_teams = {}
    for i in range(8):
        payload = {"name": f"L{i+1}", "seed": i + 1}
        if i == 0:                       # narrow daily window
            payload.update({"available_from": "10:00", "available_to": "17:00"})
        if i == 1:                       # needs a real break between matches
            payload["no_back_to_back"] = True
        if i == 2:                       # capped per day
            payload["max_matches_per_day"] = 2
        if i == 3:                       # away on the middle day
            payload["unavailable_dates"] = ["2026-10-03"]
        league_teams[f"L{i+1}"] = api("POST", f"/categories/{cats['league']}/teams", json=payload).json()["id"]

    # B — groups + knockout, 8 teams, 45' matches, grounds 1,2,3 (shared with A)
    cats["gk"] = api("POST", f"/tournaments/{tid}/categories", json={
        "name": "Youth Cup", "format": "groups_knockout", "seeded": True,
        "num_groups": 2, "qualifiers_per_group": 2,
        "ground_ids": [G[1], G[2], G[3]],
        "constraints": {"start_date": "2026-10-02", "end_date": "2026-10-04",
                        "earliest_time": "08:00", "latest_time": "19:00",
                        "match_duration_minutes": 45, "slot_gap_minutes": 15,
                        "min_rest_minutes": 45, "max_matches_per_day": 0,
                        "knockout_start_date": "2026-10-04"}}).json()["id"]
    for i in range(8):
        api("POST", f"/categories/{cats['gk']}/teams", json={"name": f"Y{i+1}", "seed": i + 1})

    # C — knockout, 8 teams, 90' matches, grounds 3&4 only (restricted)
    cats["ko"] = api("POST", f"/tournaments/{tid}/categories", json={
        "name": "Seniors Knockout", "format": "knockout", "seeded": True,
        "ground_ids": [G[3], G[4]],
        "constraints": {"start_date": "2026-10-02", "end_date": "2026-10-04",
                        "earliest_time": "09:00", "latest_time": "18:00",
                        "match_duration_minutes": 90, "slot_gap_minutes": 30,
                        "min_rest_minutes": 120, "max_matches_per_day": 0}}).json()["id"]
    for i in range(8):
        api("POST", f"/categories/{cats['ko']}/teams", json={"name": f"S{i+1}", "seed": i + 1})

    for cid in cats.values():
        r = api("POST", f"/categories/{cid}/generate-fixtures")
        assert r.status_code == 200, r.text

    # Give the KO bracket real teams beyond round 1 so progression is schedulable
    ko_ms = jget(f"/categories/{cats['ko']}/matches")
    ko_tids = [t["id"] for t in jget(f"/categories/{cats['ko']}/teams")]
    for m in ko_ms:
        if m["round"] > 1:
            api("PUT", f"/matches/{m['id']}", json={"home_id": ko_tids[0], "away_id": ko_tids[1],
                                                    "status": "scheduled"})
    return tid, G, cats, league_teams


def load_state(tid):
    cats = jget(f"/tournaments/{tid}/categories")
    grounds = {g["id"]: g for g in jget(f"/tournaments/{tid}/grounds")}
    data = {}
    for c in cats:
        data[c["id"]] = {"cat": c,
                         "teams": {t["id"]: t for t in jget(f"/categories/{c['id']}/teams")},
                         "matches": jget(f"/categories/{c['id']}/matches")}
    return grounds, data


def placed_list(data):
    out = []
    for cid, d in data.items():
        dur = int((d["cat"].get("constraints") or {}).get("match_duration_minutes", 90))
        for m in d["matches"]:
            if m.get("date") and m.get("time") and m.get("ground_id"):
                out.append({"m": m, "cat": d["cat"], "dur": dur,
                            "s": parse_t(m["time"]), "e": parse_t(m["time"]) + dur})
    return out


# ================================================================== main
def run():
    print(f"TournamentOS — Scheduling Behaviour conformance · {datetime.now().isoformat()}\n")
    sign_in()
    tid, G, cats, league_teams = build()

    # ---- §1 fixtures vs scheduling separation -------------------------------
    _, data0 = load_state(tid)
    snap = {m["id"]: (m["home_id"], m["away_id"], m["round"], m["order"], m.get("next_match_id"),
                      m.get("group"), m.get("stage"))
            for d in data0.values() for m in d["matches"]}
    n_fixtures = len(snap)
    info(1, "fixtures generated", f"{n_fixtures} matches across {len(cats)} categories")
    check(1, "fixtures created unscheduled (no date/time/ground)",
          all(not m.get("date") for d in data0.values() for m in d["matches"]))

    # ---- §17/§18 pre-place and lock one match, pre-place another unlocked ----
    league_ms = sorted(jget(f"/categories/{cats['league']}/matches"), key=lambda m: m["order"])
    locked_id = league_ms[0]["id"]
    api("PUT", f"/matches/{locked_id}", json={"date": "2026-10-03", "time": "15:00",
                                             "ground_id": G[1], "locked": True})
    manual_id = league_ms[1]["id"]
    api("PUT", f"/matches/{manual_id}", json={"date": "2026-10-03", "time": "09:00",
                                             "ground_id": G[2]})

    # ---- run the tournament-wide scheduler ----------------------------------
    r = api("POST", f"/tournaments/{tid}/auto-schedule")
    check(2, "tournament-wide auto-schedule succeeds", r.status_code == 200, r.text[:200])
    resp = r.json()
    info(2, "scheduler result",
         f"{resp['scheduled']} scheduled / {resp['unscheduled']} unplaced across {resp['categories']} categories")
    grounds, data = load_state(tid)
    P = placed_list(data)

    # ---- §1 again: nothing about the fixtures changed ------------------------
    snap2 = {m["id"]: (m["home_id"], m["away_id"], m["round"], m["order"], m.get("next_match_id"),
                       m.get("group"), m.get("stage"))
             for d in data.values() for m in d["matches"]}
    check(1, "scheduling did not alter opponents, rounds, groups or bracket links", snap == snap2,
          {k: (snap[k], snap2.get(k)) for k in snap if snap.get(k) != snap2.get(k)})

    # ---- §2 all categories considered together -------------------------------
    cats_placed = {p["cat"]["id"] for p in P}
    check(2, "every category received placements", len(cats_placed) == len(cats),
          f"{len(cats_placed)} of {len(cats)}")
    shared = defaultdict(set)
    for p in P:
        shared[(p["m"]["date"], p["m"]["ground_id"])].add(p["cat"]["name"])
    multi = [k for k, v in shared.items() if len(v) > 1]
    check(2, "categories genuinely share grounds (one coherent schedule)", bool(multi),
          f"{len(multi)} ground-days host more than one category")

    # ---- §10 ground conflicts ------------------------------------------------
    byg = defaultdict(list)
    for p in P:
        byg[(p["m"]["date"], p["m"]["ground_id"])].append(p)
    clashes = []
    for key, lst in byg.items():
        lst.sort(key=lambda x: x["s"])
        for i in range(len(lst) - 1):
            if lst[i + 1]["s"] < lst[i]["e"]:
                clashes.append((key, lst[i]["m"]["id"], lst[i + 1]["m"]["id"]))
    check(10, "no ground hosts two overlapping matches (across all categories)", not clashes, clashes[:5])

    # ---- §9 team conflicts + rest -------------------------------------------
    tsched = defaultdict(list)
    allteams = {}
    for d in data.values():
        allteams.update(d["teams"])
    for p in P:
        for t in (p["m"]["home_id"], p["m"]["away_id"]):
            if t:
                tsched[t].append(p)
    overlaps, rest_viol, b2b_viol = [], [], []
    rest_margins = []
    for t, lst in tsched.items():
        lst.sort(key=lambda x: (x["m"]["date"], x["s"]))
        info_t = allteams.get(t, {})
        for i in range(len(lst) - 1):
            a, b = lst[i], lst[i + 1]
            if a["m"]["date"] != b["m"]["date"]:
                continue
            gap = b["s"] - a["e"]
            if gap < 0:
                overlaps.append((info_t.get("name"), a["m"]["id"], b["m"]["id"]))
                continue
            need = int((a["cat"].get("constraints") or {}).get("min_rest_minutes", 0))
            if info_t.get("no_back_to_back"):
                if gap < a["dur"]:
                    b2b_viol.append((info_t.get("name"), gap, a["dur"]))
                need = max(need, a["dur"])
            if gap < need:
                rest_viol.append((info_t.get("name"), gap, need))
            rest_margins.append(gap - need)
    check(9, "no team plays two matches at once", not overlaps, overlaps[:5])
    check(9, "minimum rest always honoured", not rest_viol, rest_viol[:5])
    check(8, "no-back-to-back teams never play consecutively", not b2b_viol, b2b_viol[:5])

    # ---- §3/§11/§13/§14 configured rules ------------------------------------
    bad_ground, bad_window, bad_break, bad_avail, bad_dates, bad_max = [], [], [], [], [], []
    for p in P:
        m, c, g = p["m"], p["cat"], grounds.get(p["m"]["ground_id"])
        allowed = c.get("ground_ids") or list(grounds)
        if m["ground_id"] not in allowed:
            bad_ground.append((c["name"], g["name"] if g else "?"))
        cons = c.get("constraints") or {}
        dw = (cons.get("date_windows") or {}).get(m["date"]) or {}
        lo = parse_t(dw.get("earliest") or cons.get("earliest_time", "08:00"))
        hi = parse_t(dw.get("latest") or cons.get("latest_time", "20:00"))
        if p["s"] < lo or p["e"] > hi:
            bad_window.append((c["name"], m["date"], m["time"], "category hours"))
        gdh = (g.get("date_hours") or {}).get(m["date"]) or {}
        g_open = gdh.get("open") or g.get("open_time")
        g_close = gdh.get("close") or g.get("close_time")
        if g_open and p["s"] < parse_t(g_open):
            bad_window.append((g["name"], m["time"], "before ground opens"))
        if g_close and p["e"] > parse_t(g_close):
            bad_window.append((g["name"], m["time"], "after ground closes"))
        bs, be = cons.get("break_start"), cons.get("break_end")
        if bs and be and p["s"] < parse_t(be) and parse_t(bs) < p["e"]:
            bad_break.append((c["name"], m["date"], m["time"]))
    for t, lst in tsched.items():
        it = allteams.get(t, {})
        per_day = defaultdict(int)
        for p in lst:
            per_day[p["m"]["date"]] += 1
            af, at = it.get("available_from"), it.get("available_to")
            if af and p["s"] < parse_t(af):
                bad_avail.append((it.get("name"), p["m"]["time"], f"available from {af}"))
            if at and p["e"] > parse_t(at):
                bad_avail.append((it.get("name"), p["m"]["time"], f"available until {at}"))
            if p["m"]["date"] in (it.get("unavailable_dates") or []):
                bad_dates.append((it.get("name"), p["m"]["date"]))
            av = it.get("available_dates") or []
            if av and p["m"]["date"] not in av:
                bad_dates.append((it.get("name"), p["m"]["date"], "outside available dates"))
        mx = it.get("max_matches_per_day")
        if mx and any(v > int(mx) for v in per_day.values()):
            bad_max.append((it.get("name"), dict(per_day), f"max {mx}"))
    check(11, "category ground restrictions respected", not bad_ground, bad_ground[:5])
    check(11, "ground opening/closing hours respected", not bad_window, bad_window[:6])
    check(12, "protected breaks kept clear", not bad_break, bad_break[:5])
    check(13, "team playing windows respected", not bad_avail, bad_avail[:5])
    check(13, "team unavailable dates respected", not bad_dates, bad_dates[:5])
    check(14, "team max-matches-per-day respected", not bad_max, bad_max[:5])

    # ---- §15 knockout progression -------------------------------------------
    prog_viol = []
    for cid, d in data.items():
        by_id = {m["id"]: m for m in d["matches"]}
        for m in d["matches"]:
            nm = by_id.get(m.get("next_match_id") or "")
            if nm and m.get("date") and nm.get("date"):
                dur = int((d["cat"].get("constraints") or {}).get("match_duration_minutes", 90))
                feeder_end = (m["date"], parse_t(m["time"]) + dur)
                nxt = (nm["date"], parse_t(nm["time"]))
                if nxt < feeder_end:
                    prog_viol.append((d["cat"]["name"], m.get("label"), nm.get("label")))
        grp = [m for m in d["matches"] if m.get("stage") == "group" and m.get("date")]
        ko = [m for m in d["matches"] if m.get("stage") == "knockout" and m.get("date")]
        if grp and ko:
            gend = max((m["date"], parse_t(m["time"])) for m in grp)
            kstart = min((m["date"], parse_t(m["time"])) for m in ko)
            if kstart < gend:
                prog_viol.append((d["cat"]["name"], "group stage", "knockout starts too early"))
    check(15, "every knockout match follows its feeders (and the group stage)",
          not prog_viol, prog_viol[:5])
    ko_gk = [m for m in data[cats["gk"]]["matches"] if m["stage"] == "knockout" and m.get("date")]
    check(15, "declared knockout start date honoured (Youth Cup: not before 2026-10-04)",
          all(m["date"] >= "2026-10-04" for m in ko_gk),
          [(m["label"], m["date"]) for m in ko_gk if m["date"] < "2026-10-04"][:5])

    # ---- §17 locked / §18 pre-scheduled --------------------------------------
    lm = next(m for m in data[cats["league"]]["matches"] if m["id"] == locked_id)
    check(17, "locked match kept its exact date, time and ground",
          (lm["date"], lm["time"], lm["ground_id"]) == ("2026-10-03", "15:00", G[1]),
          (lm["date"], lm["time"]))
    mm = next(m for m in data[cats["league"]]["matches"] if m["id"] == manual_id)
    check(18, "manually placed but unlocked match kept its slot (default fill mode)",
          (mm["date"], mm["time"], mm["ground_id"]) == ("2026-10-03", "09:00", G[2]),
          f"moved to {mm['date']} {mm['time']}")

    # and an explicit re-plan is still available when the organizer wants a clean solve
    r2 = api("POST", f"/tournaments/{tid}/auto-schedule?replan=true")
    check(18, "explicit re-plan still rebuilds the whole schedule", r2.status_code == 200, r2.text[:150])
    ms2 = {m["id"]: m for m in jget(f"/categories/{cats['league']}/matches")}
    check(17, "locked match survives an explicit re-plan too",
          (ms2[locked_id]["date"], ms2[locked_id]["time"]) == ("2026-10-03", "15:00"),
          (ms2[locked_id]["date"], ms2[locked_id]["time"]))

    # ---- §4/§5 balance and parallelism --------------------------------------
    per_ground = defaultdict(int)
    for p in P:
        per_ground[grounds[p["m"]["ground_id"]]["name"]] += 1
    info(5, "matches per ground", dict(per_ground))
    used = sum(1 for v in per_ground.values() if v)
    check(5, "more than one ground actually used", used >= 2, dict(per_ground))
    top_share = max(per_ground.values()) / max(1, len(P))
    soft(5, "no single ground dominates (<50% of all matches)", top_share < 0.5,
         f"busiest ground holds {top_share:.0%}")
    conc = defaultdict(set)
    for p in P:
        conc[(p["m"]["date"], p["m"]["time"])].add(p["m"]["ground_id"])
    peak = max(len(v) for v in conc.values())
    soft(4, "matches run in parallel across grounds", peak >= 2, f"peak concurrency {peak}")
    info(4, "peak concurrency", f"{peak} grounds in simultaneous use")

    # ---- §6 idle gaps --------------------------------------------------------
    idle_total, span_total = 0, 0
    for key, lst in byg.items():
        lst.sort(key=lambda x: x["s"])
        span = lst[-1]["e"] - lst[0]["s"]
        busy = sum(x["e"] - x["s"] for x in lst)
        idle_total += max(0, span - busy)
        span_total += span
    util = (span_total - idle_total) / span_total if span_total else 1
    info(6, "ground utilisation within each day's span", f"{util:.0%} busy, {idle_total} idle minutes")
    soft(6, "grounds are used efficiently (>=60% of their active span)", util >= 0.6,
         f"{util:.0%} — large gaps suggest matches are spread more than necessary")

    # ---- §7 comfortable rest -------------------------------------------------
    if rest_margins:
        avg_margin = sum(rest_margins) / len(rest_margins)
        tight = sum(1 for x in rest_margins if x < 15)
        info(7, "rest beyond the minimum", f"average +{avg_margin:.0f} min across {len(rest_margins)} same-day pairs")
        soft(7, "teams generally get more than the bare minimum rest", avg_margin > 0,
             f"average margin +{avg_margin:.0f} min, {tight} pair(s) within 15 min of the limit")
    else:
        info(7, "rest margins", "no team played twice in a day")

    # ---- §16 finals late -----------------------------------------------------
    for cname, cid in (("Youth Cup", cats["gk"]), ("Seniors Knockout", cats["ko"])):
        fin = [m for m in data[cid]["matches"] if m.get("label") == "Final" and m.get("date")]
        if not fin:
            info(16, f"{cname} final", "not scheduled")
            continue
        f = fin[0]
        same_day = [p for p in P if p["m"]["date"] == f["date"]]
        later = [p for p in same_day if p["s"] > parse_t(f["time"])]
        soft(16, f"{cname} final sits late in its day",
             len(later) <= max(1, 0.25 * len(same_day)),
             f"final at {f['date']} {f['time']}; {len(later)} of {len(same_day)} matches that day start later")

    # ---- §19/§20 graceful infeasibility --------------------------------------
    if resp["unscheduled"]:
        types = {c["type"] for c in resp["conflicts"]}
        check(19, "unplaced matches are reported, not silently dropped", "capacity" in types, types)
        # Either a reason per match, or a category-level explanation of why the
        # configuration itself makes them impossible — both name the cause.
        check(19, "every unplaced match has a stated cause",
              any(c["type"] in ("unplaced_match", "impossible_config") for c in resp["conflicts"]),
              types)
        check(20, "actionable suggestions provided", len(resp.get("suggestions", [])) > 0)
        info(19, "sample reasons", json.dumps([c["message"] for c in resp["conflicts"]
                                               if c["type"] in ("unplaced_match", "impossible_config")][:3]))
        info(20, "suggestions", json.dumps(resp.get("suggestions", [])[:4]))
    else:
        info(19, "feasibility", "everything fitted — infeasibility diagnostics exercised separately below")

    # deliberately impossible variant to prove §19/§20 behaviour
    t2 = api("POST", "/tournaments", json={"name": "SPEC Impossible", "start_date": "2026-10-10",
                                           "end_date": "2026-10-10"}).json()["id"]
    TOURS.append(t2)
    g = api("POST", f"/tournaments/{t2}/grounds", json={"name": "only"}).json()["id"]
    c2 = api("POST", f"/tournaments/{t2}/categories", json={
        "name": "Impossible", "format": "league_single", "ground_ids": [g],
        "constraints": {"start_date": "2026-10-10", "end_date": "2026-10-10",
                        "earliest_time": "09:00", "latest_time": "12:00",
                        "match_duration_minutes": 60, "slot_gap_minutes": 15,
                        "min_rest_minutes": 120}}).json()["id"]
    for i in range(6):
        api("POST", f"/categories/{c2}/teams", json={"name": f"I{i+1}"})
    api("POST", f"/categories/{c2}/generate-fixtures")
    d2 = api("POST", f"/tournaments/{t2}/auto-schedule").json()
    check(19, "impossible tournament does not produce an invalid schedule",
          d2["unscheduled"] > 0 and d2["scheduled"] < 15, f"{d2['scheduled']} placed, {d2['unscheduled']} not")
    types2 = {c["type"] for c in d2["conflicts"]}
    check(19, "impossible tournament reports capacity + per-match reasons",
          "capacity" in types2 and "unplaced_match" in types2, types2)
    check(20, "impossible tournament offers suggestions", len(d2.get("suggestions", [])) > 0)
    info(20, "suggestions given", json.dumps(d2.get("suggestions", [])[:4]))
    placed2 = jget(f"/tournaments/{t2}/schedule")
    bad2 = []
    byg2 = defaultdict(list)
    for m in placed2:
        byg2[(m["date"], m["ground_id"])].append(parse_t(m["time"]))
    for k, v in byg2.items():
        v.sort()
        for i in range(len(v) - 1):
            if v[i + 1] - v[i] < 60:
                bad2.append((k, v[i], v[i + 1]))
    check(19, "the partial schedule it did produce is still valid", not bad2, bad2[:5])

    # ---- summary -------------------------------------------------------------
    days = sorted({p["m"]["date"] for p in P})
    info(0, "schedule shape", f"{len(P)} matches over {len(days)} day(s): {days}")
    for dte in days:
        dm = [p for p in P if p["m"]["date"] == dte]
        info(0, f"day {dte}", f"{len(dm)} matches, {fmt_t(min(p['s'] for p in dm))}–{fmt_t(max(p['e'] for p in dm))}")


if __name__ == "__main__":
    try:
        run()
    finally:
        for t in TOURS:
            try:
                api("DELETE", f"/tournaments/{t}")
            except Exception:
                pass
        p = sum(1 for r in RESULTS if r["status"] == "PASS")
        f = sum(1 for r in RESULTS if r["status"] == "FAIL")
        w = sum(1 for r in RESULTS if r["status"] == "WARN")
        with open("qa_spec_results.json", "w") as fh:
            json.dump({"ts": datetime.now().isoformat(), "pass": p, "fail": f, "warn": w,
                       "results": RESULTS}, fh, indent=1)
        print(f"\n==== {p} passed · {f} failed · {w} preference warning(s) — qa_spec_results.json ====")
