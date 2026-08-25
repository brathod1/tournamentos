# Deploying TournamentOS

Three free services, connected by environment variables:

| Piece | Service | Free tier notes |
|---|---|---|
| Database | **MongoDB Atlas** | 512 MB — far more than a tournament needs |
| Backend (FastAPI) | **Render** | Sleeps after ~15 min idle; first request then takes ~50 s to wake |
| Frontend (React) | **Vercel** | Always fast, generous limits |

Total cost: nothing. If the backend's cold start bothers you on match day, Render's
$7/month Starter plan keeps it awake — worth it for a live event.

Do the steps in order; each one produces a value the next step needs.

---

## Before you start

Commit and push everything, since both hosts deploy from GitHub:

```powershell
cd "D:\Data Backup\project"
git add .
git commit -m "Add authentication and deployment config"
git push
```

---

## 1. Database — MongoDB Atlas

1. Sign up at <https://www.mongodb.com/cloud/atlas/register>.
2. Create a **free M0 cluster** (any provider/region; pick one near you).
3. **Database Access** → *Add New Database User*. Username e.g. `tournamentos`,
   and use the **Autogenerate Secure Password** button — copy the password somewhere safe now,
   it is not shown again.
4. **Network Access** → *Add IP Address* → **Allow Access from Anywhere** (`0.0.0.0/0`).
   Render's outbound IPs aren't fixed on the free plan, so this is required. Your database is
   still protected by the username and password.
5. **Database** → *Connect* → *Drivers* → copy the connection string. It looks like:

   ```
   mongodb+srv://tournamentos:<db_password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
   ```

   Replace `<db_password>` with the real password. Keep this string — it's `MONGO_URL` below.
   If the password contains `@ : / ? # [ ] %`, URL-encode those characters.

---

## 2. Backend — Render

1. Sign up at <https://render.com> with your GitHub account.
2. **New +** → **Web Service** → connect the `tournamentos` repository.
3. Settings:
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Free
4. **Environment Variables** — add these:

   | Key | Value |
   |---|---|
   | `MONGO_URL` | the Atlas string from step 1 |
   | `DB_NAME` | `tournamentos` |
   | `ENVIRONMENT` | `production` |
   | `JWT_SECRET` | a long random string (see below) |
   | `TOKEN_TTL_HOURS` | `12` |
   | `CORS_ORIGINS` | `*` for now — tighten in step 4 |

   Generate the secret locally and paste the output:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   `ENVIRONMENT=production` makes the app refuse to start without a real `JWT_SECRET`,
   so a misconfigured deploy fails loudly instead of running insecurely.
5. **Create Web Service** and wait for the first build (2–4 minutes).
6. Test it: open `https://<your-service>.onrender.com/api/` — you should see
   `{"message":"TournamentOS API","status":"ok"}`. Copy that base URL (without `/api/`).

---

## 3. Frontend — Vercel

1. Sign up at <https://vercel.com> with GitHub.
2. **Add New** → **Project** → import the `tournamentos` repository.
3. Settings:
   - **Root Directory:** `frontend`
   - Framework preset: *Create React App* (detected automatically)
4. **Environment Variables** — add one:

   | Key | Value |
   |---|---|
   | `REACT_APP_BACKEND_URL` | your Render URL, e.g. `https://tournamentos-api.onrender.com` |

   No trailing slash. This is read at **build** time, so if you change it later you must
   redeploy for it to take effect.
5. **Deploy**, then open the URL Vercel gives you.

---

## 4. Lock down CORS

Back in Render → your service → Environment, change `CORS_ORIGINS` from `*` to your exact
Vercel URL:

```
https://tournamentos.vercel.app
```

Comma-separate if you have more than one (e.g. a custom domain). Save — Render redeploys
automatically. This stops other websites from making authenticated calls to your API.

---

## 5. Create your admin account

Open your Vercel URL. Because the production database is empty, you'll get the
**first-time setup** screen. Enter your name, email and a strong password — that becomes the
admin account.

Then use **Account → Add Account** to create logins for the rest of your committee.
Give them the `organizer` role unless they also need to manage accounts.

> The local test account (`qa-harness@example.com`) exists only in your laptop's database.
> Never create it in production.

---

## Everyday use

- **Deploying changes:** `git push` — Vercel and Render both rebuild automatically.
- **Local development is unaffected:** your local `.env` files still point at localhost and
  your local MongoDB, so you can keep working without touching production.
- **Backend asleep?** The first request after idle takes ~50 s on the free plan. Open the
  site a minute before you need it, or upgrade to Starter.

## Checks worth doing once live

1. Sign out, open the public URL — you should see fixtures/standings but no edit controls.
2. Sign in — Categories, Teams, Grounds and Schedule tabs reappear.
3. Run a schedule; confirm referees get assigned.
4. Open the site on your phone to check the tournament-day experience.

## If something breaks

- **Vercel build fails on ESLint warnings** ("Treating warnings as errors because
  process.env.CI = true"): add a Vercel environment variable `CI` = `false` and redeploy.
  Better long-term is to fix the warnings the log names.

- **"Failed to fetch" / network errors in the browser:** `CORS_ORIGINS` doesn't match your
  Vercel URL exactly (scheme, no trailing slash), or `REACT_APP_BACKEND_URL` is wrong — the
  latter needs a Vercel redeploy after changing.
- **Backend won't start:** check Render logs. `JWT_SECRET must be set when
  ENVIRONMENT=production` means the variable is missing.
- **Database connection errors:** confirm Atlas Network Access allows `0.0.0.0/0` and that the
  password in `MONGO_URL` is correct and URL-encoded.

## Security posture, honestly

What you have: passwords hashed with bcrypt, signed 12-hour sessions, every write
authenticated, personal contact details hidden from the public, CORS restricted, secrets in
environment variables rather than the repo.

What you don't have: rate limiting on login (someone could try passwords in bulk — use strong
ones), no password reset flow (an admin re-creates the account), no audit log of who changed
what, and no automated backups (Atlas free tier has none — export anything you'd hate to lose).
None of these block a club tournament; all are worth revisiting if this grows.
