"""End-to-end backend tests for TournamentOS.
Covers tournament -> categories -> teams -> grounds -> fixtures -> auto-schedule -> standings.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def tour(session):
    r = session.post(f"{API}/tournaments", json={
        "name": "TEST_Backend Cup",
        "sport": "Football",
        "start_date": "2026-02-01",
        "end_date": "2026-02-15",
    })
    assert r.status_code == 200, r.text
    t = r.json()
    yield t
    session.delete(f"{API}/tournaments/{t['id']}")


class TestHealth:
    def test_root(self, session):
        r = session.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


class TestTournamentFlow:
    def test_tournament_created(self, tour):
        assert tour["id"]
        assert tour["name"] == "TEST_Backend Cup"

    def test_tournament_in_list(self, session, tour):
        r = session.get(f"{API}/tournaments")
        assert r.status_code == 200
        assert any(x["id"] == tour["id"] for x in r.json())


class TestLeagueEndToEnd:
    """League (single RR) with 5 teams (odd) + 2 grounds -> schedule + standings."""

    @pytest.fixture(scope="class")
    def ctx(self, session, tour):
        # category
        c = session.post(f"{API}/tournaments/{tour['id']}/categories", json={
            "name": "TEST_League A", "format": "league_single",
        }).json()
        # 5 teams
        teams = []
        for name in ["TA", "TB", "TC", "TD", "TE"]:
            teams.append(session.post(f"{API}/categories/{c['id']}/teams", json={"name": f"TEST_{name}"}).json())
        # 2 grounds
        grounds = []
        for gn in ["G1", "G2"]:
            grounds.append(session.post(f"{API}/tournaments/{tour['id']}/grounds", json={
                "name": f"TEST_{gn}", "open_time": "08:00", "close_time": "20:00"
            }).json())
        return {"tour": tour, "cat": c, "teams": teams, "grounds": grounds}

    def test_generate_fixtures(self, session, ctx):
        r = session.post(f"{API}/categories/{ctx['cat']['id']}/generate-fixtures")
        assert r.status_code == 200
        # 5 teams single RR = C(5,2) = 10 matches
        assert r.json()["generated"] == 10

    def test_matches_listed(self, session, ctx):
        r = session.get(f"{API}/categories/{ctx['cat']['id']}/matches")
        assert r.status_code == 200
        ms = r.json()
        assert len(ms) == 10
        # order/round populated
        assert all(m.get("round") for m in ms)

    def test_record_score_persists(self, session, ctx):
        ms = session.get(f"{API}/categories/{ctx['cat']['id']}/matches").json()
        m = ms[0]
        r = session.put(f"{API}/matches/{m['id']}", json={"home_score": 3, "away_score": 1})
        assert r.status_code == 200
        assert r.json()["home_score"] == 3
        assert r.json()["status"] == "completed"

    def test_auto_schedule(self, session, ctx):
        # attach grounds to category
        gids = [g["id"] for g in ctx["grounds"]]
        session.put(f"{API}/categories/{ctx['cat']['id']}", json={
            "ground_ids": gids,
            "constraints": {
                "start_date": "2026-02-01", "end_date": "2026-02-15",
                "earliest_time": "08:00", "latest_time": "20:00",
                "match_duration_minutes": 90, "slot_gap_minutes": 30,
                "min_rest_minutes": 60, "max_matches_per_day": 0,
            }
        })
        r = session.post(f"{API}/categories/{ctx['cat']['id']}/auto-schedule")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["unscheduled"] == 0
        # errors should be empty
        assert not [c for c in data.get("conflicts", []) if c.get("severity") == "error"]

    def test_standings_reflect_result(self, session, ctx):
        r = session.get(f"{API}/categories/{ctx['cat']['id']}/standings")
        assert r.status_code == 200
        data = r.json()
        assert data["grouped"] is False
        rows = data["standings"]
        # exactly one team has played, one has 3 pts (winner)
        played = [x for x in rows if x["played"] > 0]
        assert len(played) == 2
        winner = [x for x in rows if x["points"] == 3]
        assert len(winner) == 1
        assert winner[0]["gf"] == 3 and winner[0]["ga"] == 1

    def test_schedule_report(self, session, ctx):
        r = session.get(f"{API}/tournaments/{ctx['tour']['id']}/schedule")
        assert r.status_code == 200
        # All 10 league matches should be scheduled with dates
        assert len(r.json()) == 10


class TestGroupsKnockout:
    @pytest.fixture(scope="class")
    def gctx(self, session, tour):
        c = session.post(f"{API}/tournaments/{tour['id']}/categories", json={
            "name": "TEST_Groups B", "format": "groups_knockout", "num_groups": 2,
        }).json()
        teams = []
        for name in ["G1", "G2", "G3", "G4", "G5", "G6"]:
            teams.append(session.post(f"{API}/categories/{c['id']}/teams", json={"name": f"TEST_{name}"}).json())
        return {"cat": c, "teams": teams}

    def test_generate(self, session, gctx):
        r = session.post(f"{API}/categories/{gctx['cat']['id']}/generate-fixtures")
        assert r.status_code == 200
        assert r.json()["generated"] > 0

    def test_grouped_standings(self, session, gctx):
        r = session.get(f"{API}/categories/{gctx['cat']['id']}/standings")
        assert r.status_code == 200
        data = r.json()
        assert data["grouped"] is True
        assert len(data["standings"]) >= 2
