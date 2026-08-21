import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const http = axios.create({ baseURL: API });

export const api = {
  // tournaments
  listTournaments: () => http.get("/tournaments").then((r) => r.data),
  getTournament: (id) => http.get(`/tournaments/${id}`).then((r) => r.data),
  createTournament: (d) => http.post("/tournaments", d).then((r) => r.data),
  updateTournament: (id, d) => http.put(`/tournaments/${id}`, d).then((r) => r.data),
  deleteTournament: (id) => http.delete(`/tournaments/${id}`).then((r) => r.data),
  // categories
  listCategories: (tid) => http.get(`/tournaments/${tid}/categories`).then((r) => r.data),
  createCategory: (tid, d) => http.post(`/tournaments/${tid}/categories`, d).then((r) => r.data),
  getCategory: (id) => http.get(`/categories/${id}`).then((r) => r.data),
  updateCategory: (id, d) => http.put(`/categories/${id}`, d).then((r) => r.data),
  deleteCategory: (id) => http.delete(`/categories/${id}`).then((r) => r.data),
  // teams
  listTeams: (cid) => http.get(`/categories/${cid}/teams`).then((r) => r.data),
  createTeam: (cid, d) => http.post(`/categories/${cid}/teams`, d).then((r) => r.data),
  updateTeam: (id, d) => http.put(`/teams/${id}`, d).then((r) => r.data),
  deleteTeam: (id) => http.delete(`/teams/${id}`).then((r) => r.data),
  // grounds
  listGrounds: (tid) => http.get(`/tournaments/${tid}/grounds`).then((r) => r.data),
  createGround: (tid, d) => http.post(`/tournaments/${tid}/grounds`, d).then((r) => r.data),
  updateGround: (id, d) => http.put(`/grounds/${id}`, d).then((r) => r.data),
  deleteGround: (id) => http.delete(`/grounds/${id}`).then((r) => r.data),
  // referees
  listReferees: (tid) => http.get(`/tournaments/${tid}/referees`).then((r) => r.data),
  createReferee: (tid, d) => http.post(`/tournaments/${tid}/referees`, d).then((r) => r.data),
  updateReferee: (id, d) => http.put(`/referees/${id}`, d).then((r) => r.data),
  deleteReferee: (id) => http.delete(`/referees/${id}`).then((r) => r.data),
  // fixtures & matches
  generateFixtures: (cid) => http.post(`/categories/${cid}/generate-fixtures`).then((r) => r.data),
  seedKnockout: (cid) => http.post(`/categories/${cid}/seed-knockout`).then((r) => r.data),
  listMatches: (cid) => http.get(`/categories/${cid}/matches`).then((r) => r.data),
  updateMatch: (id, d) => http.put(`/matches/${id}`, d).then((r) => r.data),
  clearMatches: (cid) => http.delete(`/categories/${cid}/matches`).then((r) => r.data),
  // scheduling
  autoSchedule: (cid) => http.post(`/categories/${cid}/auto-schedule`).then((r) => r.data),
  scheduleTournament: (tid) => http.post(`/tournaments/${tid}/auto-schedule`).then((r) => r.data),
  assignReferees: (tid) => http.post(`/tournaments/${tid}/assign-referees`).then((r) => r.data),
  conflicts: (cid) => http.get(`/categories/${cid}/conflicts`).then((r) => r.data),
  tournamentConflicts: (tid) => http.get(`/tournaments/${tid}/conflicts`).then((r) => r.data),
  // standings
  standings: (cid) => http.get(`/categories/${cid}/standings`).then((r) => r.data),
  schedule: (tid) => http.get(`/tournaments/${tid}/schedule`).then((r) => r.data),
};

export const FORMATS = [
  { value: "league_single", label: "League — Single Round Robin" },
  { value: "league_double", label: "Double League — Home & Away" },
  { value: "knockout", label: "Knockout — Single Elimination" },
  { value: "groups_knockout", label: "Groups + Knockout" },
];

export const TIEBREAKERS = [
  { value: "points", label: "Points" },
  { value: "goal_difference", label: "Goal Difference" },
  { value: "goals_for", label: "Goals For" },
  { value: "head_to_head", label: "Head to Head" },
  { value: "wins", label: "Number of Wins" },
];
