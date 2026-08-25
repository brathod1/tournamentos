import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const http = axios.create({ baseURL: API });

// ---------------------------------------------------------------- auth token
const TOKEN_KEY = "tos_token";
export const getToken = () => {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
};
export const setToken = (t) => {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ }
};

// Attach the bearer token to every request when signed in.
http.interceptors.request.use((cfg) => {
  const t = getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

// A rejected/expired token signs the user out so the UI drops to read-only
// instead of repeatedly failing with a stale session.
let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };
http.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err.response?.status;
    const isLoginAttempt = (err.config?.url || "").includes("/auth/login");
    if (status === 401 && !isLoginAttempt && getToken()) { setToken(null); onUnauthorized(); }
    return Promise.reject(err);
  }
);

export const api = {
  // auth
  authStatus: () => http.get("/auth/status").then((r) => r.data),
  bootstrap: (d) => http.post("/auth/bootstrap", d).then((r) => r.data),
  login: (d) => http.post("/auth/login", d).then((r) => r.data),
  me: () => http.get("/auth/me").then((r) => r.data),
  changePassword: (d) => http.post("/auth/change-password", d).then((r) => r.data),
  listUsers: () => http.get("/auth/users").then((r) => r.data),
  createUser: (d) => http.post("/auth/users", d).then((r) => r.data),
  deleteUser: (id) => http.delete(`/auth/users/${id}`).then((r) => r.data),
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
  // replan=false keeps matches that already have a slot (locked or hand-placed) and
  // only fills the gaps; replan=true rebuilds the whole schedule from scratch.
  autoSchedule: (cid, replan = false) => http.post(`/categories/${cid}/auto-schedule?replan=${replan}`).then((r) => r.data),
  scheduleTournament: (tid, replan = false) => http.post(`/tournaments/${tid}/auto-schedule?replan=${replan}`).then((r) => r.data),
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
