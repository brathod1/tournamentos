"""TournamentOS — Full-System QA Harness (Part 1: setup + fixture audits + scheduling audit).

Run with the backend up:  python qa_test.py
Writes qa_results.json next to this file. Non-destructive to other tournaments.
Leaves 'TournamentOS Grand Championship 2026' in the DB for manual UI inspection.
"""
import json
import sys
import time
from collections import defaultdict
from datetime import datetime

import requests

BASE = "http://localhost:8001/api"
S = requests.Session()
ANON = requests.Session()          # never carries a token — used to probe the auth boundary
QA_EMAIL = "qa-harness@example.com"
QA_PASSWORD = "qa-harness-password-123"

RESULTS = []          # list of {section, check, status, detail}
CREATED_TOURS = []    # temp tournaments to clean up


def check(section, name, ok, detail=""):
    RESULTS.append({"section": section, "check": name,
                    "status": "PASS" if ok else "FAIL", "detail": str(detail)[:2000]})
    print(("  PASS  " if ok else "  FAIL  ") + f"[{section}] {name}" + (f" — {detail}" if (detail and not ok) else ""))
    return ok


def info(section, name, detail):
    RESULTS.append({"section": section, "check": name, "status": "INFO", "detail": str(detail)[:2000]})
    print(f"  INFO  [{section}] {name} — {detail}")


def api(method, path, **kw):
    r = S.request(method, BASE + path, timeout=120, **kw)
    return r


def anon(method, path, **kw):
    """Request with no credentials at all."""
    return ANON.request(method, BASE + path, timeout=60, **kw)


def sign_in():
    """Ensure the harness is authenticated; bootstraps the first admin if needed."""
    st = jget("/auth/status")
    if not st["initialized"]:
        r = api("POST", "/auth/bootstrap", json={
            "email": QA_EMAIL, "name": "QA Harness", "password": QA_PASSWORD, "role": "admin"})
        r.raise_for_status()
        token = r.json()["access_token"]
    else:
        r = api("POST", "/auth/login", json={"email": QA_EMAIL, "password": QA_PASSWORD})
        if r.status_code != 200:
            print("\n!! Could not sign in as the QA account.\n"
                  f"   Create it in the app (email {QA_EMAIL}, password {QA_PASSWORD})\n"
                  "   via Account -> Add Account, or edit QA_EMAIL/QA_PASSWORD at the top of this file.\n"
                  f"   Server said: {r.status_code} {r.text[:200]}")
            sys.exit(1)
        token = r.json()["access_token"]
    S.headers.update({"Authorization": f"Bearer {token}"})


def jget(path):
    r = api("GET", path)
    r.raise_for_status()
    return r.json()


