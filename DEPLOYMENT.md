# BantayAni Deployment Guide

## Architecture

| Service   | Port | Description                          |
|-----------|------|--------------------------------------|
| Frontend  | 3000 | Next.js 14 app                       |
| Backend   | 8000 | FastAPI API (`/api/*`)               |
| PostgreSQL| 5432 | Production database (or Supabase)    |

## Quick Start (Docker Compose)

```bash
# From project root
docker compose up --build
```

- App: http://localhost:3000
- API: http://localhost:8000/api
- API docs: http://localhost:8000/docs

Postgres is initialized with `database/schema.sql` and `database/seed.sql`.

### Demo mode without Postgres

Set `DATABASE_URL=demo` in the backend environment to use JSON files from `data/` instead of PostgreSQL.

## Environment Files

| File | Purpose |
|------|---------|
| `frontend/.env.production` | Build-time vars for `npm run build` |
| `frontend/.env.local` | Local dev overrides (not committed) |
| `backend/.env.production.example` | Template for production backend secrets |
| `backend/.env` | Active backend config (copy from `.env.example`) |

### Frontend variables

```env
NEXT_PUBLIC_API_URL=https://api.your-domain.com/api
NEXT_PUBLIC_GOOGLE_MAPS_KEY=   # optional
```

`NEXT_PUBLIC_*` vars are baked in at build time. Rebuild the frontend after changing them.

### Backend variables

See `backend/.env.production.example` for the full list. Required for production:

- `DATABASE_URL` — PostgreSQL connection string
- `JWT_SECRET_KEY` — random 32-byte hex string
- `CORS_ORIGINS` — comma-separated frontend URL(s)

Optional integrations:

- `GOOGLE_APPLICATION_CREDENTIALS` — Earth Engine NDVI tiles
- `SENTINEL_HUB_CLIENT_ID` + `SENTINEL_HUB_CLIENT_SECRET` — Sentinel View imagery
- `DEEPSEEK_API_KEY` — AI chat

### Parcel ID sequencing (production)

When using PostgreSQL, farm parcel IDs and RSBSA numbers must be allocated inside a transaction to avoid collisions under concurrent registration. Use `SELECT ... FOR UPDATE` on the municipality row (or a dedicated `municipality_sequences` table) before computing the next `NAGA-{NNN}` parcel ID and `RSBSA-NAG-{YEAR}-{NNNNN}` number. Demo mode uses atomic read-compute-write on `data/farms.json` with the same max-suffix logic.

## Manual Deployment

### Backend

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.production.example .env   # edit with real values
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm ci
cp .env.production .env.local     # edit NEXT_PUBLIC_API_URL
npm run build
npm start
```

## Supabase (Managed Postgres)

1. Create a Supabase project.
2. Run `database/schema.sql` then `database/seed.sql` in the SQL Editor.
3. Set `DATABASE_URL` to the Supabase pooler connection string (port 6543).
4. Add your frontend URL to `CORS_ORIGINS`.

## Health Check

```bash
curl http://localhost:8000/api/health
```

Expected: `{"success":true,"data":{"status":"healthy",...}}`

## Demo Credentials

| Field    | Value                |
|----------|----------------------|
| Email    | `mao.naga@da.gov.ph` |
| Password | `demo123`            |

## Security Configuration (Production)

### Authentication and rate limiting

- `JWT_SECRET_KEY` must be at least 32 characters of cryptographically random data. The backend logs a critical warning at startup if the key is shorter; in production mode this prevents startup.
- JWT access tokens currently expire after 24 hours. For production deployments, reduce this to 1 hour and implement refresh tokens or require re-authentication.
- Login brute-force protection is enabled: 5 failed attempts from the same IP within 5 minutes triggers a 15-minute lockout (HTTP 429). No credentials are logged on failed attempts — only the email and client IP.
- Login request validation enforces `email` max 255 characters and `password` max 128 characters (HTTP 422 if exceeded).
- Login responses never include `password_hash` or other sensitive fields — only `id`, `email`, `first_name`, `last_name`, `role`, and `municipality_id`.

### CORS

- Set `CORS_ORIGINS` to your exact frontend domain(s), comma-separated. Never use wildcard `*` in production.
- Example: `CORS_ORIGINS=https://bantayani.cloud,https://www.bantayani.cloud`

### Database

- All SQL queries use parameterized placeholders (`%s` with psycopg2). Do not concatenate user input into SQL strings.

### Earth Engine credentials

- Store the service account key outside the repository. Set `GOOGLE_APPLICATION_CREDENTIALS` to the key file path.
- `backend/credentials/*.json` is gitignored. If a key was ever committed, rotate it in Google Cloud Console immediately.

### Environment files

- Never commit `.env`, `.env.local`, or `.env.production` with real secrets.
- Use `backend/.env.production.example` and `frontend/.env.example` as templates only.

### Reverse proxy

- When behind nginx or a load balancer, configure trusted proxy IPs before honoring `X-Forwarded-For` for rate limiting.