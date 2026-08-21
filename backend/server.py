from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import re
import uuid
from datetime import datetime, timezone

from scheduling import (generate_matches, auto_schedule, detect_conflicts, compute_standings,
                        schedule_matches, dates_in_range, detect_all_conflicts, assign_referees)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="TournamentOS")
api_router = APIRouter(prefix="/api")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


def build_team_info(teams):
    return {t["id"]: {
        "name": t.get("name"),
        "available_from": t.get("available_from"), "available_to": t.get("available_to"),
        "no_back_to_back": t.get("no_back_to_back", False),
        "available_dates": t.get("available_dates") or [],
        "unavailable_dates": t.get("unavailable_dates") or [],
        "day_preference": t.get("day_preference") or "any",
        "max_matches_per_day": t.get("max_matches_per_day"),
    } for t in teams}


# --------------------------- MODELS ---------------------------
DEFAULT_POINTS = {"win": 3, "draw": 1, "loss": 0,
                  "tiebreakers": ["points", "goal_difference", "goals_for", "wins"]}
DEFAULT_CONSTRAINTS = {
    "start_date": None, "end_date": None,
    "earliest_time": "08:00", "latest_time": "20:00",
    "match_duration_minutes": 90, "slot_gap_minutes": 30,
    "min_rest_minutes": 60, "max_matches_per_day": 0,
    "break_start": None, "break_end": None,
    "unavailable_dates": [],
}


