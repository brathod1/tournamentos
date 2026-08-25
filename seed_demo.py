"""Build the GOLAZO NATIONALS 2026 demo tournament — a deliberately demanding,
realistic multi-category event for hands-on testing.

    python seed_demo.py            # build it (replaces any previous copy)
    python seed_demo.py --results  # also enter results for the group/league stages

What it creates
  * 4 days: two evening-only weekday sessions, then two full weekend days
  * 6 grounds with different opening hours, floodlights and per-date availability
  * 14 referees with different daily limits
  * 8 categories covering all four formats, with different match durations,
    playing windows, rest rules, per-day caps, protected breaks and ground access
  * 73 teams, many with real-world availability restrictions
  * fixtures generated for every category, plus two locked showcase matches

It deliberately does NOT run the scheduler — that's the first thing for you to try.
"""
import sys
from collections import defaultdict

import requests

BASE = "http://localhost:8001/api"
S = requests.Session()
QA_EMAIL = "qa-harness@example.com"
QA_PASSWORD = "qa-harness-password-123"

NAME = "GOLAZO NATIONALS 2026"
THU, FRI, SAT, SUN = "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"
EVENING = {"earliest": "18:00", "latest": "22:00"}


def api(method, path, **kw):
    r = S.request(method, BASE + path, timeout=120, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code} {r.text[:300]}")
    return r.json() if r.text else {}


def sign_in():
    st = requests.get(f"{BASE}/auth/status", timeout=30).json()
    if not st["initialized"]:
        r = requests.post(f"{BASE}/auth/bootstrap", timeout=30, json={
            "email": QA_EMAIL, "name": "QA", "password": QA_PASSWORD, "role": "admin"})
    else:
        r = requests.post(f"{BASE}/auth/login", timeout=30,
                          json={"email": QA_EMAIL, "password": QA_PASSWORD})
    if r.status_code != 200:
        print(f"Could not sign in as {QA_EMAIL} ({r.status_code}).\n"
              "Edit QA_EMAIL / QA_PASSWORD at the top of this file to match an account you have.")
        sys.exit(1)
    S.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})


def base_constraints(dur, gap, rest, **extra):
    """Common shape: evening-only on the two weekdays, full days at the weekend."""
    c = {"start_date": THU, "end_date": SUN,
         "earliest_time": "08:00", "latest_time": "20:00",
         "match_duration_minutes": dur, "slot_gap_minutes": gap,
         "min_rest_minutes": rest, "max_matches_per_day": 0,
         "date_windows": {THU: dict(EVENING), FRI: dict(EVENING)}}
    c.update(extra)
    return c