def parse_t(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------- setup helpers
def mk_tour(name, start, end, temp=True):
    r = api("POST", "/tournaments", json={"name": name, "start_date": start, "end_date": end,
                                          "location": "Ahmedabad", "organizer": "QA Harness"})
    r.raise_for_status()
    tid = r.json()["id"]
    if temp:
        CREATED_TOURS.append(tid)
    return tid


def mk_ground(tid, name, open_time=None, close_time=None, lighting=False, priority=1):
    r = api("POST", f"/tournaments/{tid}/grounds", json={
        "name": name, "open_time": open_time, "close_time": close_time,
        "lighting": lighting, "priority": priority, "surface": "Grass"})
    r.raise_for_status()
    return r.json()["id"]


def mk_ref(tid, name, cert, years, maxpd):
    r = api("POST", f"/tournaments/{tid}/referees", json={
        "name": name, "certification": cert, "experience_years": years, "max_matches_per_day": maxpd})
    r.raise_for_status()
    return r.json()["id"]


def mk_cat(tid, name, fmt, constraints, ground_ids=None, seeded=False,
           num_groups=2, qualifiers=2, points=None):
    payload = {"name": name, "format": fmt, "seeded": seeded, "num_groups": num_groups,
               "qualifiers_per_group": qualifiers, "constraints": constraints,
               "ground_ids": ground_ids or []}
    if points:
        payload["points_config"] = points
    r = api("POST", f"/tournaments/{tid}/categories", json=payload)
    r.raise_for_status()
    return r.json()["id"]


def mk_team(cid, name, **extra):
    r = api("POST", f"/categories/{cid}/teams", json={"name": name, **extra})
    r.raise_for_status()
    return r.json()["id"]


def cleanup():
    for tid in CREATED_TOURS:
        try:
            api("DELETE", f"/tournaments/{tid}")
        except Exception:
            pass
    # remove throwaway accounts created during auth checks (never the QA account itself)
    try:
        for u in jget("/auth/users"):
            if u["email"] in ("weak@example.com", "x@y.com"):
                api("DELETE", f"/auth/users/{u['id']}")
    except Exception:
        pass


# ================================================================ 0. HEALTH
def phase_health():
    sec = "0-health"
    try:
        r = api("GET", "/")
        check(sec, "API root reachable", r.status_code == 200 and r.json().get("status") == "ok", r.text[:200])
    except Exception as e:
        check(sec, "API root reachable", False, e)
        print("Backend not reachable — aborting.")
        sys.exit(1)
    sign_in()
    check(sec, "authenticated as QA account", "Authorization" in S.headers)


# ================================================================ 0b. AUTH BOUNDARY
def phase_auth():
    """The security contract: reads are public, writes need a token, PII is protected."""
    sec = "0b-auth"
    me = jget("/auth/me")
    check(sec, "/auth/me returns the signed-in user", me.get("email") == QA_EMAIL, me)
    check(sec, "password hash never leaves the server", "password_hash" not in me, list(me))

    # --- writes must be rejected without a token ---
    probes = [
        ("POST", "/tournaments", {"name": "HACK", "start_date": "2026-01-01"}),
        ("DELETE", f"/tournaments/{GC.get('tid', 'x')}", None),
        ("POST", f"/tournaments/{GC.get('tid', 'x')}/auto-schedule", None),
        ("POST", f"/categories/{GC.get('u13', 'x')}/generate-fixtures", None),
        ("DELETE", f"/categories/{GC.get('u13', 'x')}/matches", None),
        ("POST", f"/tournaments/{GC.get('tid', 'x')}/grounds", {"name": "HACK"}),
        ("POST", f"/tournaments/{GC.get('tid', 'x')}/referees", {"name": "HACK"}),
    ]
    bad = []
    for method, path, body in probes:
        r = anon(method, path, json=body) if body else anon(method, path)
        if r.status_code != 401:
            bad.append((method, path, r.status_code))
    check(sec, "every write endpoint rejects anonymous callers with 401", not bad, bad)

    # nothing was actually created by those probes
    names = [t["name"] for t in anon("GET", "/tournaments").json()]
    check(sec, "anonymous write attempts changed nothing", "HACK" not in names)

    # --- public reads still work ---
    for path in (f"/tournaments/{GC['tid']}", f"/tournaments/{GC['tid']}/categories",
                 f"/tournaments/{GC['tid']}/schedule", f"/categories/{GC['u13']}/matches",
                 f"/categories/{GC['u13']}/standings", f"/tournaments/{GC['tid']}/conflicts"):
        r = anon("GET", path)
        if not check(sec, f"public read works: {path.split('/')[-1]}", r.status_code == 200, r.status_code):
            break

    # --- PII is stripped for anonymous readers ---
    a_refs = anon("GET", f"/tournaments/{GC['tid']}/referees").json()
    s_refs = jget(f"/tournaments/{GC['tid']}/referees")
    check(sec, "referee phone numbers hidden from anonymous readers",
          all("phone" not in r for r in a_refs) and any("phone" in r for r in s_refs))
    check(sec, "referee names still visible publicly (needed on fixture lists)",
          all(r.get("name") for r in a_refs))
    a_teams = anon("GET", f"/categories/{GC['u13']}/teams").json()
    check(sec, "team contact details hidden from anonymous readers",
          all("contact" not in t for t in a_teams))

    # --- admin-only surface ---
    check(sec, "user list requires auth", anon("GET", "/auth/users").status_code == 401)
    r = anon("POST", "/auth/bootstrap", json={"email": "x@y.com", "name": "X", "password": "password123"})
    check(sec, "bootstrap blocked once an account exists (409)", r.status_code == 409, r.status_code)

    # --- token handling ---
    bad_tok = requests.get(BASE + "/auth/me", headers={"Authorization": "Bearer not-a-real-token"}, timeout=30)
    check(sec, "garbage token rejected with 401", bad_tok.status_code == 401, bad_tok.status_code)
    r = api("POST", "/auth/login", json={"email": QA_EMAIL, "password": "wrong-password"})
    check(sec, "wrong password rejected with 401", r.status_code == 401, r.status_code)
    check(sec, "login error does not reveal whether the email exists",
          "password" in r.text.lower() and "not found" not in r.text.lower(), r.text[:120])
    r = api("POST", "/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    check(sec, "unknown email gives the same 401", r.status_code == 401, r.status_code)
    r = api("POST", "/auth/users", json={"email": "weak@example.com", "name": "W", "password": "short"})
    check(sec, "weak password rejected (422)", r.status_code == 422, r.status_code)
    r = api("POST", "/auth/users", json={"email": "not-an-email", "name": "W", "password": "password123"})
    check(sec, "malformed email rejected (422)", r.status_code == 422, r.status_code)


# ================================================================ 1. BUILD GRAND CHAMPIONSHIP
GC = {}  # ids live here


def phase_build():
    sec = "1-build"
    # remove any previous run of the grand tournament
    for t in jget("/tournaments"):
        if t["name"] == "TournamentOS Grand Championship 2026":
            api("DELETE", f"/tournaments/{t['id']}")
    tid = mk_tour("TournamentOS Grand Championship 2026", "2026-09-05", "2026-09-06", temp=False)
    GC["tid"] = tid

    g = {}
    g[1] = mk_ground(tid, "1", "08:00", "20:00", True, 1)
    g[2] = mk_ground(tid, "2", "09:00", "20:00", True, 1)
    g[3] = mk_ground(tid, "3", "08:00", "18:00", False, 2)
    g[4] = mk_ground(tid, "4", "10:00", "22:00", True, 2)
    g[5] = mk_ground(tid, "5", "08:00", "16:00", False, 3)
    # Ground 3 is unavailable on the Sunday; Ground 2 opens late on the Saturday.
    api("PUT", f"/grounds/{g[3]}", json={"date_hours": {"2026-09-06": {"closed": True}}})
    api("PUT", f"/grounds/{g[2]}", json={"date_hours": {"2026-09-05": {"open": "18:00", "close": "22:00"}}})
    GC["g"] = g
    check(sec, "5 grounds created", len(jget(f"/tournaments/{tid}/grounds")) == 5)

    refs = [("R. Sharma", "FIFA", 12, 3), ("A. Patel", "National", 8, 4), ("K. Desai", "State", 5, 3),
            ("M. Shah", "National", 10, 2), ("P. Joshi", "State", 3, 5), ("V. Mehta", "FIFA", 15, 3),
            ("S. Trivedi", "District", 2, 6), ("N. Vyas", "State", 6, 3), ("H. Bhatt", "National", 9, 4),
            ("D. Raval", "District", 1, 4)]
    GC["refs"] = [mk_ref(tid, *r) for r in refs]
    check(sec, "10 referees created", len(jget(f"/tournaments/{tid}/referees")) == 10)

    # ---- Category 1: U-13 League (league_single, 8 teams) ----
    u13 = mk_cat(tid, "U-13 League", "league_single", {
        "start_date": "2026-09-05", "end_date": "2026-09-06",
        "earliest_time": "08:00", "latest_time": "18:00",
        "match_duration_minutes": 60, "slot_gap_minutes": 15,
        "min_rest_minutes": 60, "max_matches_per_day": 0,
        "break_start": "12:30", "break_end": "14:00",
        # Sat 5 Sep is an evening-only session; Sun 6 Sep uses the default window.
        "date_windows": {"2026-09-05": {"earliest": "16:00", "latest": "22:00"}},
    }, ground_ids=[g[1], g[2], g[3]])
    GC["u13"] = u13
    u13_names = ["Ahmedabad United", "Baroda FC", "Surat Strikers", "Gandhinagar City",
                 "Anand Athletic", "Rajkot Rangers", "Vadodara Warriors", "Mehsana FC"]
    tmap = {}
    for i, n in enumerate(u13_names):
        extra = {"seed": i + 1}
        if n == "Ahmedabad United":
            extra["available_from"] = "10:00"
        if n == "Baroda FC":
            extra["no_back_to_back"] = True
        if n == "Mehsana FC":
            extra["available_to"] = "17:00"
        tmap[n] = mk_team(u13, n, **extra)
    GC["u13_teams"] = tmap

    # ---- Category 2: Open Boys (groups_knockout, 12 teams, 4 groups, top2) ----
    ob = mk_cat(tid, "Open Boys", "groups_knockout", {
        "start_date": "2026-09-05", "end_date": "2026-09-06",
        "earliest_time": "09:00", "latest_time": "19:00",
        "match_duration_minutes": 45, "slot_gap_minutes": 15,
        "min_rest_minutes": 45, "max_matches_per_day": 0,
    }, ground_ids=[g[1], g[2], g[4]], seeded=True, num_groups=4, qualifiers=2,
        points={"win": 2, "draw": 1, "loss": 0,
                "tiebreakers": ["points", "goal_difference", "goals_for", "wins"]})
    GC["ob"] = ob
    ob_names = [f"OB Club {i:02d}" for i in range(1, 13)]
    obmap = {}
    for i, n in enumerate(ob_names):
        extra = {"seed": i + 1}
        if i == 10:                                # OB Club 11: Saturday only
            extra["available_dates"] = ["2026-09-05"]
        if i == 11:                                # OB Club 12: not on Sunday
            extra["unavailable_dates"] = ["2026-09-06"]
        obmap[n] = mk_team(ob, n, **extra)
    GC["ob_teams"] = obmap

    # ---- Category 3: U-23 (knockout, 16 teams, seeded) ----
    u23 = mk_cat(tid, "U-23", "knockout", {
        "start_date": "2026-09-05", "end_date": "2026-09-06",
        "earliest_time": "10:00", "latest_time": "20:00",
        "match_duration_minutes": 60, "slot_gap_minutes": 15,
        "min_rest_minutes": 90, "max_matches_per_day": 0,
    }, ground_ids=[g[3], g[4], g[5]], seeded=True)
    GC["u23"] = u23
    u23map = {}
    # deliberately created OUT of seed order — a seeded bracket must honour the seed
    # field, not insertion order (regression guard for the seeding fix)
    for i in list(range(16, 0, -1)):
        n = f"U23 Seed {i:02d}"
        u23map[n] = mk_team(u23, n, seed=i, max_matches_per_day=2)
    GC["u23_teams"] = u23map

    # ---- Category 4: Veterans (league_double, 6 teams) ----
    vet = mk_cat(tid, "Veterans Double League", "league_double", {
        "start_date": "2026-09-05", "end_date": "2026-09-06",
        "earliest_time": "08:00", "latest_time": "20:00",
        "match_duration_minutes": 45, "slot_gap_minutes": 15,
        "min_rest_minutes": 45, "max_matches_per_day": 0,
        "break_start": "12:30", "break_end": "14:00",
    }, ground_ids=[g[1], g[2], g[5]])
    GC["vet"] = vet
    vmap = {}
    for i in range(1, 7):
        n = f"Vets {chr(64+i)}"
        extra = {}
        if i == 1:
            extra["no_back_to_back"] = True
        if i == 2:
            extra["max_matches_per_day"] = 3
        vmap[n] = mk_team(vet, n, **extra)
    GC["vet_teams"] = vmap

    cats = jget(f"/tournaments/{tid}/categories")
    check(sec, "4 categories created", len(cats) == 4)
    check(sec, "42 teams created", sum(c["team_count"] for c in cats) == 42,
          [ (c["name"], c["team_count"]) for c in cats ])


# ================================================================ 2. FIXTURE AUDITS
def audit_round_robin(sec, cid, n_teams, double=False):
    ms = jget(f"/categories/{cid}/matches")
    expected = n_teams * (n_teams - 1) // 2 * (2 if double else 1)
    check(sec, f"match count == {expected}", len(ms) == expected, len(ms))
    pairs = defaultdict(int)
    per_team = defaultdict(int)
    for m in ms:
        key = tuple(sorted([m["home_id"], m["away_id"]]))
        pairs[key] += 1
        per_team[m["home_id"]] += 1
        per_team[m["away_id"]] += 1
    want = 2 if double else 1
    check(sec, f"every pair meets exactly {want}x",
          all(v == want for v in pairs.values()) and len(pairs) == n_teams * (n_teams - 1) // 2,
          {str(k): v for k, v in pairs.items() if v != want})
    check(sec, "every team has the right match count",
          all(v == (n_teams - 1) * want for v in per_team.values()), dict(per_team))
    check(sec, "no self-matches", all(m["home_id"] != m["away_id"] for m in ms))
    check(sec, "fixtures generated unscheduled (no date/time/ground)",
          all(not m.get("date") and not m.get("time") and not m.get("ground_id") for m in ms))
    if double:
        # home/away reversed in the second leg
        legs = defaultdict(list)
        for m in ms:
            legs[tuple(sorted([m["home_id"], m["away_id"]]))].append((m["home_id"], m["away_id"]))
        rev = all(len(v) == 2 and v[0] == (v[1][1], v[1][0]) for v in legs.values())
        check(sec, "double league: legs have reversed home/away", rev)
    return ms


def audit_knockout_bracket(sec, ms, n_real_teams):
    by_id = {m["id"]: m for m in ms}
    rounds = defaultdict(list)
    for m in ms:
        rounds[m["round"]].append(m)
    nround = max(rounds)
    size = 2 ** nround
    check(sec, f"bracket size {size} rounds {nround}",
          all(len(rounds[r]) == size // (2 ** r) for r in rounds), {r: len(v) for r, v in rounds.items()})
    # progression links
    bad_links = [m["id"] for m in ms if m.get("next_match_id") and m["next_match_id"] not in by_id]
    check(sec, "all next_match_id links resolve", not bad_links, bad_links)
    finals = [m for m in ms if not m.get("next_match_id")]
    check(sec, "exactly one match without next (the Final)",
          len(finals) == 1 and finals[0].get("label") == "Final",
          [(m.get("label"), m["round"]) for m in finals])
    # each later-round slot fed by exactly 2 (or has a source)
    feed = defaultdict(list)
    for m in ms:
        if m.get("next_match_id"):
            feed[(m["next_match_id"], m["next_slot"])].append(m["id"])
    dup = {k: v for k, v in feed.items() if len(v) != 1}
    check(sec, "each KO slot fed by exactly one feeder", not dup, dup)
    byes = [m for m in ms if m.get("is_bye") or m.get("status") == "bye"]
    exp_byes = size - n_real_teams
    check(sec, f"bye count == {exp_byes}", len(byes) == exp_byes, len(byes))
    return rounds


def phase_fixtures():
    sec = "2-fixtures"
    # U-13
    r = api("POST", f"/categories/{GC['u13']}/generate-fixtures")
    check(sec, "U-13 generate ok", r.status_code == 200, r.text[:200])
    audit_round_robin(sec + "-u13", GC["u13"], 8)

    # Veterans double
    r = api("POST", f"/categories/{GC['vet']}/generate-fixtures")
    check(sec, "Veterans generate ok", r.status_code == 200, r.text[:200])
    audit_round_robin(sec + "-vet", GC["vet"], 6, double=True)

    # U-23 knockout
    r = api("POST", f"/categories/{GC['u23']}/generate-fixtures")
    check(sec, "U-23 generate ok", r.status_code == 200, r.text[:200])
    ms = jget(f"/categories/{GC['u23']}/matches")
    check(sec + "-u23", "15 matches (8+4+2+1)", len(ms) == 15, len(ms))
    rounds = audit_knockout_bracket(sec + "-u23", ms, 16)
    # seeding honored? classic pairing puts seed1 v seed16 in R1
    teams = jget(f"/categories/{GC['u23']}/teams")
    seed_of = {t["id"]: t.get("seed") for t in teams}
    r1_pairs = sorted([tuple(sorted((seed_of.get(m["home_id"]), seed_of.get(m["away_id"]))))
                       for m in rounds[1]])
    expected_pairs = sorted([tuple(sorted((s, 17 - s))) for s in range(1, 9)])
    check(sec + "-u23", "seeded bracket pairs 1v16 2v15 ... (seed field honored)",
          r1_pairs == expected_pairs, f"got {r1_pairs}")
    check(sec + "-u23", "R2+ slots are TBD (no teams)",
          all(not m.get("home_id") and not m.get("away_id") for m in ms if m["round"] > 1))

    # Open Boys groups+KO
    r = api("POST", f"/categories/{GC['ob']}/generate-fixtures")
    check(sec, "Open Boys generate ok", r.status_code == 200, r.text[:200])
    ms = jget(f"/categories/{GC['ob']}/matches")
    grp = [m for m in ms if m["stage"] == "group"]
    ko = [m for m in ms if m["stage"] == "knockout"]
    check(sec + "-ob", "12 group matches (4 groups x 3)", len(grp) == 12, len(grp))
    check(sec + "-ob", "7 KO matches (QF+SF+F for 8 qualifiers)", len(ko) == 7, len(ko))
    by_group = defaultdict(set)
    for m in grp:
        by_group[m["group"]].add(m["home_id"])
        by_group[m["group"]].add(m["away_id"])
    check(sec + "-ob", "4 groups of 3 teams",
          len(by_group) == 4 and all(len(v) == 3 for v in by_group.values()),
          {k: len(v) for k, v in by_group.items()})
    pair_cnt = defaultdict(int)
    for m in grp:
        pair_cnt[tuple(sorted([m["home_id"], m["away_id"]]))] += 1
    check(sec + "-ob", "no duplicate group fixtures", all(v == 1 for v in pair_cnt.values()))
    srcs = [(m.get("home_source"), m.get("away_source")) for m in ko if m["round"] == 1]
    flat = [s for hs, as_ in srcs for s in (hs, as_) if s]
    check(sec + "-ob", "KO round1 fed by 8 group sources (top2 x 4 groups)",
          len(flat) == 8 and len({(s["group"], s["pos"]) for s in flat}) == 8, flat)
    audit_knockout_bracket(sec + "-ob-ko", ko, 8)


# ================================================================ 3. SCHEDULING AUDIT
def collect_items():
    """Everything needed to independently validate the schedule."""
    tid = GC["tid"]
    cats = jget(f"/tournaments/{tid}/categories")
    grounds = {g["id"]: g for g in jget(f"/tournaments/{tid}/grounds")}
    data = {}
    for c in cats:
        teams = {t["id"]: t for t in jget(f"/categories/{c['id']}/teams")}
        ms = jget(f"/categories/{c['id']}/matches")
        data[c["id"]] = {"cat": c, "teams": teams, "matches": ms}
    return cats, grounds, data


def phase_schedule():
    sec = "3-schedule"
    tid = GC["tid"]
    # snapshot pairings to prove scheduler never touches fixtures
    _, _, before = collect_items()
    snap = {m["id"]: (m["home_id"], m["away_id"], m.get("round"), m.get("order"),
                      m.get("next_match_id"), m.get("group"))
            for d in before.values() for m in d["matches"]}

    t0 = time.time()
    r = api("POST", f"/tournaments/{tid}/auto-schedule")
    dt = time.time() - t0
    check(sec, "tournament auto-schedule 200", r.status_code == 200, r.text[:300])
    resp = r.json()
    info(sec, "scheduler timing", f"{dt:.2f}s for {resp.get('scheduled', '?')} scheduled / "
         f"{resp.get('unscheduled', '?')} unscheduled across {resp.get('categories')} categories")
    GC["sched_resp"] = resp
    for k in ("scheduled", "unscheduled", "conflicts", "suggestions", "categories"):
        check(sec, f"response has '{k}'", k in resp)
    if resp.get("unscheduled"):
        types = {c["type"] for c in resp["conflicts"]}
        check(sec, "unscheduled -> capacity conflict present", "capacity" in types, types)
        check(sec, "unscheduled -> per-match diagnostics present",
              any(c["type"] == "unplaced_match" for c in resp["conflicts"]))
        check(sec, "unscheduled -> suggestions present", len(resp.get("suggestions", [])) > 0)
        info(sec, "conflict sample", json.dumps(resp["conflicts"][:6]))
        info(sec, "suggestions", json.dumps(resp.get("suggestions", [])))

    cats, grounds, after = collect_items()
    snap2 = {m["id"]: (m["home_id"], m["away_id"], m.get("round"), m.get("order"),
                       m.get("next_match_id"), m.get("group"))
             for d in after.values() for m in d["matches"]}
    check(sec, "fixtures untouched by scheduler (pairings/rounds/links identical)", snap == snap2,
          {k: (snap.get(k), snap2.get(k)) for k in snap if snap.get(k) != snap2.get(k)})

    # ---------- independent hard-constraint verification ----------
    placed = []   # (match, cat, dur)
    for cid, d in after.items():
        cons = d["cat"].get("constraints") or {}
        dur = int(cons.get("match_duration_minutes", 90))
        for m in d["matches"]:
            if m.get("date") and m.get("time") and m.get("ground_id"):
                placed.append((m, d["cat"], dur))
    info(sec, "placed matches", len(placed))

    # ground checks
    viol_ground, viol_window, viol_allowed, viol_break = [], [], [], []
    by_gd = defaultdict(list)
    for m, c, dur in placed:
        g = grounds.get(m["ground_id"])
        if not g:
            viol_allowed.append((m["id"], "ground missing"))
            continue
        allowed = c.get("ground_ids") or list(grounds)
        if m["ground_id"] not in allowed:
            viol_allowed.append((m["id"], c["name"], g["name"]))
        s = parse_t(m["time"]); e = s + dur
        cons = c.get("constraints") or {}
        # per-date window overrides the category default
        dw = (cons.get("date_windows") or {}).get(m["date"]) or {}
        lo = parse_t(dw.get("earliest") or cons.get("earliest_time", "08:00"))
        hi = parse_t(dw.get("latest") or cons.get("latest_time", "20:00"))
        # per-date ground hours override the ground default
        gdh = (g.get("date_hours") or {}).get(m["date"]) or {}
        if gdh.get("closed"):
            viol_ground.append((m["id"], g["name"], m["date"], "ground closed that day"))
        g_open = gdh.get("open") or g.get("open_time")
        g_close = gdh.get("close") or g.get("close_time")
        gl = parse_t(g_open) if g_open else 0
        gh = parse_t(g_close) if g_close else 24 * 60
        if s < lo or e > hi:
            viol_window.append((m["id"], c["name"], m["time"], m["date"], "category window"))
        if s < gl or e > gh:
            viol_window.append((m["id"], g["name"], m["time"], m["date"], "ground hours"))
        bs, be = cons.get("break_start"), cons.get("break_end")
        if bs and be and s < parse_t(be) and parse_t(bs) < e:
            viol_break.append((m["id"], c["name"], m["time"]))
        by_gd[(m["date"], m["ground_id"])].append((s, e, m["id"]))
    for key, lst in by_gd.items():
        lst.sort()
        for i in range(len(lst) - 1):
            if lst[i + 1][0] < lst[i][1]:
                viol_ground.append((key, lst[i][2], lst[i + 1][2]))
    check(sec, "no ground double-booking / closed-day use", not viol_ground, viol_ground[:5])
    check(sec, "grounds allowed for category", not viol_allowed, viol_allowed[:5])
    check(sec, "within category window AND ground hours (per-date aware)", not viol_window, viol_window[:5])
    check(sec, "protected break respected", not viol_break, viol_break[:5])

    # --- per-date windows actually took effect ---
    sec_d = "3-date-windows"
    u13_placed = [(m, c, d) for m, c, d in placed if c["id"] == GC["u13"]]
    sat = [m for m, c, d in u13_placed if m["date"] == "2026-09-05"]
    sun = [m for m, c, d in u13_placed if m["date"] == "2026-09-06"]
    check(sec_d, "Saturday U-13 matches all start at/after the 16:00 evening window",
          all(parse_t(m["time"]) >= 16 * 60 for m in sat),
          [(m["time"]) for m in sat if parse_t(m["time"]) < 16 * 60][:5])
    info(sec_d, "evening-only Saturday", f"{len(sat)} match(es), earliest {min([m['time'] for m in sat], default='-')}")
    check(sec_d, "Sunday U-13 matches use the default 08:00-18:00 window",
          all(8 * 60 <= parse_t(m["time"]) and parse_t(m["time"]) + 60 <= 18 * 60 for m in sun),
          [(m["time"]) for m in sun][:5])
    on_closed = [m["id"] for m, c, d in placed if m["date"] == "2026-09-06" and m["ground_id"] == GC["g"][3]]
    check(sec_d, "nothing scheduled on a ground marked closed for that date", not on_closed, on_closed[:5])
    g2_sat = [m for m, c, d in placed if m["date"] == "2026-09-05" and m["ground_id"] == GC["g"][2]]
    check(sec_d, "ground with late Saturday opening respected (18:00+)",
          all(parse_t(m["time"]) >= 18 * 60 for m in g2_sat),
          [m["time"] for m in g2_sat if parse_t(m["time"]) < 18 * 60][:5])

    # team checks
    team_sched = defaultdict(list)   # tid -> (date, s, e, cat)
    for m, c, dur in placed:
        for t in (m["home_id"], m["away_id"]):
            if t:
                team_sched[t].append((m["date"], parse_t(m["time"]), parse_t(m["time"]) + dur, c, m["id"]))
    all_teams = {}
    for d in after.values():
        all_teams.update(d["teams"])
    v_overlap, v_rest, v_avail, v_dates, v_maxpd = [], [], [], [], []
    for t, lst in team_sched.items():
        info_t = all_teams.get(t, {})
        lst.sort()
        per_day = defaultdict(int)
        for (dte, s, e, c, mid) in lst:
            per_day[dte] += 1
            af, at = info_t.get("available_from"), info_t.get("available_to")
            if af and s < parse_t(af):
                v_avail.append((info_t.get("name"), mid, "before available_from"))
            if at and e > parse_t(at):
                v_avail.append((info_t.get("name"), mid, "after available_to"))
            av = info_t.get("available_dates") or []
            if av and dte not in av:
                v_dates.append((info_t.get("name"), mid, dte, "not in available_dates"))
            if dte in (info_t.get("unavailable_dates") or []):
                v_dates.append((info_t.get("name"), mid, dte, "on unavailable date"))
        mx = info_t.get("max_matches_per_day")
        if mx and any(v > mx for v in per_day.values()):
            v_maxpd.append((info_t.get("name"), dict(per_day), f"max {mx}"))
        for i in range(len(lst) - 1):
            (d1, s1, e1, c1, m1), (d2, s2, e2, c2, m2) = lst[i], lst[i + 1]
            if d1 != d2:
                continue
            if s2 < e1:
                v_overlap.append((info_t.get("name"), d1, m1, m2))
                continue
            rest_req = int((c1.get("constraints") or {}).get("min_rest_minutes", 0))
            if info_t.get("no_back_to_back"):
                rest_req = max(rest_req, e1 - s1)
            if s2 - e1 < rest_req:
                v_rest.append((info_t.get("name"), d1, s2 - e1, f"need {rest_req}"))
    check(sec, "no team plays two matches at once", not v_overlap, v_overlap[:5])
    check(sec, "minimum rest / no-back-to-back respected", not v_rest, v_rest[:8])
    check(sec, "team daily time windows respected", not v_avail, v_avail[:8])
    check(sec, "team available/unavailable dates respected", not v_dates, v_dates[:8])
    check(sec, "team max matches/day respected", not v_maxpd, v_maxpd[:5])

    # category max/day (all our cats use 0 = unlimited, recorded for completeness)
    # knockout dependency: later rounds only schedulable when they have teams; R1 vs group stage for OB
    ob = after[GC["ob"]]
    grp_placed = [m for m in ob["matches"] if m["stage"] == "group" and m.get("date")]
    ko_placed = [m for m in ob["matches"] if m["stage"] == "knockout" and m.get("date")]
    check(sec, "OB knockout not scheduled before seeding (TBD matches unplaced)",
          not ko_placed, [m["id"] for m in ko_placed][:5])
    info(sec, "OB group placed", f"{len(grp_placed)}/12")

    # ---------- referee auto-assignment ----------
    sec_r = "3-referees"
    refs = {r["id"]: r for r in jget(f"/tournaments/{tid}/referees")}
    with_ref = [(m, c, dur) for m, c, dur in placed if m.get("referee_id")]
    gap = len(placed) - len(with_ref)
    # Full coverage OR an explicit warning — never a silent gap.
    ref_warned = any(c["type"] == "referee_capacity" for c in resp.get("conflicts", []))
    check(sec_r, "referee coverage is complete or the shortfall is reported",
          gap == 0 or ref_warned, f"{len(with_ref)}/{len(placed)} assigned, warned={ref_warned}")
    if gap:
        info(sec_r, "referee shortfall",
             f"{gap} match(es) uncovered — officials' daily limits exhausted (warning raised)")
    check(sec_r, "assigned referee ids all exist",
          all(m["referee_id"] in refs for m, c, d in with_ref))
    ref_sched = defaultdict(list)
    for m, c, dur in with_ref:
        ref_sched[m["referee_id"]].append((m["date"], parse_t(m["time"]), parse_t(m["time"]) + dur, m["id"]))
    v_overlap, v_max = [], []
    for rid, lst in ref_sched.items():
        lst.sort()
        per_day = defaultdict(int)
        for (d, s, e, mid) in lst:
            per_day[d] += 1
        mx = int(refs[rid].get("max_matches_per_day") or 0)
        if mx and any(v > mx for v in per_day.values()):
            v_max.append((refs[rid]["name"], dict(per_day), f"max {mx}"))
        for i in range(len(lst) - 1):
            if lst[i][0] == lst[i + 1][0] and lst[i + 1][1] < lst[i][2]:
                v_overlap.append((refs[rid]["name"], lst[i][3], lst[i + 1][3]))
    check(sec_r, "no referee officiates two overlapping matches", not v_overlap, v_overlap[:5])
    check(sec_r, "referee max matches/day respected", not v_max, v_max[:5])
    loads = sorted(len(v) for v in ref_sched.values())
    info(sec_r, "referee workload spread", f"{len(ref_sched)} officials used, loads {loads}")
    # idempotent re-run endpoint
    r2 = api("POST", f"/tournaments/{tid}/assign-referees")
    check(sec_r, "standalone /assign-referees endpoint works",
          r2.status_code == 200 and r2.json().get("assigned", 0) > 0, r2.text[:200])

    # conflicts endpoint agrees
    cf = jget(f"/tournaments/{tid}/conflicts")["conflicts"]
    errs = [c for c in cf if c["severity"] == "error"]
    check(sec, "tournament /conflicts has no ERROR-level conflicts on committed schedule",
          not errs, errs[:5])
    GC["conflicts_after_schedule"] = cf


if __name__ == "__main__":
    print(f"TournamentOS QA — {datetime.now().isoformat()} — base {BASE}\n")
    try:
        phase_health()
        phase_build()
        phase_auth()
        phase_fixtures()
        phase_schedule()
        # part 2 continues in qa_test2 (imported to keep files manageable)
        import qa_test2
        qa_test2.run(GC, RESULTS, check, info, api, jget, parse_t,
                     mk_tour, mk_ground, mk_cat, mk_team, CREATED_TOURS, collect_items)
    finally:
        cleanup()
        passed = sum(1 for r in RESULTS if r["status"] == "PASS")
        failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
        with open("qa_results.json", "w") as f:
            json.dump({"ts": datetime.now().isoformat(), "passed": passed, "failed": failed,
                       "results": RESULTS}, f, indent=1)
        print(f"\n==== DONE: {passed} passed, {failed} failed — details in qa_results.json ====")
