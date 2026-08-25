"""Focused tests for the date-editing bug fix:
- Tournament can be created without dates
- Auto-schedule 400s with the specific 'Set the tournament start and end dates...' message
- PUT /tournaments/{id} persists dates
- Single-day (only start_date, no end_date) schedules all matches successfully
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


TEST_EMAIL = os.environ.get("QA_EMAIL", "qa-harness@example.com")
TEST_PASSWORD = os.environ.get("QA_PASSWORD", "qa-harness-password-123")


def _token():
    """Sign in (bootstrapping the first admin on an empty database) for write access."""
    st = requests.get(f"{API}/auth/status", timeout=30).json()
    if not st.get("initialized"):
        r = requests.post(f"{API}/auth/bootstrap", timeout=30, json={
            "email": TEST_EMAIL, "name": "QA Harness", "password": TEST_PASSWORD, "role": "admin"})
    else:
        r = requests.post(f"{API}/auth/login", timeout=30,
                          json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"Could not authenticate as {TEST_EMAIL}: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json",
                      "Authorization": f"Bearer {_token()}"})
    return s


@pytest.fixture(scope="module")
def tour_no_dates(session):
    r = session.post(f"{API}/tournaments", json={"name": "TEST_NoDates Cup", "sport": "Football"})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t.get("start_date") in (None, "")
    assert t.get("end_date") in (None, "")
    yield t
    session.delete(f"{API}/tournaments/{t['id']}")


class TestDateEditingFlow:
    def test_1_create_without_dates(self, tour_no_dates):
        assert tour_no_dates["id"]
        assert tour_no_dates.get("start_date") in (None, "")

    def test_2_schedule_fails_without_dates(self, session, tour_no_dates):
        tid = tour_no_dates["id"]
        # Need a category+teams+ground+fixtures for scheduler to reach date check meaningfully,
        # but scheduler checks dates first, so we can test standalone.
        r = session.post(f"{API}/tournaments/{tid}/auto-schedule")
        assert r.status_code == 400
        assert "start and end dates" in r.json().get("detail", "").lower()

    def test_3_setup_category_teams_ground_fixtures(self, session, tour_no_dates):
        tid = tour_no_dates["id"]
        # Category
        r = session.post(f"{API}/tournaments/{tid}/categories", json={"name": "TEST_U15", "format": "league_single"})
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        tour_no_dates["_cid"] = cid
        # 4 Teams
        for i in range(4):
            rt = session.post(f"{API}/categories/{cid}/teams", json={"name": f"TEST_Team{i+1}"})
            assert rt.status_code == 200, rt.text
        # Ground
        rg = session.post(f"{API}/tournaments/{tid}/grounds", json={"name": "TEST_Main Ground"})
        assert rg.status_code == 200, rg.text
        # Fixtures
        rf = session.post(f"{API}/categories/{cid}/generate-fixtures")
        assert rf.status_code == 200, rf.text
        gen = rf.json()["generated"]
        # 4 teams round-robin single = 6 matches
        assert gen == 6

    def test_4_schedule_still_fails_without_dates(self, session, tour_no_dates):
        tid = tour_no_dates["id"]
        r = session.post(f"{API}/tournaments/{tid}/auto-schedule")
        assert r.status_code == 400
        assert "Set the tournament start and end dates before scheduling." in r.json().get("detail", "")

    def test_5_update_dates_start_only_persists(self, session, tour_no_dates):
        tid = tour_no_dates["id"]
        r = session.put(f"{API}/tournaments/{tid}", json={"start_date": "2026-03-15", "end_date": ""})
        assert r.status_code == 200, r.text
        # GET to verify persistence
        g = session.get(f"{API}/tournaments/{tid}")
        assert g.status_code == 200
        data = g.json()
        assert data["start_date"] == "2026-03-15"
        # end_date may be "" or None — both acceptable, scheduler will fall back to start_date
        assert data.get("end_date") in (None, "", "2026-03-15")

    def test_6_schedule_single_day_success(self, session, tour_no_dates):
        tid = tour_no_dates["id"]
        r = session.post(f"{API}/tournaments/{tid}/auto-schedule")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["scheduled"] >= 1
        # For single-day, ALL scheduled matches must be on the start_date (never spill to another date)
        cid = tour_no_dates["_cid"]
        ms = session.get(f"{API}/categories/{cid}/matches").json()
        scheduled_dates = {m["date"] for m in ms if m.get("date")}
        assert scheduled_dates == {"2026-03-15"}, f"Expected all on 2026-03-15, got {scheduled_dates}"

    def test_7_edit_persists_after_reload(self, session, tour_no_dates):
        tid = tour_no_dates["id"]
        # Update again with both dates
        r = session.put(f"{API}/tournaments/{tid}", json={"start_date": "2026-04-01", "end_date": "2026-04-05"})
        assert r.status_code == 200
        g = session.get(f"{API}/tournaments/{tid}").json()
        assert g["start_date"] == "2026-04-01"
        assert g["end_date"] == "2026-04-05"
