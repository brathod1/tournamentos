"""Backend tests for TournamentOS Scheduling Engine.

Covers invariants:
 - endpoint response shape
 - no ground clash / no team overlap on committed schedule
 - minimum rest respected
 - fixtures (pairings) untouched by scheduler
 - locked matches preserved on re-run
 - knockout progression (Final after Semi-Finals; KO after group stage)
 - graceful infeasibility diagnostics (no 500)
 - per-category endpoint
 - ground balancing across multiple grounds
"""
import os
import time
import requests
import pytest
from datetime import datetime, timedelta

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for ln in f:
                    if ln.startswith("REACT_APP_BACKEND_URL="):
                        v = ln.strip().split("=", 1)[1]
                        break
        except Exception:
            pass
    if not v:
        raise RuntimeError("REACT_APP_BACKEND_URL missing")
    return v.rstrip("/") + "/api"

BASE = _load_base()

SEEDED_LEAGUE = "91d2837c-39fa-4b2b-bafe-9e874821d8a1"     # Verified League (6/6 expected)
SEEDED_MULTI = "4fd6415f-36c0-4be0-aad1-ae308fabfe9c"       # CAWDADC (multi-cat)


def _parse(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


# ------------------------------------------------------------------
# Response shape + core invariants against seeded League
# ------------------------------------------------------------------
class TestSeededLeague:
    def test_auto_schedule_shape(self):
        r = requests.post(f"{BASE}/tournaments/{SEEDED_LEAGUE}/auto-schedule")
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("scheduled", "unscheduled", "conflicts", "suggestions", "categories"):
            assert k in data, f"missing key {k}: {data}"
        assert data["scheduled"] == 6
        assert data["unscheduled"] == 0

    def test_schedule_endpoint_populated(self):
        r = requests.get(f"{BASE}/tournaments/{SEEDED_LEAGUE}/schedule")
        assert r.status_code == 200
        matches = r.json()
        assert len(matches) >= 6
        for m in matches:
            assert m.get("date"), m
            assert m.get("time"), m
            assert m.get("ground_id"), m

    def test_no_ground_or_team_overlap_and_rest(self):
        # Fetch tournament + categories to get durations & min_rest
        cats = requests.get(f"{BASE}/tournaments/{SEEDED_LEAGUE}/categories").json()
        cat_by_id = {c["id"]: c for c in cats}
        matches = requests.get(f"{BASE}/tournaments/{SEEDED_LEAGUE}/schedule").json()
        # ground overlap
        by_gd = {}
        for m in matches:
            dur = int((cat_by_id[m["category_id"]].get("constraints") or {}).get("match_duration_minutes", 90))
            key = (m["date"], m["ground_id"])
            for om, odur in by_gd.get(key, []):
                s1, s2 = _parse(m["time"]), _parse(om["time"])
                assert not (s1 < s2 + odur and s2 < s1 + dur), \
                    f"Ground clash on {key}: {m['time']} vs {om['time']}"
            by_gd.setdefault(key, []).append((m, dur))
        # team overlap + rest
        team_matches = {}
        for m in matches:
            for tid in (m.get("home_id"), m.get("away_id")):
                if tid:
                    team_matches.setdefault(tid, []).append(m)
        for tid, ms in team_matches.items():
            ms.sort(key=lambda x: (x["date"], _parse(x["time"])))
            for i in range(len(ms) - 1):
                a, b = ms[i], ms[i + 1]
                if a["date"] != b["date"]:
                    continue
                dur_a = int((cat_by_id[a["category_id"]].get("constraints") or {}).get("match_duration_minutes", 90))
                min_rest = int((cat_by_id[a["category_id"]].get("constraints") or {}).get("min_rest_minutes", 0))
                gap = _parse(b["time"]) - (_parse(a["time"]) + dur_a)
                assert gap >= 0, f"Team {tid} overlap on {a['date']}"
                assert gap >= min_rest, f"Team {tid} rest {gap} < {min_rest} on {a['date']}"


# ------------------------------------------------------------------
# Fixtures untouched by scheduler
# ------------------------------------------------------------------
class TestFixturesUntouched:
    def test_pairings_unchanged_after_schedule(self):
        cats = requests.get(f"{BASE}/tournaments/{SEEDED_LEAGUE}/categories").json()
        cid = cats[0]["id"]
        before = requests.get(f"{BASE}/categories/{cid}/matches").json()
        before_map = {m["id"]: (m["home_id"], m["away_id"], m["round"], m["order"]) for m in before}
        r = requests.post(f"{BASE}/categories/{cid}/auto-schedule")
        assert r.status_code == 200, r.text
        after = requests.get(f"{BASE}/categories/{cid}/matches").json()
        for m in after:
            assert (m["home_id"], m["away_id"], m["round"], m["order"]) == before_map[m["id"]], \
                f"Fixture changed for {m['id']}"


# ------------------------------------------------------------------
# Multi-category tournament (CAWDADC) - shape and invariants + diagnostics
# ------------------------------------------------------------------
class TestSeededMulti:
    def test_run_and_check_invariants(self):
        r = requests.post(f"{BASE}/tournaments/{SEEDED_MULTI}/auto-schedule")
        assert r.status_code == 200, r.text
        data = r.json()
        # Should have diagnostics if infeasible (expected ~1 unsched per problem statement)
        assert data["scheduled"] >= 20
        if data["unscheduled"] > 0:
            types = {c["type"] for c in data["conflicts"]}
            assert "capacity" in types, f"missing capacity conflict: {data['conflicts']}"
            assert any(c["type"] == "unplaced_match" for c in data["conflicts"]), \
                "expected per-match unplaced_match diagnostic"
            assert isinstance(data["suggestions"], list) and len(data["suggestions"]) > 0

        # No 500 for infeasibility
        # Check no ground clash / no team overlap in committed placements
        matches = requests.get(f"{BASE}/tournaments/{SEEDED_MULTI}/schedule").json()
        cats = requests.get(f"{BASE}/tournaments/{SEEDED_MULTI}/categories").json()
        cat_by_id = {c["id"]: c for c in cats}
        by_gd = {}
        for m in matches:
            dur = int((cat_by_id[m["category_id"]].get("constraints") or {}).get("match_duration_minutes", 90))
            key = (m["date"], m["ground_id"])
            for om, odur in by_gd.get(key, []):
                s1, s2 = _parse(m["time"]), _parse(om["time"])
                assert not (s1 < s2 + odur and s2 < s1 + dur), f"Ground clash {key}"
            by_gd.setdefault(key, []).append((m, dur))
        # team overlap
        tmap = {}
        for m in matches:
            for tid in (m.get("home_id"), m.get("away_id")):
                if tid:
                    tmap.setdefault(tid, []).append(m)
        for tid, ms in tmap.items():
            ms.sort(key=lambda x: (x["date"], _parse(x["time"])))
            for i in range(len(ms) - 1):
                a, b = ms[i], ms[i + 1]
                if a["date"] != b["date"]:
                    continue
                dur_a = int((cat_by_id[a["category_id"]].get("constraints") or {}).get("match_duration_minutes", 90))
                assert _parse(b["time"]) >= _parse(a["time"]) + dur_a, \
                    f"Team {tid} overlap on {a['date']}"


# ------------------------------------------------------------------
# Custom tournament fixture builder used across the remaining tests
# ------------------------------------------------------------------
def _mk_tour(name, start, end):
    r = requests.post(f"{BASE}/tournaments", json={
        "name": f"TEST_{name}_{int(time.time()*1000)}",
        "start_date": start, "end_date": end,
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _mk_ground(tid, name, priority=1):
    r = requests.post(f"{BASE}/tournaments/{tid}/grounds", json={
        "name": name, "priority": priority,
    })
    assert r.status_code == 200
    return r.json()["id"]


def _mk_cat(tid, name, fmt, ground_ids, constraints=None, num_groups=2, seeded=True):
    payload = {
        "name": name, "format": fmt, "ground_ids": ground_ids,
        "seeded": seeded, "num_groups": num_groups,
        "constraints": constraints or {},
    }
    r = requests.post(f"{BASE}/tournaments/{tid}/categories", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _mk_team(cid, name, seed=None):
    r = requests.post(f"{BASE}/categories/{cid}/teams", json={"name": name, "seed": seed})
    assert r.status_code == 200
    return r.json()["id"]


def _cleanup(tid):
    try:
        requests.delete(f"{BASE}/tournaments/{tid}")
    except Exception:
        pass


# ------------------------------------------------------------------
# Locked match preservation
# ------------------------------------------------------------------
class TestLockedMatches:
    def test_locked_match_preserved_on_rerun(self):
        tid = _mk_tour("locked", "2026-06-01", "2026-06-05")
        try:
            g1 = _mk_ground(tid, "G1")
            g2 = _mk_ground(tid, "G2")
            cid = _mk_cat(tid, "L", "league_single", [g1, g2], constraints={
                "start_date": "2026-06-01", "end_date": "2026-06-05",
                "earliest_time": "08:00", "latest_time": "20:00",
                "match_duration_minutes": 60, "slot_gap_minutes": 15,
                "min_rest_minutes": 30, "max_matches_per_day": 0,
            })
            for i in range(4):
                _mk_team(cid, f"T{i+1}", seed=i+1)
            r = requests.post(f"{BASE}/categories/{cid}/generate-fixtures")
            assert r.status_code == 200
            r = requests.post(f"{BASE}/tournaments/{tid}/auto-schedule")
            assert r.status_code == 200
            matches = requests.get(f"{BASE}/categories/{cid}/matches").json()
            # Lock the first match at a specific slot
            m0 = matches[0]
            locked_slot = {"date": "2026-06-03", "time": "14:00", "ground_id": g1, "locked": True}
            r = requests.put(f"{BASE}/matches/{m0['id']}", json=locked_slot)
            assert r.status_code == 200
            # Re-run scheduler
            r = requests.post(f"{BASE}/tournaments/{tid}/auto-schedule")
            assert r.status_code == 200
            after = requests.get(f"{BASE}/categories/{cid}/matches").json()
            after_map = {m["id"]: m for m in after}
            m0a = after_map[m0["id"]]
            assert m0a["date"] == "2026-06-03"
            assert m0a["time"] == "14:00"
            assert m0a["ground_id"] == g1
            assert m0a.get("locked") is True
            # And no other match on G1 on that date overlaps 14:00-15:00
            for m in after:
                if m["id"] == m0["id"] or not m.get("date"):
                    continue
                if m["date"] == "2026-06-03" and m["ground_id"] == g1:
                    s = _parse(m["time"])
                    assert not (s < 15 * 60 and 14 * 60 < s + 60), \
                        f"Overlap with locked match: {m['time']}"
        finally:
            _cleanup(tid)


# ------------------------------------------------------------------
# Knockout progression (Final after Semi-Finals)
# ------------------------------------------------------------------
class TestKnockoutProgression:
    def test_final_after_semi(self):
        tid = _mk_tour("ko", "2026-07-01", "2026-07-05")
        try:
            g1 = _mk_ground(tid, "G1")
            cid = _mk_cat(tid, "KO", "knockout", [g1], seeded=True, constraints={
                "start_date": "2026-07-01", "end_date": "2026-07-05",
                "earliest_time": "08:00", "latest_time": "18:00",
                "match_duration_minutes": 60, "slot_gap_minutes": 15,
                "min_rest_minutes": 30, "max_matches_per_day": 2,
            })
            for i in range(8):
                _mk_team(cid, f"K{i+1}", seed=i+1)
            requests.post(f"{BASE}/categories/{cid}/generate-fixtures")
            # Seed later-round team ids manually so scheduler considers them
            ms = requests.get(f"{BASE}/categories/{cid}/matches").json()
            teams = requests.get(f"{BASE}/categories/{cid}/teams").json()
            tids = [t["id"] for t in teams]
            for m in ms:
                if m["round"] > 1 and not (m.get("home_id") and m.get("away_id")):
                    requests.put(f"{BASE}/matches/{m['id']}", json={
                        "home_id": tids[0], "away_id": tids[1], "status": "scheduled"})
            r = requests.post(f"{BASE}/tournaments/{tid}/auto-schedule")
            assert r.status_code == 200, r.text
            matches = requests.get(f"{BASE}/categories/{cid}/matches").json()
            by_round = {}
            for m in matches:
                if m.get("date"):
                    by_round.setdefault(m["round"], []).append(m)
            # find max end time per round
            def end_key(m):
                return (m["date"], _parse(m["time"]))
            rounds = sorted(by_round.keys())
            assert len(rounds) >= 2
            for i in range(len(rounds) - 1):
                r_end_max = max(end_key(m) for m in by_round[rounds[i]])
                r_next_min = min(end_key(m) for m in by_round[rounds[i + 1]])
                assert r_next_min >= r_end_max, \
                    f"Round {rounds[i+1]} starts before Round {rounds[i]} ends"
            # Final is last round
            finals = [m for m in matches if m.get("label") == "Final" and m.get("date")]
            semis = [m for m in matches if m.get("label") == "Semi-Final" and m.get("date")]
            if finals and semis:
                fmin = min(end_key(m) for m in finals)
                smax = max(end_key(m) for m in semis)
                assert fmin >= smax, "Final scheduled before Semi-Finals end"
        finally:
            _cleanup(tid)


# ------------------------------------------------------------------
# Infeasibility diagnostics: no 500, structured conflicts + suggestions
# ------------------------------------------------------------------
class TestInfeasibility:
    def test_single_day_too_many_matches(self):
        tid = _mk_tour("tight", "2026-08-01", "2026-08-01")
        try:
            g1 = _mk_ground(tid, "G1")
            # 6 teams league_single -> 15 matches on 1 day/1 ground - impossible
            cid = _mk_cat(tid, "Tight", "league_single", [g1], constraints={
                "start_date": "2026-08-01", "end_date": "2026-08-01",
                "earliest_time": "09:00", "latest_time": "17:00",
                "match_duration_minutes": 60, "slot_gap_minutes": 15,
                "min_rest_minutes": 45, "max_matches_per_day": 0,
            })
            for i in range(6):
                _mk_team(cid, f"X{i+1}", seed=i+1)
            requests.post(f"{BASE}/categories/{cid}/generate-fixtures")
            r = requests.post(f"{BASE}/tournaments/{tid}/auto-schedule")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["unscheduled"] > 0
            types = {c["type"] for c in data["conflicts"]}
            assert "capacity" in types
            assert any(c["type"] == "unplaced_match" for c in data["conflicts"]), \
                f"missing unplaced_match diagnostics: {data['conflicts']}"
            assert isinstance(data["suggestions"], list) and len(data["suggestions"]) > 0
        finally:
            _cleanup(tid)


# ------------------------------------------------------------------
# Per-category endpoint returns same-shape response
# ------------------------------------------------------------------
class TestCategoryEndpoint:
    def test_category_auto_schedule_shape(self):
        cats = requests.get(f"{BASE}/tournaments/{SEEDED_LEAGUE}/categories").json()
        cid = cats[0]["id"]
        r = requests.post(f"{BASE}/categories/{cid}/auto-schedule")
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("scheduled", "unscheduled", "conflicts", "suggestions"):
            assert k in data, f"missing {k}"


# ------------------------------------------------------------------
# Ground balancing across multiple grounds
# ------------------------------------------------------------------
class TestGroundBalancing:
    def test_matches_spread_across_grounds(self):
        tid = _mk_tour("balance", "2026-09-01", "2026-09-01")
        try:
            g1 = _mk_ground(tid, "GA", priority=1)
            g2 = _mk_ground(tid, "GB", priority=1)
            g3 = _mk_ground(tid, "GC", priority=1)
            cid = _mk_cat(tid, "Bal", "league_single", [g1, g2, g3], constraints={
                "start_date": "2026-09-01", "end_date": "2026-09-01",
                "earliest_time": "08:00", "latest_time": "20:00",
                "match_duration_minutes": 60, "slot_gap_minutes": 15,
                "min_rest_minutes": 30, "max_matches_per_day": 0,
            })
            # 6 teams -> 15 matches - plenty to spread
            for i in range(6):
                _mk_team(cid, f"B{i+1}", seed=i+1)
            requests.post(f"{BASE}/categories/{cid}/generate-fixtures")
            r = requests.post(f"{BASE}/tournaments/{tid}/auto-schedule")
            assert r.status_code == 200
            matches = requests.get(f"{BASE}/categories/{cid}/matches").json()
            placed = [m for m in matches if m.get("date")]
            counts = {g1: 0, g2: 0, g3: 0}
            for m in placed:
                counts[m["ground_id"]] = counts.get(m["ground_id"], 0) + 1
            # All 3 grounds should have at least one match (balanced parallelism)
            used = sum(1 for v in counts.values() if v > 0)
            assert used >= 2, f"Grounds usage unbalanced: {counts}"
            # And no single ground should host >70% of placed
            top = max(counts.values())
            assert top <= 0.75 * len(placed) + 1, f"One ground dominates: {counts}"
        finally:
            _cleanup(tid)