def main(with_results=False):
    sign_in()

    # ---------------------------------------------------------------- reset
    for t in api("GET", "/tournaments"):
        if t["name"] == NAME:
            api("DELETE", f"/tournaments/{t['id']}")
            print(f"Removed previous {NAME}")

    tid = api("POST", "/tournaments", json={
        "name": NAME, "sport": "Football", "organizer": "Golazo Sports Ahmedabad",
        "location": "Ahmedabad", "start_date": THU, "end_date": SUN,
        "description": "Four-day national age-group championship. Thursday and Friday are "
                       "evening sessions under floodlights; Saturday and Sunday run all day. "
                       "Eight categories share six grounds."})["id"]
    print(f"\n{NAME}  ({THU} → {SUN})")

    # -------------------------------------------------------------- grounds
    def ground(name, o, c, lights, prio, date_hours=None):
        g = api("POST", f"/tournaments/{tid}/grounds", json={
            "name": name, "open_time": o, "close_time": c, "lighting": lights,
            "priority": prio, "surface": "Grass" if lights else "Turf",
            "capacity": 2000 if prio == 1 else 500})["id"]
        if date_hours:
            api("PUT", f"/grounds/{g}", json={"date_hours": date_hours})
        return g

    G = {
        "main":  ground("Main Stadium", "08:00", "22:00", True, 1),
        "north": ground("North Field", "08:00", "22:00", True, 1),
        "south": ground("South Field", "09:00", "21:00", True, 2),
        "east":  ground("East Ground", "08:00", "20:00", False, 2),
        "west":  ground("West Ground", "10:00", "22:00", True, 2),
        # Training pitch: no floodlights, and unavailable on the Sunday
        "train": ground("Training Pitch", "08:00", "17:00", False, 3,
                        date_hours={SUN: {"closed": True}}),
    }
    print(f"  {len(G)} grounds (Training Pitch closed on Sunday)")

    # ------------------------------------------------------------- referees
    refs = [("R. Sharma", "FIFA", 15, 4), ("A. Patel", "FIFA", 12, 4),
            ("K. Desai", "National", 9, 5), ("M. Shah", "National", 11, 4),
            ("P. Joshi", "National", 7, 5), ("V. Mehta", "State", 6, 5),
            ("S. Trivedi", "State", 5, 6), ("N. Vyas", "State", 8, 5),
            ("H. Bhatt", "District", 3, 6), ("D. Raval", "District", 2, 6),
            ("J. Parmar", "District", 4, 6), ("T. Solanki", "State", 6, 5),
            ("B. Chauhan", "National", 10, 4), ("G. Pandya", "District", 1, 6)]
    for n, cert, yrs, mx in refs:
        api("POST", f"/tournaments/{tid}/referees", json={
            "name": n, "certification": cert, "experience_years": yrs,
            "max_matches_per_day": mx, "phone": "+91 90000 00000"})
    print(f"  {len(refs)} referees")

    # ------------------------------------------------------------ categories
    cats = []

    def category(name, fmt, dur, gap, rest, grounds, teams, **kw):
        payload = {"name": name, "format": fmt, "ground_ids": grounds,
                   "constraints": base_constraints(dur, gap, rest, **kw.pop("constraints", {}))}
        payload.update(kw)
        cid = api("POST", f"/tournaments/{tid}/categories", json=payload)["id"]
        ids = {}
        for t in teams:
            ids[t["name"]] = api("POST", f"/categories/{cid}/teams", json=t)["id"]
        api("POST", f"/categories/{cid}/generate-fixtures")
        n = len(api("GET", f"/categories/{cid}/matches"))
        cats.append((name, cid, len(teams), n))
        print(f"  {name:<22} {fmt:<16} {len(teams):>2} teams → {n:>3} matches")
        return cid, ids

    def T(name, **kw):
        return {"name": name, **kw}

    # 1 — youngest: short matches, small grounds, weekend only (school nights).
    #     6 teams => 5 matches each; 3/day over 2 weekend days = 6, so it fits.
    category(
        "U-8 Mini Kickers", "league_single", 20, 10, 45,
        [G["east"], G["train"]],
        [T(f"Mini {c}", short_name=f"M{c}", day_preference="weekend", max_matches_per_day=3)
         for c in "ABCDEF"],
        constraints={"latest_time": "17:00"})

    # 2 — groups + knockout, finals on the Sunday
    category(
        "U-10 Cup", "groups_knockout", 25, 10, 45,
        [G["east"], G["south"], G["train"]],
        [T(f"Cubs {i}", short_name=f"C{i}", seed=i,
           **({"day_preference": "weekend"} if i <= 2 else {}))
         for i in range(1, 9)],
        seeded=True, num_groups=2, qualifiers_per_group=2,
        constraints={"latest_time": "18:00", "knockout_start_date": SUN})

    # 3 — double round robin: everyone plays everyone twice (4 teams => 12 matches,
    #     6 each, which is plenty over four days without crowding the grounds)
    category(
        "U-12 Double League", "league_double", 30, 10, 60,
        [G["south"], G["east"], G["west"]],
        [T(f"Juniors {c}", short_name=f"J{c}",
           **({"no_back_to_back": True} if c in "AB" else {}))
         for c in "ABCD"],
        constraints={"break_start": "12:30", "break_end": "13:30"})

    # 4 — four groups of three, knockout from the Sunday
    category(
        "U-14 Championship", "groups_knockout", 30, 15, 60,
        [G["north"], G["south"], G["west"]],
        [T(f"Colts {i:02d}", short_name=f"K{i}", seed=i,
           **({"available_from": "10:00"} if i == 1 else {}),
           **({"unavailable_dates": [SAT]} if i == 5 else {}))
         for i in range(1, 13)],
        seeded=True, num_groups=4, qualifiers_per_group=2,
        constraints={"knockout_start_date": SUN, "break_start": "13:00", "break_end": "14:00"})

    # 5 — straight knockout, 16 seeds, big pitches
    category(
        "U-16 Knockout", "knockout", 40, 15, 90,
        [G["main"], G["north"], G["west"]],
        [T(f"Academy {i:02d}", short_name=f"A{i}", seed=i,
           **({"available_to": "18:00"} if i in (3, 9) else {}))
         for i in range(1, 17)],
        seeded=True,
        constraints={"knockout_earliest_time": "09:00"})

    # 6 — full league, longer matches, capped per day (6 teams => 5 matches each,
    #     2/day over four days = 8, comfortable)
    category(
        "U-19 League", "league_single", 45, 15, 120,
        [G["main"], G["north"], G["south"], G["east"]],
        [T(f"Colleges {c}", short_name=f"U{c}", max_matches_per_day=2,
           **({"available_from": "11:00", "available_to": "21:00"} if c == "A" else {}))
         for c in "ABCDEF"],
        constraints={"max_matches_per_day": 0, "break_start": "12:30", "break_end": "13:30"})

    # 7 — the marquee category: long matches, main grounds, Sunday final
    category(
        "Open Men", "groups_knockout", 50, 15, 150,
        [G["main"], G["north"], G["west"]],
        [T(f"City FC {i:02d}", short_name=f"CF{i}", seed=i,
           **({"available_dates": [SAT, SUN]} if i in (2, 7) else {}),
           **({"no_back_to_back": True} if i <= 4 else {}))
         for i in range(1, 13)],
        seeded=True, num_groups=4, qualifiers_per_group=2,
        constraints={"earliest_time": "09:00", "latest_time": "21:00",
                     "knockout_start_date": SUN, "knockout_earliest_time": "11:00",
                     "break_start": "13:00", "break_end": "14:00"})

    # 8 — veterans: odd number of teams (tests the round-robin bye), weekend
    #     afternoons only; 4 matches each, 3/day over 2 days = 6, so it fits
    category(
        "Veterans 40+", "league_single", 45, 15, 90,
        [G["south"], G["east"], G["west"]],
        [T(f"Legends {c}", short_name=f"V{c}", day_preference="weekend",
           available_from="14:00", max_matches_per_day=3) for c in "ABCDE"],
        constraints={"earliest_time": "14:00", "latest_time": "20:00"})

    # -------------------------------------------------- two locked showcase slots
    u16 = next(c for c in cats if c[0] == "U-16 Knockout")[1]
    openm = next(c for c in cats if c[0] == "Open Men")[1]
    locked = []
    ms = sorted(api("GET", f"/categories/{u16}/matches"), key=lambda m: m.get("order") or 0)
    opener = next((m for m in ms if m.get("home_id") and m.get("away_id")), None)
    if opener:
        api("PUT", f"/matches/{opener['id']}", json={
            "date": THU, "time": "19:00", "ground_id": G["main"], "locked": True})
        locked.append("U-16 opening match — Thu 19:00, Main Stadium")
    oms = sorted([m for m in api("GET", f"/categories/{openm}/matches")
                  if m.get("stage") == "group"], key=lambda m: m.get("order") or 0)
    if oms:
        api("PUT", f"/matches/{oms[0]['id']}", json={
            "date": FRI, "time": "20:00", "ground_id": G["main"], "locked": True})
        locked.append("Open Men marquee group match — Fri 20:00, Main Stadium")

    # ------------------------------------------------------- optional results
    if with_results:
        n = 0
        for name, cid, _, _ in cats:
            for i, m in enumerate(sorted(api("GET", f"/categories/{cid}/matches"),
                                         key=lambda x: x.get("order") or 0)):
                if m.get("stage") == "knockout" or not (m.get("home_id") and m.get("away_id")):
                    continue
                h, a = (i * 3 + 1) % 5, (i * 2) % 4
                api("PUT", f"/matches/{m['id']}", json={
                    "home_score": h, "away_score": a, "status": "completed"})
                n += 1
        print(f"\n  Entered {n} group/league results (knockouts left blank)")

    # ------------------------------------------------------------- summary
    total_teams = sum(c[2] for c in cats)
    total_matches = sum(c[3] for c in cats)
    print(f"\n  TOTAL: {len(cats)} categories · {total_teams} teams · {total_matches} matches")
    print("  Locked: " + ("; ".join(locked) if locked else "none"))
    print(f"\n  Open the app and pick '{NAME}'.")
    print("""
  This configuration is sized to fit: every team's matches are within what its
  per-day limit and available days allow, and total demand is roughly half the
  available pitch time. Scheduling it should place everything with no errors.

  Suggested test run
  ------------------
   1. Schedule tab → 'Schedule Whole Tournament'. Everything should be placed with
      no conflicts. Note how long it takes.
   2. Check the two locked matches did not move (Thu 19:00 and Fri 20:00, Main Stadium).
   3. Board tab → step through Thu/Fri/Sat/Sun.
        - Thursday and Friday should only have evening matches (18:00+)
        - Sunday should show nothing on the Training Pitch (closed)
        - Veterans should never appear before 14:00
        - try dragging a match; try dragging a locked one (should refuse)
   4. Schedule tab → set a per-day window (e.g. Saturday 09:00-15:00 for one category),
      save, re-run, and confirm it is obeyed.
   5. Fixtures tab → enter U-10 and U-14 group results → 'Seed from Group Standings'
      → re-run the scheduler → knockout matches should land on Sunday only.
   6. Standings tab → check the tables, then edit a score and watch them update.
   7. Reports tab → By Time and By Ground, export the CSV, check referees appear.
   8. Sign out → confirm you can still browse fixtures/standings but cannot edit.
   9. Try to break it deliberately: set Veterans' teams to 1 match/day, or shrink the
      tournament to a single day, then re-schedule. You should get named settings and
      the arithmetic behind them — not a broken schedule.
""")


if __name__ == "__main__":
    main(with_results="--results" in sys.argv)
