"""Fixture generation + smart scheduling engine + standings for TournamentOS.
Sport-agnostic, fully driven by category configuration.
"""
from datetime import datetime, timedelta, date, time
from itertools import combinations
import random
import math
import uuid
from collections import defaultdict


def _round_name(total_rounds, r):
    """Human name for a knockout round (r is 1-based, final is the last)."""
    remaining = total_rounds - r
    names = {0: "Final", 1: "Semi-Final", 2: "Quarter-Final", 3: "Round of 16", 4: "Round of 32", 5: "Round of 64"}
    return names.get(remaining, f"Round {r}")


# ---------------------------------------------------------------------------
# FIXTURE GENERATION
# ---------------------------------------------------------------------------

def _round_robin(team_ids):
    """Circle method single round robin. Returns list of rounds, each a list of (home, away)."""
    teams = list(team_ids)
    if len(teams) < 2:
        return []
    bye = None
    if len(teams) % 2 == 1:
        bye = "__BYE__"
        teams.append(bye)
    n = len(teams)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            if a != bye and b != bye:
                # alternate home/away for balance
                if r % 2 == 0:
                    pairs.append((a, b))
                else:
                    pairs.append((b, a))
        rounds.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return rounds


def _next_pow2(n):
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))


def _seed_order(size):
    """Standard bracket seeding positions for a bracket of given size (power of 2)."""
    if size == 1:
        return [0]
    prev = _seed_order(size // 2)
    res = []
    for p in prev:
        res.append(p)
        res.append(size - 1 - p)
    return res


def _ordered_team_ids(teams, seeded):
    """Team ids in competition order. When the category is seeded, honour each team's
    `seed` number (1 = strongest, unseeded teams last); otherwise keep entry order."""
    if not seeded:
        return [t["id"] for t in teams]
    def key(t):
        s = t.get("seed")
        return (1, 0) if s in (None, "") else (0, int(s))
    return [t["id"] for t in sorted(teams, key=key)]


def generate_matches(category, teams):
    """Generate match dicts (unscheduled) based on category format config.
    Returns list of dicts with keys: round, group, stage, home_id, away_id, order.
    """
    fmt = category.get("format", "league_single")
    seeded = bool(category.get("seeded", False))
    team_ids = _ordered_team_ids(teams, seeded)
    matches = []
    order = 0

    def add(home, away, rnd, stage, group=None, label=None):
        nonlocal order
        matches.append({
            "round": rnd, "group": group, "stage": stage,
            "home_id": home, "away_id": away, "order": order,
            "label": label,
        })
        order += 1

    if fmt in ("league_single", "league_double"):
        rounds = _round_robin(team_ids)
        for ri, pairs in enumerate(rounds, start=1):
            for (h, a) in pairs:
                add(h, a, ri, "league")
        if fmt == "league_double":
            base = len(rounds)
            for ri, pairs in enumerate(rounds, start=1):
                for (h, a) in pairs:
                    add(a, h, base + ri, "league")  # reverse home/away

    elif fmt == "knockout":
        ids = list(team_ids)   # already seed-ordered when the category is seeded
        if not seeded:
            random.shuffle(ids)
        size = _next_pow2(len(ids))
        positions = _seed_order(size)
        slots = [None] * size
        for i in range(size):
            si = positions[i]
            slots[i] = ids[si] if si < len(ids) else None  # None = BYE
        total_rounds = int(math.log2(size))
        round_matches = []
        r1 = []
        for i in range(size // 2):
            r1.append({"id": str(uuid.uuid4()), "home_id": slots[2 * i], "away_id": slots[2 * i + 1],
                       "round": 1, "stage": "knockout", "group": None, "bracket_pos": i,
                       "label": _round_name(total_rounds, 1)})
        round_matches.append(r1)
        for r in range(2, total_rounds + 1):
            prev = round_matches[-1]
            cur = []
            for i in range(len(prev) // 2):
                cur.append({"id": str(uuid.uuid4()), "home_id": None, "away_id": None,
                            "round": r, "stage": "knockout", "group": None, "bracket_pos": i,
                            "label": _round_name(total_rounds, r)})
            for i, pm in enumerate(prev):
                pm["next_match_id"] = cur[i // 2]["id"]
                pm["next_slot"] = "home" if i % 2 == 0 else "away"
            round_matches.append(cur)
        flat = [m for rm in round_matches for m in rm]
        by_id = {m["id"]: m for m in flat}
        # auto-advance byes into the next round (byes only exist in round 1)
        for m in flat:
            if m["round"] != 1:
                continue
            w = None
            if m.get("home_id") and not m.get("away_id"):
                w = m["home_id"]; m["is_bye"] = True
            elif m.get("away_id") and not m.get("home_id"):
                w = m["away_id"]; m["is_bye"] = True
            if w and m.get("next_match_id"):
                by_id[m["next_match_id"]][m["next_slot"] + "_id"] = w
        for o, m in enumerate(flat):
            m["order"] = o
            matches.append(m)

    elif fmt == "groups_knockout":
        num_groups = max(1, int(category.get("num_groups", 2)))
        ids = list(team_ids)   # already seed-ordered when the category is seeded
        if not seeded:
            random.shuffle(ids)
        groups = {i: [] for i in range(num_groups)}
        # snake allocation for balance
        gi, direction = 0, 1
        for tid in ids:
            groups[gi].append(tid)
            gi += direction
            if gi == num_groups:
                gi, direction = num_groups - 1, -1
            elif gi < 0:
                gi, direction = 0, 1
        for g, gteams in groups.items():
            rounds = _round_robin(gteams)
            for ri, pairs in enumerate(rounds, start=1):
                for (h, a) in pairs:
                    add(h, a, ri, "group", group=f"Group {chr(65+g)}")
        # Build the knockout bracket skeleton fed by group qualifiers
        q_per = max(1, int(category.get("qualifiers_per_group", 2)))
        group_names = [f"Group {chr(65+g)}" for g in range(num_groups)]
        sources = []
        for pos in range(1, q_per + 1):
            for gn in group_names:
                sources.append({"group": gn, "pos": pos})
        Q = len(sources)
        if Q >= 2:
            size = _next_pow2(Q)
            positions = _seed_order(size)
            slot_src = [None] * size
            for i in range(size):
                si = positions[i]
                slot_src[i] = sources[si] if si < Q else None
            total_rounds = int(math.log2(size))
            round_matches = []
            r1 = []
            for i in range(size // 2):
                r1.append({"id": str(uuid.uuid4()), "home_id": None, "away_id": None,
                           "round": 1, "stage": "knockout", "group": None, "bracket_pos": i,
                           "label": _round_name(total_rounds, 1),
                           "home_source": slot_src[2 * i], "away_source": slot_src[2 * i + 1]})
            round_matches.append(r1)
            for r in range(2, total_rounds + 1):
                prev = round_matches[-1]
                cur = []
                for i in range(len(prev) // 2):
                    cur.append({"id": str(uuid.uuid4()), "home_id": None, "away_id": None,
                                "round": r, "stage": "knockout", "group": None, "bracket_pos": i,
                                "label": _round_name(total_rounds, r)})
                for i, pm in enumerate(prev):
                    pm["next_match_id"] = cur[i // 2]["id"]
                    pm["next_slot"] = "home" if i % 2 == 0 else "away"
                round_matches.append(cur)
            base = len(matches)
            for o, m in enumerate([mm for rm in round_matches for mm in rm]):
                m["order"] = base + o
                matches.append(m)

    return matches


# ---------------------------------------------------------------------------
# SMART SCHEDULING ENGINE
# ---------------------------------------------------------------------------

def _parse_t(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _fmt_t(mins):
    return f"{mins // 60:02d}:{mins % 60:02d}"


def build_slots(constraints, grounds):
    """Generate candidate (date, ground_id, start_min) slots between start/end date."""
    earliest = _parse_t(constraints.get("earliest_time", "08:00"))
    latest = _parse_t(constraints.get("latest_time", "20:00"))
    dur = int(constraints.get("match_duration_minutes", 90))
    gap = int(constraints.get("slot_gap_minutes", 30))
    step = dur + gap
    start = datetime.fromisoformat(constraints["start_date"]).date()
    end = datetime.fromisoformat(constraints["end_date"]).date()
    unavailable = set(constraints.get("unavailable_dates", []))
    slots = []
    d = start
    while d <= end:
        if d.isoformat() not in unavailable:
            for g in grounds:
                # ground specific window overrides
                g_open = _parse_t(g.get("open_time") or _fmt_t(earliest))
                g_close = _parse_t(g.get("close_time") or _fmt_t(latest))
                lo = max(earliest, g_open)
                hi = min(latest, g_close)
                t = lo
                while t + dur <= hi:
                    slots.append({"date": d.isoformat(), "ground_id": g["id"], "start": t, "dur": dur})
                    t += step
        d += timedelta(days=1)
    slots.sort(key=lambda s: (s["date"], s["start"], s["ground_id"]))
    return slots


def auto_schedule(matches, constraints, grounds, team_info=None):
    """Greedy scheduler. Assigns date/time/ground to each match respecting constraints.
    Returns (scheduled_matches, unscheduled, conflicts)."""
    team_info = team_info or {}
    if not grounds:
        return matches, matches, [{
            "type": "no_grounds", "severity": "error",
            "message": "No grounds assigned to this category. Assign at least one ground before scheduling."
        }]
    slots = build_slots(constraints, grounds)
    min_rest = int(constraints.get("min_rest_minutes", 0))
    max_per_day = int(constraints.get("max_matches_per_day", 0))  # 0 = unlimited (per category)

    # sort matches by round/order so earlier rounds scheduled first
    ordered = sorted(matches, key=lambda m: (m.get("round") or 0, m.get("order") or 0))
    used_slots = set()  # (date, ground_id, start)
    team_busy = {}       # team_id -> list of (date,start,end)
    day_count = {}       # date -> count
    unscheduled = []

    def team_ok(team_id, slot):
        if team_id is None:
            return True
        s0, e0 = slot["start"], slot["start"] + slot["dur"]
        info = team_info.get(team_id, {})
        # team-specific playable window
        af = info.get("available_from")
        at = info.get("available_to")
        if af and s0 < _parse_t(af):
            return False
        if at and e0 > _parse_t(at):
            return False
        # no back-to-back => require at least one match-length break between this team's matches
        eff_rest = max(min_rest, slot["dur"]) if info.get("no_back_to_back") else min_rest
        for (d, s, e) in team_busy.get(team_id, []):
            if d != slot["date"]:
                continue
            # overlap
            if s0 < e and s < e0:
                return False
            # rest gap
            gap = s0 - e if s0 >= e else s - e0
            if gap < eff_rest:
                return False
        return True

    for m in ordered:
        placed = False
        for slot in slots:
            key = (slot["date"], slot["ground_id"], slot["start"])
            if key in used_slots:
                continue
            if max_per_day and day_count.get(slot["date"], 0) >= max_per_day:
                continue
            if not team_ok(m["home_id"], slot) or not team_ok(m["away_id"], slot):
                continue
            # assign
            m["date"] = slot["date"]
            m["time"] = _fmt_t(slot["start"])
            m["ground_id"] = slot["ground_id"]
            used_slots.add(key)
            day_count[slot["date"]] = day_count.get(slot["date"], 0) + 1
            for tid in (m["home_id"], m["away_id"]):
                if tid:
                    team_busy.setdefault(tid, []).append((slot["date"], slot["start"], slot["start"] + slot["dur"]))
            placed = True
            break
        if not placed:
            unscheduled.append(m)

    conflicts = detect_conflicts(ordered, constraints, team_info)
    if unscheduled:
        conflicts.insert(0, {
            "type": "capacity", "severity": "error",
            "message": f"{len(unscheduled)} match(es) could not be scheduled within the available dates, grounds and time windows. Add more grounds, extend the date range, or relax rest/time constraints."
        })
    return ordered, unscheduled, conflicts


def detect_conflicts(matches, constraints, team_info=None):
    """Validate scheduled matches and produce human-readable conflicts."""
    team_info = team_info or {}
    conflicts = []
    min_rest = int(constraints.get("min_rest_minutes", 0))
    dur = int(constraints.get("match_duration_minutes", 90))
    earliest = _parse_t(constraints.get("earliest_time", "08:00"))
    latest = _parse_t(constraints.get("latest_time", "20:00"))
    scheduled = [m for m in matches if m.get("date") and m.get("time")]

    # ground double booking
    seen = {}
    for m in scheduled:
        s = _parse_t(m["time"])
        key = (m["date"], m.get("ground_id"))
        for om in seen.get(key, []):
            os_ = _parse_t(om["time"])
            if s < os_ + dur and os_ < s + dur:
                conflicts.append({
                    "type": "ground_clash", "severity": "error",
                    "message": f"Ground double-booked on {m['date']} at {m['time']} — two matches overlap on the same ground."
                })
        seen.setdefault(key, []).append(m)

    # team clashes / rest
    team_matches = {}
    for m in scheduled:
        for tid in (m.get("home_id"), m.get("away_id")):
            if tid:
                team_matches.setdefault(tid, []).append(m)
    for tid, ms in team_matches.items():
        info = team_info.get(tid, {})
        nb = info.get("no_back_to_back")
        af = info.get("available_from")
        at = info.get("available_to")
        # team playable-window violations
        for m in ms:
            s = _parse_t(m["time"])
            if af and s < _parse_t(af):
                conflicts.append({
                    "type": "team_availability", "severity": "warning",
                    "message": f"A team is scheduled at {m['time']} on {m['date']} but is only available from {af}."
                })
            if at and s + dur > _parse_t(at):
                conflicts.append({
                    "type": "team_availability", "severity": "warning",
                    "message": f"A team is scheduled at {m['time']} on {m['date']} but is only available until {at}."
                })
        ms_sorted = sorted(ms, key=lambda x: (x["date"], _parse_t(x["time"])))
        for i in range(len(ms_sorted) - 1):
            a, b = ms_sorted[i], ms_sorted[i + 1]
            if a["date"] != b["date"]:
                continue
            ae = _parse_t(a["time"]) + dur
            bs = _parse_t(b["time"])
            if bs < ae:
                conflicts.append({
                    "type": "team_clash", "severity": "error",
                    "message": f"A team is scheduled for two overlapping matches on {a['date']}."
                })
            elif nb and bs - ae < dur:
                conflicts.append({
                    "type": "back_to_back", "severity": "warning",
                    "message": f"A team plays back-to-back on {a['date']} ({a['time']} then {b['time']}) but is set to avoid back-to-back matches."
                })
            elif bs - ae < min_rest:
                conflicts.append({
                    "type": "rest_violation", "severity": "warning",
                    "message": f"A team has only {bs - ae} min rest on {a['date']} (minimum required is {min_rest} min)."
                })

    # time window
    for m in scheduled:
        s = _parse_t(m["time"])
        if s < earliest or s + dur > latest:
            conflicts.append({
                "type": "time_window", "severity": "warning",
                "message": f"Match on {m['date']} at {m['time']} falls outside the allowed window {constraints.get('earliest_time','08:00')}–{constraints.get('latest_time','20:00')}."
            })

    # mid-day break
    bs_c = constraints.get("break_start")
    be_c = constraints.get("break_end")
    if bs_c and be_c:
        b0, b1 = _parse_t(bs_c), _parse_t(be_c)
        for m in scheduled:
            s = _parse_t(m["time"])
            if s < b1 and b0 < s + dur:
                conflicts.append({
                    "type": "break_overlap", "severity": "warning",
                    "message": f"Match on {m['date']} at {m['time']} overlaps the scheduled break ({bs_c}–{be_c})."
                })
    return conflicts


def detect_all_conflicts(items):
    """Tournament-wide conflicts over already-placed matches (used by the Board)."""
    conflicts = []
    for it in items:
        conflicts += detect_conflicts(it["matches"], it["constraints"], it["team_info"])
    placed = []
    for it in items:
        d = int(it["constraints"].get("match_duration_minutes", 90))
        for m in it["matches"]:
            if m.get("date") and m.get("time") and m.get("ground_id"):
                placed.append((d, m))
    byg = defaultdict(list)
    for d, m in placed:
        byg[(m["date"], m["ground_id"])].append((d, m))
    for key, lst in byg.items():
        lst.sort(key=lambda dm: _parse_t(dm[1]["time"]))
        for i in range(len(lst) - 1):
            if _parse_t(lst[i + 1][1]["time"]) < _parse_t(lst[i][1]["time"]) + lst[i][0]:
                conflicts.append({"type": "ground_clash", "severity": "error",
                    "message": f"Ground double-booked on {lst[i][1]['date']} around {lst[i + 1][1]['time']} (two categories on the same ground)."})
    seen = set(); uniq = []
    for c in conflicts:
        k = (c["type"], c["message"])
        if k in seen:
            continue
        seen.add(k); uniq.append(c)
    return uniq


# ---------------------------------------------------------------------------
# REFEREE ASSIGNMENT
# ---------------------------------------------------------------------------

def assign_referees(placed, referees, keep_locked=True):
    """Assign a referee to each already-scheduled match.

    Strictly a post-scheduling pass: it only ever sets `referee_id`, never date/time/ground
    and never fixtures. Hard constraints: a referee cannot officiate two overlapping
    matches (including travel-free back-to-back on different grounds at the same instant)
    and cannot exceed their own `max_matches_per_day`. Soft objective: spread work evenly,
    preferring the least-loaded eligible official (experience breaks ties).

    placed: [{id, date, time, dur, ground_id, locked, referee_id}] — mutated in place.
    Returns (assigned_count, unassigned_matches, conflicts).
    """
    conflicts = []
    if not referees:
        if placed:
            conflicts.append({"type": "no_referees", "severity": "warning",
                "message": "No referees defined — matches were scheduled without officials. "
                           "Add referees in Grounds & Referees, then re-run assignment."})
        return 0, list(placed), conflicts

    busy = defaultdict(list)      # ref_id -> [(date, start, end)]
    day_count = defaultdict(int)  # (ref_id, date) -> count
    total = defaultdict(int)      # ref_id -> total matches

    # Respect referees already pinned on locked matches.
    for m in placed:
        if keep_locked and m.get("locked") and m.get("referee_id"):
            s = _parse_t(m["time"])
            busy[m["referee_id"]].append((m["date"], s, s + m["dur"]))
            day_count[(m["referee_id"], m["date"])] += 1
            total[m["referee_id"]] += 1

    targets = [m for m in placed
               if not (keep_locked and m.get("locked") and m.get("referee_id"))]
    targets.sort(key=lambda m: (m["date"], _parse_t(m["time"])))

    assigned, unassigned = 0, []
    for m in targets:
        s = _parse_t(m["time"])
        e = s + m["dur"]
        d = m["date"]
        best, best_key = None, None
        for r in referees:
            rid = r["id"]
            mx = int(r.get("max_matches_per_day") or 0)
            if mx and day_count[(rid, d)] >= mx:
                continue
            if any(od == d and s < oe and os_ < e for (od, os_, oe) in busy[rid]):
                continue
            # least loaded that day, then overall, then more experience first
            key = (day_count[(rid, d)], total[rid], -(r.get("experience_years") or 0), r.get("name") or "")
            if best_key is None or key < best_key:
                best, best_key = r, key
        if best is None:
            m["referee_id"] = None
            unassigned.append(m)
            continue
        rid = best["id"]
        m["referee_id"] = rid
        busy[rid].append((d, s, e))
        day_count[(rid, d)] += 1
        total[rid] += 1
        assigned += 1

    if unassigned:
        conflicts.append({"type": "referee_capacity", "severity": "warning",
            "message": f"{len(unassigned)} match(es) have no referee — every official was already "
                       "busy or at their daily limit. Add referees or raise their max matches/day."})
    return assigned, unassigned, conflicts


# ---------------------------------------------------------------------------
# STANDINGS
# ---------------------------------------------------------------------------

def compute_standings(teams, matches, points_config):
    win_p = points_config.get("win", 3)
    draw_p = points_config.get("draw", 1)
    loss_p = points_config.get("loss", 0)
    tiebreakers = points_config.get("tiebreakers", ["points", "goal_difference", "goals_for", "wins"])

    rows = {t["id"]: {
        "team_id": t["id"], "team_name": t["name"],
        "played": 0, "won": 0, "drawn": 0, "lost": 0,
        "gf": 0, "ga": 0, "gd": 0, "points": 0,
    } for t in teams}

    completed = [m for m in matches if m.get("status") == "completed"
                 and m.get("home_id") in rows and m.get("away_id") in rows
                 and m.get("home_score") is not None and m.get("away_score") is not None]

    for m in completed:
        h, a = rows[m["home_id"]], rows[m["away_id"]]
        hs, as_ = int(m["home_score"]), int(m["away_score"])
        h["played"] += 1; a["played"] += 1
        h["gf"] += hs; h["ga"] += as_
        a["gf"] += as_; a["ga"] += hs
        if hs > as_:
            h["won"] += 1; a["lost"] += 1
            h["points"] += win_p; a["points"] += loss_p
        elif hs < as_:
            a["won"] += 1; h["lost"] += 1
            a["points"] += win_p; h["points"] += loss_p
        else:
            h["drawn"] += 1; a["drawn"] += 1
            h["points"] += draw_p; a["points"] += draw_p

    for r in rows.values():
        r["gd"] = r["gf"] - r["ga"]

    def h2h_points(tid, other_ids):
        pts = 0
        for m in completed:
            if m["home_id"] == tid and m["away_id"] in other_ids:
                hs, as_ = int(m["home_score"]), int(m["away_score"])
                pts += win_p if hs > as_ else draw_p if hs == as_ else loss_p
            elif m["away_id"] == tid and m["home_id"] in other_ids:
                hs, as_ = int(m["home_score"]), int(m["away_score"])
                pts += win_p if as_ > hs else draw_p if hs == as_ else loss_p
        return pts

    def sort_key(r):
        key = []
        for tb in tiebreakers:
            if tb == "points":
                key.append(-r["points"])
            elif tb == "goal_difference":
                key.append(-r["gd"])
            elif tb == "goals_for":
                key.append(-r["gf"])
            elif tb == "wins":
                key.append(-r["won"])
            elif tb == "head_to_head":
                same = [x["team_id"] for x in rows.values() if x["points"] == r["points"]]
                key.append(-h2h_points(r["team_id"], set(same)))
        key.append(r["team_name"])
        return tuple(key)

    ranked = sorted(rows.values(), key=sort_key)
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    return ranked


# ---------------------------------------------------------------------------
# TOURNAMENT-LEVEL SCHEDULING (shared grounds across parallel categories)
# ---------------------------------------------------------------------------

def dates_in_range(start, end, exclude):
    s = datetime.fromisoformat(start).date()
    e = datetime.fromisoformat(end).date()
    out = []
    d = s
    while d <= e:
        if d.isoformat() not in exclude:
            out.append(d)
        d += timedelta(days=1)
    return out


def _t_from(tid, ti):
    v = (ti.get(tid, {}) or {}).get("available_from")
    return _parse_t(v) if v else 0


def _t_to(tid, ti):
    v = (ti.get(tid, {}) or {}).get("available_to")
    return _parse_t(v) if v else 24 * 60


def _team_date_ok(tid, diso, dobj, ti):
    if tid is None:
        return True
    info = ti.get(tid, {}) or {}
    av = info.get("available_dates") or []
    if av and diso not in av:
        return False
    if diso in (info.get("unavailable_dates") or []):
        return False
    dp = info.get("day_preference") or "any"
    weekend = dobj.weekday() >= 5
    if dp == "weekend" and not weekend:
        return False
    if dp == "weekday" and weekend:
        return False
    return True


def _team_day_ok(tid, diso, ti, team_day):
    if tid is None:
        return True
    mx = (ti.get(tid, {}) or {}).get("max_matches_per_day")
    if mx and team_day[(tid, diso)] >= int(mx):
        return False
    return True


def _team_time_ok(tid, diso, t, dur, min_rest, ti, team_busy):
    if tid is None:
        return True
    info = ti.get(tid, {}) or {}
    eff = max(min_rest, dur) if info.get("no_back_to_back") else min_rest
    s0, e0 = t, t + dur
    for (d, s, e) in team_busy.get(tid, []):
        if d != diso:
            continue
        if s0 < e and s < e0:
            return False
        gap = s0 - e if s0 >= e else s - e0
        if gap < eff:
            return False
    return True


def _fits(blocks, t, block_len):
    for (s, e) in blocks:
        if t < e and s < t + block_len:
            return False
    return True


DAY_MINUTES = 24 * 60

# Objective weights (lower total cost = better placement). Tuned so that spreading
# matches across grounds (parallelism -> earliest finish + balanced usage) dominates,
# then earliness of the slot, then packing, rest comfort and avoiding soft back-to-backs.
W_GROUND_BALANCE = 100000   # prefer the least-loaded ground on the day (parallel + balanced)
W_TIME = 1                  # prefer earlier start times (compact makespan)
W_IDLE = 20                 # prefer starting right after an existing match (less unused ground time)
W_SOFT_B2B = 5000           # penalise creating a near back-to-back for a team even when allowed
W_REST = 5                  # penalise shortfall below the comfortable rest per minute
COMFORT_REST_BONUS = 30     # minutes of rest beyond the hard minimum considered "comfortable"


def _team_name(tid, ti):
    return (ti.get(tid, {}) or {}).get("name") or "A team"


def _match_desc(m, it):
    home = _team_name(m.get("home_id"), it["team_info"]) if m.get("home_id") else (m.get("home_source", {}) or {}).get("group", "TBD")
    away = _team_name(m.get("away_id"), it["team_info"]) if m.get("away_id") else (m.get("away_source", {}) or {}).get("group", "TBD")
    label = m.get("label") or m.get("group") or (f"Round {m.get('round')}" if m.get("round") else "Match")
    return f"{home} v {away} ({label})"


def _feeder_map(items):
    """Map next_match_id -> [feeder match ids]; and cat_id -> [group/league match ids]."""
    reverse_feed = defaultdict(list)
    group_by_cat = defaultdict(list)
    for it in items:
        for m in it["matches"] + it.get("locked", []):
            nmid = m.get("next_match_id")
            if nmid:
                reverse_feed[nmid].append(m.get("id"))
            if m.get("stage") in ("group", "league"):
                group_by_cat[it["cat_id"]].append(m.get("id"))
    return reverse_feed, group_by_cat


def _score_slot(g, t, diso, dur, min_rest, home, away, is_final,
                ground_blocks, ground_day_count, team_busy):
    """Multi-objective cost for placing a match on ground g at minute t. Lower is better.
    Modular: add new terms here to introduce future soft constraints."""
    gid = g["id"]
    cost = 0.0
    # 1) Balance / parallelism: favour grounds with fewer matches already that day.
    cost += W_GROUND_BALANCE * ground_day_count.get((gid, diso), 0)
    # 2) Makespan: earlier is better (finals prefer later so they close the event).
    cost += W_TIME * (DAY_MINUTES - t if is_final else t)
    # 3) Packing: minimise idle ground time before this match.
    ends = [e for (s, e) in ground_blocks.get((gid, diso), []) if e <= t]
    if ends:
        cost += W_IDLE * (t - max(ends))
    # 4) Rest comfort + soft back-to-back for each real team.
    for tid in (home, away):
        if not tid:
            continue
        for (d, s, e) in team_busy.get(tid, []):
            if d != diso:
                continue
            gap = (t - e) if t >= e else (s - (t + dur))
            if gap < 0:
                continue
            if gap < dur:
                cost += W_SOFT_B2B
            comfort = min_rest + COMFORT_REST_BONUS
            if gap < comfort:
                cost += W_REST * (comfort - gap)
    return cost


def _suggestions(reasons, items, grounds, tour_dates):
    """Targeted suggestions based on the aggregated blocking reasons."""
    out = []
    if reasons.get("grounds_busy"):
        out.append(f"Add more grounds or playing days — the {len(grounds)} ground(s) over {len(tour_dates)} day(s) are full during the required playing windows.")
    if reasons.get("window_too_tight"):
        out.append("Widen the playing window — the category hours, ground open/close times or team playable windows leave no room for a full match plus buffer.")
    if reasons.get("cat_day_full") or reasons.get("team_day_full"):
        out.append("Increase 'max matches per day' for the affected categories or teams.")
    if reasons.get("team_date"):
        out.append("Relax team unavailable dates or weekday/weekend preferences.")
    if reasons.get("dependency"):
        out.append("Later knockout rounds need earlier rounds finished first — add days or grounds so feeder matches complete in time.")
    if reasons.get("grounds_missing"):
        out.append("Reassign grounds to the affected categories — the grounds they were restricted to have been deleted.")
    if reasons.get("rest_or_b2b"):
        out.append("Reduce minimum rest, or turn off 'no back-to-back' for some teams.")
    if not out:
        out.append("Extend the tournament date range, add grounds, or relax time/rest constraints.")
    return out


def schedule_matches(items, grounds, tour_dates):
    """Global, quality-first scheduler shared across all categories on common grounds.

    Responsibility: assign every already-generated fixture the best possible
    (date, time, ground). It never changes opponents or fixtures. For each match it
    evaluates all feasible slots against the live tournament state and commits the
    lowest-cost one (see _score_slot), rather than the first that fits.

    items: [{cat_id, constraints, matches, team_info, ground_ids, locked}]
    Returns (scheduled, unscheduled, conflicts, suggestions)."""
    all_targets = [m for it in items for m in it["matches"]]
    if not grounds:
        return [], all_targets, [{"type": "no_grounds", "severity": "error",
                "message": "No grounds defined for this tournament. Add at least one ground before scheduling."}], \
               ["Add at least one ground in Grounds & Referees."]

    gmap = {g["id"]: g for g in grounds}
    date_index = {d.isoformat(): i for i, d in enumerate(tour_dates)}
    ground_blocks = defaultdict(list)     # (ground_id, date) -> [(start, end_block)]
    ground_day_count = defaultdict(int)   # (ground_id, date) -> match count
    team_busy = defaultdict(list)         # team_id -> [(date, start, end)]
    team_day = defaultdict(int)           # (team_id, date) -> count
    cat_day = defaultdict(int)            # (cat_id, date) -> count
    placed_end = {}                       # match_id -> (date_index, end_minute) for progression

    reverse_feed, group_by_cat = _feeder_map(items)

    # A category explicitly restricted to grounds that no longer exist must fail
    # loudly instead of silently spilling onto every ground.
    pre_conflicts = []
    dead_cats = set()
    for it in items:
        _gids = it.get("ground_ids") or []
        if _gids and not any(g in gmap for g in _gids):
            dead_cats.add(it["cat_id"])
            pre_conflicts.append({"type": "no_grounds", "severity": "error",
                "message": "A category is restricted to ground(s) that no longer exist — "
                           "reassign its grounds (Schedule tab) before scheduling."})

    # Pre-book locked/already-placed matches so the scheduler works around them.
    for it in items:
        c = it["constraints"]
        block = int(c.get("match_duration_minutes", 90)) + int(c.get("slot_gap_minutes", 0))
        dur = int(c.get("match_duration_minutes", 90))
        for m in it.get("locked", []):
            if m.get("date") and m.get("time") and m.get("ground_id"):
                t = _parse_t(m["time"])
                ground_blocks[(m["ground_id"], m["date"])].append((t, t + block))
                ground_day_count[(m["ground_id"], m["date"])] += 1
                for tid in (m.get("home_id"), m.get("away_id")):
                    if tid:
                        team_busy[tid].append((m["date"], t, t + dur))
                        team_day[(tid, m["date"])] += 1
                cat_day[(it["cat_id"], m["date"])] += 1
                if m.get("date") in date_index:
                    placed_end[m.get("id")] = (date_index[m["date"]], t + dur)

    # Ordering: group/league before knockout (feeders first); earlier rounds first;
    # most-constrained categories (tighter playing window) first; then stable order.
    def _winsize(it):
        c = it["constraints"]
        return _parse_t(c.get("latest_time", "20:00")) - _parse_t(c.get("earliest_time", "08:00"))

    flat = []
    for it in items:
        for m in it["matches"]:
            stage_rank = 1 if m.get("stage") == "knockout" else 0
            flat.append((stage_rank, m.get("round") or 0, _winsize(it), m.get("order") or 0, it, m))
    flat.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    flat = [(it, m) for *_ , it, m in flat]

    unscheduled = []
    for it, m in flat:
        if it["cat_id"] in dead_cats:
            m["_fail_reasons"] = {"grounds_missing": 1}
            m["_desc"] = _match_desc(m, it)
            unscheduled.append(m)
            continue
        c = it["constraints"]
        dur = int(c.get("match_duration_minutes", 90))
        buf = int(c.get("slot_gap_minutes", 0))
        block = dur + buf
        cat_lo = _parse_t(c.get("earliest_time", "08:00"))
        cat_hi = _parse_t(c.get("latest_time", "20:00"))
        min_rest = int(c.get("min_rest_minutes", 0))
        max_cat_day = int(c.get("max_matches_per_day", 0))
        cat_unavail = set(c.get("unavailable_dates", []))
        bstart = c.get("break_start"); bend = c.get("break_end")
        brk = (_parse_t(bstart), _parse_t(bend)) if bstart and bend else None
        gids = it.get("ground_ids") or list(gmap.keys())
        cat_grounds = [gmap[g] for g in gids if g in gmap] or grounds
        cat_grounds = sorted(cat_grounds, key=lambda x: x.get("priority", 1))
        ti = it["team_info"]
        home, away = m.get("home_id"), m.get("away_id")
        is_final = m.get("label") == "Final"

        # Chronological progression: this match must start after every feeder finishes.
        feeders = list(reverse_feed.get(m.get("id"), []))
        if m.get("stage") == "knockout":
            feeders += group_by_cat.get(it["cat_id"], [])
        bound_di, bound_end = -1, 0
        dep_unresolved = False
        for f in feeders:
            if f in placed_end:
                if placed_end[f] > (bound_di, bound_end):
                    bound_di, bound_end = placed_end[f]
            else:
                dep_unresolved = True

        reasons = defaultdict(int)
        placed = False
        for dobj in tour_dates:
            diso = dobj.isoformat()
            di = date_index[diso]
            if di < bound_di:
                reasons["dependency"] += 1
                continue
            if diso in cat_unavail:
                continue
            if max_cat_day and cat_day[(it["cat_id"], diso)] >= max_cat_day:
                reasons["cat_day_full"] += 1
                continue
            if not _team_date_ok(home, diso, dobj, ti) or not _team_date_ok(away, diso, dobj, ti):
                reasons["team_date"] += 1
                continue
            if not _team_day_ok(home, diso, ti, team_day) or not _team_day_ok(away, diso, ti, team_day):
                reasons["team_day_full"] += 1
                continue

            day_floor = bound_end if di == bound_di else 0
            candidates = []  # (cost, ground, t)
            for g in cat_grounds:
                lo = max(cat_lo, _parse_t(g.get("open_time") or _fmt_t(cat_lo)),
                         _t_from(home, ti), _t_from(away, ti), day_floor)
                hi = min(cat_hi, _parse_t(g.get("close_time") or _fmt_t(cat_hi)),
                         _t_to(home, ti), _t_to(away, ti))
                if lo + dur > hi:
                    reasons["window_too_tight"] += 1
                    continue
                blocks = ground_blocks[(g["id"], diso)]
                edges = sorted(set([lo] + ([brk[1]] if brk else []) + [e for (s, e) in blocks if e >= lo]))
                found_on_ground = False
                for t in edges:
                    if t + dur > hi:
                        break
                    if not _fits(blocks, t, block):
                        continue
                    if brk and t < brk[1] and brk[0] < t + dur:
                        continue
                    if not (_team_time_ok(home, diso, t, dur, min_rest, ti, team_busy)
                            and _team_time_ok(away, diso, t, dur, min_rest, ti, team_busy)):
                        reasons["rest_or_b2b"] += 1
                        continue
                    cost = _score_slot(g, t, diso, dur, min_rest, home, away, is_final,
                                       ground_blocks, ground_day_count, team_busy)
                    candidates.append((cost, g, t))
                    found_on_ground = True
                if not found_on_ground:
                    reasons["grounds_busy"] += 1

            if candidates:
                # Commit the best-scoring slot on the earliest feasible day.
                candidates.sort(key=lambda c: c[0])
                _, g, t = candidates[0]
                ground_blocks[(g["id"], diso)].append((t, t + block))
                ground_day_count[(g["id"], diso)] += 1
                for tid in (home, away):
                    if tid:
                        team_busy[tid].append((diso, t, t + dur))
                        team_day[(tid, diso)] += 1
                cat_day[(it["cat_id"], diso)] += 1
                m["date"] = diso
                m["time"] = _fmt_t(t)
                m["ground_id"] = g["id"]
                placed_end[m.get("id")] = (di, t + dur)
                placed = True
                break

        if not placed:
            m["_fail_reasons"] = dict(reasons)
            m["_desc"] = _match_desc(m, it)
            if dep_unresolved:
                m["_fail_reasons"]["dependency"] = m["_fail_reasons"].get("dependency", 0) + 1
            unscheduled.append(m)

    scheduled = [m for it, m in flat if m.get("date")]

    # ---- Validation: recompute conflicts over the committed schedule ----
    conflicts = list(pre_conflicts)
    for it in items:
        conflicts += detect_conflicts(it["matches"] + it.get("locked", []), it["constraints"], it["team_info"])
    placed_all = []
    for it in items:
        for m in it["matches"] + it.get("locked", []):
            if m.get("date") and m.get("time") and m.get("ground_id"):
                placed_all.append((int(it["constraints"].get("match_duration_minutes", 90)), m))
    byg = defaultdict(list)
    for dur_, m in placed_all:
        byg[(m["date"], m["ground_id"])].append((dur_, m))
    for key, lst in byg.items():
        lst.sort(key=lambda dm: _parse_t(dm[1]["time"]))
        for i in range(len(lst) - 1):
            d1, m1 = lst[i]
            if _parse_t(lst[i + 1][1]["time"]) < _parse_t(m1["time"]) + d1:
                conflicts.append({"type": "ground_clash", "severity": "error",
                    "message": f"Ground double-booked on {m1['date']} around {lst[i + 1][1]['time']} (two categories on the same ground)."})

    seen = set(); uniq = []
    for cft in conflicts:
        k = (cft["type"], cft["message"])
        if k in seen:
            continue
        seen.add(k); uniq.append(cft)

    suggestions = []
    if unscheduled:
        agg = defaultdict(int)
        for m in unscheduled:
            for k, v in (m.get("_fail_reasons") or {}).items():
                agg[k] += v
        uniq.insert(0, {"type": "capacity", "severity": "error",
            "message": f"{len(unscheduled)} match(es) could not be placed within the available days, grounds and constraints. See details and suggestions below."})
        for m in unscheduled[:8]:
            reasons = m.get("_fail_reasons") or {}
            dominant = max(reasons, key=reasons.get) if reasons else None
            why = {
                "grounds_busy": "all grounds were fully booked during its allowed playing window",
                "window_too_tight": "its playing window is too short for a full match plus buffer",
                "cat_day_full": "the category's max-matches-per-day limit was reached every day",
                "team_day_full": "a team's max-matches-per-day limit was reached every day",
                "team_date": "the teams' available/unavailable dates left no valid day",
                "rest_or_b2b": "rest / no-back-to-back rules blocked every open slot",
                "dependency": "the earlier rounds it depends on could not finish in time",
                "grounds_missing": "its category is restricted to grounds that no longer exist",
            }.get(dominant, "no valid slot satisfied all constraints")
            uniq.append({"type": "unplaced_match", "severity": "error",
                "message": f"{m.get('_desc', 'A match')} could not be scheduled — {why}."})
            m.pop("_fail_reasons", None); m.pop("_desc", None)
        suggestions = _suggestions(agg, items, grounds, tour_dates)

    return scheduled, unscheduled, uniq, suggestions

