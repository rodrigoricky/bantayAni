# Bantay Ani

Satellite crop monitoring and insurance claims verification platform for Philippine Municipal Agricultural Officers (MAOs).

**Demo case study:** Typhoon Kristine (October 22–24, 2024, Camarines Sur) — flood damage to rice farms verified via Sentinel-2 NDVI analysis.

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- (Optional) Supabase PostgreSQL for production database

### Quick start (both servers)

```bash
./start.sh
```

Then open **http://localhost:3000** and log in.

### Manual start

**Backend** (port 8000):
```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DATABASE_URL=demo works out of the box
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend** (port 3000):
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

App: http://localhost:3000 | API docs: http://localhost:8000/docs

### Demo Credentials

| Field    | Value                  |
|----------|------------------------|
| Email    | `mao.naga@da.gov.ph`   |
| Password | `demo123`              |

### Demo Claim Verification

| Field        | Value                        |
|--------------|------------------------------|
| RSBSA        | `RSBSA-05-NAGA-2024-00123`   |
| Disaster Date| `2024-10-23`                 |
| Damage Type  | Flood                        |
| Claimed Area | `2.5` hectares               |

Expected result: NDVI 0.682 → 0.094, ~86% damage, **APPROVED**

## Database Setup (Supabase)

1. Create a Supabase project
2. Run `database/schema.sql` in the SQL Editor
3. Run `database/seed.sql`
4. Update `backend/.env`:
   ```
   DATABASE_URL=postgresql://postgres.xxxxx:password@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```

## Project Structure

```
bantayAni/
├── backend/     FastAPI API (port 8000)
├── frontend/    Next.js 14 app (port 3000)
├── database/    PostgreSQL schema + seed
├── data/        Demo farm/satellite JSON
├── scripts/     Data prep utilities
└── docs/        API and demo documentation
```

## Demo Mode

Set `DATABASE_URL=demo` in `backend/.env` to run without Supabase. All demo data is loaded from `data/farms.json`.

## License

Demo / MVP — Philippine Department of Agriculture use case.