class Tournament(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    sport: str = "Football"
    organizer: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    status: str = "planning"
    created_at: str = Field(default_factory=now_iso)


class Category(BaseModel):
    id: str = Field(default_factory=new_id)
    tournament_id: str = ""
    name: str
    format: str = "league_single"
    seeded: bool = False
    num_groups: int = 2
    qualifiers_per_group: int = 2
    age_restriction: Optional[str] = None
    custom_rules: Optional[str] = None
    points_config: Dict[str, Any] = Field(default_factory=lambda: dict(DEFAULT_POINTS))
    constraints: Dict[str, Any] = Field(default_factory=lambda: dict(DEFAULT_CONSTRAINTS))
    ground_ids: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class Team(BaseModel):
    id: str = Field(default_factory=new_id)
    tournament_id: str = ""
    category_id: str = ""
    name: str
    short_name: Optional[str] = None
    coach: Optional[str] = None
    manager: Optional[str] = None
    contact: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    association: Optional[str] = None
    seed: Optional[int] = None
    available_from: Optional[str] = None
    available_to: Optional[str] = None
    no_back_to_back: bool = False
    available_dates: List[str] = Field(default_factory=list)
    unavailable_dates: List[str] = Field(default_factory=list)
    day_preference: str = "any"
    max_matches_per_day: Optional[int] = None
    created_at: str = Field(default_factory=now_iso)


class Ground(BaseModel):
    id: str = Field(default_factory=new_id)
    tournament_id: str = ""
    name: str
    capacity: Optional[int] = None
    surface: Optional[str] = None
    lighting: bool = False
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    priority: int = 1
    notes: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class Referee(BaseModel):
    id: str = Field(default_factory=new_id)
    tournament_id: str = ""
    name: str
    certification: Optional[str] = None
    experience_years: Optional[int] = None
    max_matches_per_day: int = 3
    phone: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")
MATCH_STATUSES = ("scheduled", "completed", "bye", "pending")


class MatchUpdate(BaseModel):
    """Whitelisted, validated payload for PUT /matches/{mid}.
    Immutable fields (id, tournament_id, category_id, round, order, stage, group,
    bracket links) are intentionally absent; unknown fields are rejected."""
    model_config = {"extra": "forbid"}
    date: Optional[str] = None
    time: Optional[str] = None
    ground_id: Optional[str] = None
    referee_id: Optional[str] = None
    home_id: Optional[str] = None
    away_id: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: Optional[str] = None
    locked: Optional[bool] = None
    notes: Optional[str] = None


async def get_or_404(coll, id, name="Resource"):
    doc = await coll.find_one({"id": id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"{name} not found")
    return doc


# --------------------------- TOURNAMENTS ---------------------------
@api_router.get("/")
async def root():
    return {"message": "TournamentOS API", "status": "ok"}


@api_router.post("/tournaments", response_model=Tournament)
async def create_tournament(t: Tournament):
    await db.tournaments.insert_one(t.model_dump())
    return t


@api_router.get("/tournaments")
async def list_tournaments():
    items = await db.tournaments.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for t in items:
        t["category_count"] = await db.categories.count_documents({"tournament_id": t["id"]})
        t["team_count"] = await db.teams.count_documents({"tournament_id": t["id"]})
    return items


@api_router.get("/tournaments/{tid}")
async def get_tournament(tid: str):
    return await get_or_404(db.tournaments, tid, "Tournament")


@api_router.put("/tournaments/{tid}")
async def update_tournament(tid: str, data: Dict[str, Any]):
    data.pop("id", None); data.pop("_id", None)
    await db.tournaments.update_one({"id": tid}, {"$set": data})
    return await get_or_404(db.tournaments, tid, "Tournament")


@api_router.delete("/tournaments/{tid}")
async def delete_tournament(tid: str):
    await db.tournaments.delete_one({"id": tid})
    for c in ("categories", "teams", "grounds", "referees", "matches"):
        await db[c].delete_many({"tournament_id": tid})
    return {"deleted": True}


# --------------------------- CATEGORIES ---------------------------
@api_router.post("/tournaments/{tid}/categories", response_model=Category)
async def create_category(tid: str, c: Category):
    c.tournament_id = tid
    await db.categories.insert_one(c.model_dump())
    return c


@api_router.get("/tournaments/{tid}/categories")
async def list_categories(tid: str):
    items = await db.categories.find({"tournament_id": tid}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    for c in items:
        c["team_count"] = await db.teams.count_documents({"category_id": c["id"]})
        c["match_count"] = await db.matches.count_documents({"category_id": c["id"]})
    return items


@api_router.get("/categories/{cid}")
async def get_category(cid: str):
    return await get_or_404(db.categories, cid, "Category")


@api_router.put("/categories/{cid}")
async def update_category(cid: str, data: Dict[str, Any]):
    data.pop("id", None); data.pop("_id", None)
    await db.categories.update_one({"id": cid}, {"$set": data})
    return await get_or_404(db.categories, cid, "Category")


@api_router.delete("/categories/{cid}")
async def delete_category(cid: str):
    await db.categories.delete_one({"id": cid})
    await db.teams.delete_many({"category_id": cid})
    await db.matches.delete_many({"category_id": cid})
    return {"deleted": True}


# --------------------------- TEAMS ---------------------------
@api_router.post("/categories/{cid}/teams", response_model=Team)
async def create_team(cid: str, t: Team):
    cat = await get_or_404(db.categories, cid, "Category")
    t.category_id = cid
    t.tournament_id = cat["tournament_id"]
    await db.teams.insert_one(t.model_dump())
    return t


@api_router.get("/categories/{cid}/teams")
async def list_teams(cid: str):
    return await db.teams.find({"category_id": cid}, {"_id": 0}).sort("created_at", 1).to_list(5000)


@api_router.put("/teams/{tid}")
async def update_team(tid: str, data: Dict[str, Any]):
    data.pop("id", None); data.pop("_id", None)
    await db.teams.update_one({"id": tid}, {"$set": data})
    return await get_or_404(db.teams, tid, "Team")


@api_router.delete("/teams/{tid}")
async def delete_team(tid: str):
    team = await get_or_404(db.teams, tid, "Team")
    n = await db.matches.count_documents({
        "category_id": team["category_id"],
        "$or": [{"home_id": tid}, {"away_id": tid}],
    })
    if n:
        raise HTTPException(409, f"'{team['name']}' appears in {n} fixture(s). "
                                 "Clear or regenerate the category's fixtures before deleting this team.")
    await db.teams.delete_one({"id": tid})
    return {"deleted": True}


# --------------------------- GROUNDS ---------------------------
@api_router.post("/tournaments/{tid}/grounds", response_model=Ground)
async def create_ground(tid: str, g: Ground):
    g.tournament_id = tid
    await db.grounds.insert_one(g.model_dump())
    return g


@api_router.get("/tournaments/{tid}/grounds")
async def list_grounds(tid: str):
    return await db.grounds.find({"tournament_id": tid}, {"_id": 0}).sort("priority", 1).to_list(1000)


@api_router.put("/grounds/{gid}")
async def update_ground(gid: str, data: Dict[str, Any]):
    data.pop("id", None); data.pop("_id", None)
    await db.grounds.update_one({"id": gid}, {"$set": data})
    return await get_or_404(db.grounds, gid, "Ground")


@api_router.delete("/grounds/{gid}")
async def delete_ground(gid: str):
    await db.grounds.delete_one({"id": gid})
    return {"deleted": True}


# --------------------------- REFEREES ---------------------------
@api_router.post("/tournaments/{tid}/referees", response_model=Referee)
async def create_referee(tid: str, r: Referee):
    r.tournament_id = tid
    await db.referees.insert_one(r.model_dump())
    return r


@api_router.get("/tournaments/{tid}/referees")
async def list_referees(tid: str):
    return await db.referees.find({"tournament_id": tid}, {"_id": 0}).sort("created_at", 1).to_list(1000)


@api_router.put("/referees/{rid}")
async def update_referee(rid: str, data: Dict[str, Any]):
    data.pop("id", None); data.pop("_id", None)
    await db.referees.update_one({"id": rid}, {"$set": data})
    return await get_or_404(db.referees, rid, "Referee")


@api_router.delete("/referees/{rid}")
async def delete_referee(rid: str):
    await db.referees.delete_one({"id": rid})
    return {"deleted": True}


# --------------------------- FIXTURES / MATCHES ---------------------------
@api_router.post("/categories/{cid}/generate-fixtures")
async def gen_fixtures(cid: str):
    cat = await get_or_404(db.categories, cid, "Category")
    teams = await db.teams.find({"category_id": cid}, {"_id": 0}).to_list(5000)
    if len(teams) < 2:
        raise HTTPException(400, "Add at least 2 teams before generating fixtures.")
    locked_count = await db.matches.count_documents({"category_id": cid, "locked": True})
    if locked_count:
        raise HTTPException(409, f"{locked_count} locked match(es) exist in this category. "
                                 "Unlock them (or clear all matches) before regenerating fixtures, "
                                 "otherwise the kept fixtures would duplicate the new ones.")
    await db.matches.delete_many({"category_id": cid})
    raw = generate_matches(cat, teams)
    docs = []
    for m in raw:
        home, away = m.get("home_id"), m.get("away_id")
        if m.get("is_bye"):
            status = "bye"
        elif home and away:
            status = "scheduled"
        elif m.get("stage") == "knockout":
            status = "pending"  # awaiting winners from earlier rounds
        else:
            status = "scheduled"
        docs.append({
            "id": m.get("id") or new_id(), "tournament_id": cat["tournament_id"], "category_id": cid,
            "round": m.get("round"), "group": m.get("group"), "stage": m.get("stage"),
            "label": m.get("label"), "order": m.get("order"), "bracket_pos": m.get("bracket_pos"),
            "next_match_id": m.get("next_match_id"), "next_slot": m.get("next_slot"),
            "home_source": m.get("home_source"), "away_source": m.get("away_source"),
            "home_id": home, "away_id": away,
            "home_score": None, "away_score": None,
            "date": None, "time": None, "ground_id": None, "referee_id": None,
            "status": status,
            "locked": False, "notes": None, "created_at": now_iso(),
        })
    if docs:
        await db.matches.insert_many(docs)
    return {"generated": len(docs)}


@api_router.get("/categories/{cid}/matches")
async def list_matches(cid: str):
    return await db.matches.find({"category_id": cid}, {"_id": 0}).sort([("round", 1), ("order", 1)]).to_list(10000)


@api_router.put("/matches/{mid}")
async def update_match(mid: str, upd: MatchUpdate):
    data = upd.model_dump(exclude_unset=True)
    if data.get("date") is not None and not DATE_RE.match(data["date"]):
        raise HTTPException(422, "date must be YYYY-MM-DD")
    if data.get("time") is not None and not TIME_RE.match(data["time"]):
        raise HTTPException(422, "time must be HH:MM (24h)")
    if data.get("status") is not None and data["status"] not in MATCH_STATUSES:
        raise HTTPException(422, f"status must be one of {MATCH_STATUSES}")
    existing = await get_or_404(db.matches, mid, "Match")
    if existing.get("locked") and data.get("locked") is not False \
            and any(k in data for k in ("date", "time", "ground_id")):
        raise HTTPException(409, "Match is locked — unlock it before moving it.")
    # knockout matches must produce a winner
    if existing.get("stage") == "knockout" \
            and data.get("home_score") is not None and data.get("away_score") is not None \
            and data["home_score"] == data["away_score"]:
        raise HTTPException(422, "Knockout matches cannot end in a draw — enter a decisive score "
                                 "(after extra time / penalties).")
    # a match is completed only when BOTH scores are present
    if "home_score" in data and "away_score" in data \
            and data["home_score"] is not None and data["away_score"] is not None:
        data.setdefault("status", "completed")
    if data:
        await db.matches.update_one({"id": mid}, {"$set": data})
    m = await get_or_404(db.matches, mid, "Match")
    # Knockout: auto-advance the winner into the next round
    if m.get("stage") == "knockout" and m.get("next_match_id"):
        winner = None
        hs, as_ = m.get("home_score"), m.get("away_score")
        if hs is not None and as_ is not None:
            if hs > as_:
                winner = m.get("home_id")
            elif as_ > hs:
                winner = m.get("away_id")
        slot = m.get("next_slot")
        await db.matches.update_one({"id": m["next_match_id"]}, {"$set": {f"{slot}_id": winner}})
        nm = await db.matches.find_one({"id": m["next_match_id"]}, {"_id": 0})
        if nm and nm.get("home_id") and nm.get("away_id") and nm.get("status") == "pending":
            await db.matches.update_one({"id": nm["id"]}, {"$set": {"status": "scheduled"}})
        elif nm and (not nm.get("home_id") or not nm.get("away_id")) and nm.get("status") != "completed":
            await db.matches.update_one({"id": nm["id"]}, {"$set": {"status": "pending"}})
    return m


@api_router.delete("/categories/{cid}/matches")
async def clear_matches(cid: str):
    await db.matches.delete_many({"category_id": cid})
    return {"cleared": True}


@api_router.post("/categories/{cid}/seed-knockout")
async def seed_knockout(cid: str):
    cat = await get_or_404(db.categories, cid, "Category")
    if cat.get("format") != "groups_knockout":
        raise HTTPException(400, "Seeding is only available for the Groups + Knockout format.")
    teams = await db.teams.find({"category_id": cid}, {"_id": 0}).to_list(5000)
    matches = await db.matches.find({"category_id": cid}, {"_id": 0}).to_list(10000)
    ko = [m for m in matches if m.get("stage") == "knockout"]
    if not ko:
        raise HTTPException(400, "Generate fixtures first — no knockout bracket found.")
    points = {**DEFAULT_POINTS, **(cat.get("points_config") or {})}
    group_names = sorted({m["group"] for m in matches if m.get("group")})
    ranked = {}
    for g in group_names:
        gm = [m for m in matches if m.get("group") == g]
        ids = set()
        for m in gm:
            ids.add(m.get("home_id")); ids.add(m.get("away_id"))
        gteams = [t for t in teams if t["id"] in ids]
        ranked[g] = compute_standings(gteams, gm, points)

    by_id = {m["id"]: m for m in ko}
    for m in ko:
        m["home_score"] = None; m["away_score"] = None; m["is_bye"] = False
        if m["round"] != 1:
            m["home_id"] = None; m["away_id"] = None
        m["status"] = "pending"
    # resolve round-1 slots from group standings
    for m in ko:
        if m["round"] != 1:
            continue
        for side in ("home", "away"):
            src = m.get(f"{side}_source")
            tid = None
            if src:
                lst = ranked.get(src["group"], [])
                if len(lst) >= src["pos"]:
                    tid = lst[src["pos"] - 1]["team_id"]
            m[f"{side}_id"] = tid
    # byes + statuses for round 1, advance winners
    for m in ko:
        if m["round"] != 1:
            continue
        h, a = m.get("home_id"), m.get("away_id")
        w = None
        if h and a:
            m["status"] = "scheduled"
        elif h and not a:
            m["status"] = "bye"; m["is_bye"] = True; w = h
        elif a and not h:
            m["status"] = "bye"; m["is_bye"] = True; w = a
        if w and m.get("next_match_id") and m["next_match_id"] in by_id:
            by_id[m["next_match_id"]][m["next_slot"] + "_id"] = w
    for m in ko:
        if m["round"] != 1 and m.get("home_id") and m.get("away_id"):
            m["status"] = "scheduled"
    for m in ko:
        await db.matches.update_one({"id": m["id"]}, {"$set": {
            "home_id": m.get("home_id"), "away_id": m.get("away_id"),
            "home_score": None, "away_score": None, "status": m["status"]
        }})
    return {"seeded": True, "qualifiers": sum(1 for m in ko if m["round"] == 1) * 2}


# --------------------------- SCHEDULING ---------------------------
async def _assign_and_persist_referees(tid: str):
    """Post-scheduling pass over every placed match in a tournament.
    Only ever writes referee_id. Returns (assigned, unassigned, conflicts)."""
    referees = await db.referees.find({"tournament_id": tid}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    cats = await db.categories.find({"tournament_id": tid}, {"_id": 0}).to_list(1000)
    dur_by_cat = {c["id"]: int({**DEFAULT_CONSTRAINTS, **(c.get("constraints") or {})}
                               .get("match_duration_minutes", 90)) for c in cats}
    ms = await db.matches.find(
        {"tournament_id": tid, "date": {"$ne": None}, "time": {"$ne": None}}, {"_id": 0}).to_list(20000)
    placed = [{"id": m["id"], "date": m["date"], "time": m["time"],
               "dur": dur_by_cat.get(m["category_id"], 90), "ground_id": m.get("ground_id"),
               "locked": m.get("locked", False), "referee_id": m.get("referee_id")}
              for m in ms if m.get("status") != "bye"]
    assigned, unassigned, conflicts = assign_referees(placed, referees)
    for p in placed:
        await db.matches.update_one({"id": p["id"]}, {"$set": {"referee_id": p.get("referee_id")}})
    return assigned, len(unassigned), conflicts


async def _category_grounds(cat):
    gids = cat.get("ground_ids") or []
    if gids:
        return await db.grounds.find({"id": {"$in": gids}}, {"_id": 0}).to_list(1000)
    return await db.grounds.find({"tournament_id": cat["tournament_id"]}, {"_id": 0}).to_list(1000)


@api_router.post("/categories/{cid}/auto-schedule")
async def do_schedule(cid: str):
    cat = await get_or_404(db.categories, cid, "Category")
    tour = await get_or_404(db.tournaments, cat["tournament_id"], "Tournament")
    constraints = {**DEFAULT_CONSTRAINTS, **(cat.get("constraints") or {})}
    start = constraints.get("start_date") or tour.get("start_date")
    end = constraints.get("end_date") or tour.get("end_date") or start
    if not start:
        raise HTTPException(400, "Set tournament dates or category start/end dates before scheduling.")
    grounds = await _category_grounds(cat)
    teams = await db.teams.find({"category_id": cid}, {"_id": 0}).to_list(5000)
    ti = build_team_info(teams)
    allm = await db.matches.find({"category_id": cid}, {"_id": 0}).to_list(10000)
    targets = [m for m in allm if not m.get("locked") and m.get("home_id") and m.get("away_id") and m.get("status") != "bye"]
    if not targets:
        raise HTTPException(400, "Generate fixtures before scheduling.")
    locked = [m for m in allm if m.get("locked") and m.get("date")]
    for m in targets:
        m["date"] = None; m["time"] = None; m["ground_id"] = None
    tour_dates = dates_in_range(start, end, set(constraints.get("unavailable_dates", [])))
    item = {"cat_id": cid, "constraints": constraints, "matches": targets,
            "team_info": ti, "ground_ids": cat.get("ground_ids"), "locked": locked}
    scheduled, unsch, conflicts, suggestions = schedule_matches([item], grounds, tour_dates)
    for m in targets:
        await db.matches.update_one({"id": m["id"]}, {"$set": {
            "date": m.get("date"), "time": m.get("time"), "ground_id": m.get("ground_id")}})
    ref_assigned, ref_unassigned, ref_conflicts = await _assign_and_persist_referees(cat["tournament_id"])
    return {"scheduled": len(scheduled), "unscheduled": len(unsch),
            "conflicts": conflicts + ref_conflicts, "suggestions": suggestions,
            "referees_assigned": ref_assigned, "referees_unassigned": ref_unassigned}


@api_router.post("/tournaments/{tid}/auto-schedule")
async def schedule_tournament_ep(tid: str):
    tour = await get_or_404(db.tournaments, tid, "Tournament")
    start = tour.get("start_date"); end = tour.get("end_date") or start
    if not start:
        raise HTTPException(400, "Set the tournament start and end dates before scheduling.")
    grounds = await db.grounds.find({"tournament_id": tid}, {"_id": 0}).to_list(1000)
    cats = await db.categories.find({"tournament_id": tid}, {"_id": 0}).to_list(1000)
    items = []; all_targets = []
    for c in cats:
        constraints = {**DEFAULT_CONSTRAINTS, **(c.get("constraints") or {})}
        teams = await db.teams.find({"category_id": c["id"]}, {"_id": 0}).to_list(5000)
        ti = build_team_info(teams)
        allm = await db.matches.find({"category_id": c["id"]}, {"_id": 0}).to_list(10000)
        targets = [m for m in allm if not m.get("locked") and m.get("home_id") and m.get("away_id") and m.get("status") != "bye"]
        for m in targets:
            m["date"] = None; m["time"] = None; m["ground_id"] = None
        locked = [m for m in allm if m.get("locked") and m.get("date")]
        items.append({"cat_id": c["id"], "constraints": constraints, "matches": targets,
                      "team_info": ti, "ground_ids": c.get("ground_ids"), "locked": locked})
        all_targets += targets
    if not all_targets:
        raise HTTPException(400, "Generate fixtures for at least one category before scheduling.")
    tour_dates = dates_in_range(start, end, set())
    scheduled, unsch, conflicts, suggestions = schedule_matches(items, grounds, tour_dates)
    for m in all_targets:
        await db.matches.update_one({"id": m["id"]}, {"$set": {
            "date": m.get("date"), "time": m.get("time"), "ground_id": m.get("ground_id")}})
    ref_assigned, ref_unassigned, ref_conflicts = await _assign_and_persist_referees(tid)
    return {"scheduled": len(scheduled), "unscheduled": len(unsch),
            "conflicts": conflicts + ref_conflicts, "suggestions": suggestions,
            "categories": len(items),
            "referees_assigned": ref_assigned, "referees_unassigned": ref_unassigned}


@api_router.post("/tournaments/{tid}/assign-referees")
async def assign_referees_ep(tid: str):
    """Re-run referee assignment over the current schedule without rescheduling anything."""
    await get_or_404(db.tournaments, tid, "Tournament")
    assigned, unassigned, conflicts = await _assign_and_persist_referees(tid)
    return {"assigned": assigned, "unassigned": unassigned, "conflicts": conflicts}


@api_router.get("/categories/{cid}/conflicts")
async def check_conflicts(cid: str):
    cat = await get_or_404(db.categories, cid, "Category")
    constraints = {**DEFAULT_CONSTRAINTS, **(cat.get("constraints") or {})}
    matches = await db.matches.find({"category_id": cid}, {"_id": 0}).to_list(10000)
    teams = await db.teams.find({"category_id": cid}, {"_id": 0}).to_list(5000)
    team_info = {t["id"]: {"available_from": t.get("available_from"), "available_to": t.get("available_to"), "no_back_to_back": t.get("no_back_to_back", False)} for t in teams}
    return {"conflicts": detect_conflicts(matches, constraints, team_info)}


@api_router.get("/tournaments/{tid}/conflicts")
async def tournament_conflicts(tid: str):
    cats = await db.categories.find({"tournament_id": tid}, {"_id": 0}).to_list(1000)
    items = []
    for c in cats:
        constraints = {**DEFAULT_CONSTRAINTS, **(c.get("constraints") or {})}
        teams = await db.teams.find({"category_id": c["id"]}, {"_id": 0}).to_list(5000)
        ms = await db.matches.find({"category_id": c["id"]}, {"_id": 0}).to_list(10000)
        items.append({"cat_id": c["id"], "constraints": constraints, "matches": ms, "team_info": build_team_info(teams)})
    return {"conflicts": detect_all_conflicts(items)}


# --------------------------- STANDINGS ---------------------------
@api_router.get("/categories/{cid}/standings")
async def standings(cid: str):
    cat = await get_or_404(db.categories, cid, "Category")
    teams = await db.teams.find({"category_id": cid}, {"_id": 0}).to_list(5000)
    matches = await db.matches.find({"category_id": cid}, {"_id": 0}).to_list(10000)
    points = {**DEFAULT_POINTS, **(cat.get("points_config") or {})}
    group_matches = [m for m in matches if m.get("group")]
    if group_matches:
        groups = sorted({m["group"] for m in group_matches})
        result = {}
        for g in groups:
            gmatches = [m for m in matches if m.get("group") == g]
            gteam_ids = set()
            for m in gmatches:
                gteam_ids.add(m.get("home_id")); gteam_ids.add(m.get("away_id"))
            gteams = [t for t in teams if t["id"] in gteam_ids]
            result[g] = compute_standings(gteams, gmatches, points)
        return {"grouped": True, "standings": result}
    league_matches = [m for m in matches if m.get("stage") != "knockout"]
    return {"grouped": False, "standings": compute_standings(teams, league_matches, points)}


# --------------------------- REPORTS ---------------------------
@api_router.get("/tournaments/{tid}/schedule")
async def full_schedule(tid: str):
    matches = await db.matches.find({"tournament_id": tid, "date": {"$ne": None}}, {"_id": 0}).to_list(20000)
    matches.sort(key=lambda m: (m.get("date") or "", m.get("time") or ""))
    return matches


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
