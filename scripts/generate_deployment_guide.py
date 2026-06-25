#!/usr/bin/env python3
"""Generate guide.md — Bantay Ani Production Deployment Guide."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "guide.md"

def main():
    farms = json.loads((ROOT / "data/farms.json").read_text())
    lines = []
    w = lines.append

    w("# Bantay Ani — Production Deployment Guide")
    w("")
    w("**Document purpose:** Complete codebase comprehension reference and step-by-step production deployment playbook for AWS + Supabase.")
    w("")
    w("**Last updated:** June 26, 2026")
    w("")
    w("---")
    w("")
    w("## Table of Contents")
    w("")
    toc = [
        ("1", "System Architecture Overview", [
            "1.1 What Bantay Ani Is", "1.2 Architecture Diagram", "1.3 The Two Operating Modes",
            "1.4 User Roles and Access Boundaries", "1.5 Data Flow for Each Core Workflow",
            "1.6 Current Limitations and Technical Debt",
        ]),
        ("2", "Complete Codebase Reference", [
            "2.1 Backend Module Map", "2.2 Frontend Module Map", "2.3 Environment Variables — Complete Reference",
            "2.4 API Endpoint Reference", "2.5 Database Schema Reference", "2.6 The Demo Data Reference",
        ]),
        ("3", "Pre-Deployment Assessment", [
            "3.1 Security Gaps", "3.2 Infrastructure Gaps", "3.3 Application Gaps",
            "3.4 What Can Be Deployed As-Is", "3.5 What Must Be Changed Before Going Live",
        ]),
        ("4", "Domain Setup", ["4.1 DNS Configuration", "4.2 SSL/TLS"]),
        ("5", "Supabase Setup (Database)", [
            "5.1 Create the Supabase Project", "5.2 Get the Connection String", "5.3 Run the Schema",
            "5.4 Run the Seed Data", "5.5 Supabase Row Level Security", "5.6 Supabase Environment Variable",
            "5.7 Connection Pooling Considerations",
        ]),
        ("6", "AWS Services Setup", [
            "6.1 AWS Account and IAM Setup", "6.2 Decision: Which AWS Services to Use",
            "6.3 Frontend: AWS Amplify Hosting", "6.4 Backend: AWS Elastic Beanstalk",
            "6.5 Google Earth Engine Service Account", "6.6 AWS S3 for Static Assets (Optional)",
            "6.7 CloudFront (Optional but Recommended)",
        ]),
        ("7", "Step-by-Step Deployment Sequence", []),
        ("8", "Environment Variable Production Values", []),
        ("9", "What the Team Needs to Do Right Now vs Later", [
            "9.1 Minimum to Go Live", "9.2 Should Be Done Within One Week", "9.3 Can Be Done Over Time",
        ]),
        ("10", "Troubleshooting Reference", []),
        ("11", "Cost Estimate", []),
        ("12", "Security Checklist Before Going Live", []),
    ]
    for num, title, subs in toc:
        anchor = title.lower().replace(" ", "-").replace("—", "").replace("(", "").replace(")", "")
        w(f"- [{num}. {title}](#{num}-{anchor})")
        for sub in subs:
            sa = sub.lower().replace(" ", "-").replace("—", "").replace(".", "")
            w(f"  - [{sub}](#{sa})")
    w("")
    w("---")
    w("")

    # Section 1
    w("## 1. System Architecture Overview")
    w("")
    w("### 1.1 What Bantay Ani Is")
    w("")
    w("Bantay Ani is a satellite crop monitoring and crop insurance claims verification platform for the Philippine Department of Agriculture ecosystem. It serves three primary user types:")
    w("")
    w("| Role | Organization | Primary use |")
    w("|------|--------------|-------------|")
    w("| **MAO** | Municipal Agricultural Officer | Monitors farm health in their municipality, runs NDVI scans, files and verifies insurance claims |")
    w("| **DA Regional** | Department of Agriculture Regional Office | Views regional crop health, damage summaries, and advisories across municipalities |")
    w("| **PCIC** | Philippine Crop Insurance Corporation | Reviews submitted claims, approves/rejects/flags, views analytics and estimated payouts |")
    w("")
    w("The system has two core modules:")
    w("")
    w("- **TANAW** (crop health monitoring): Dashboard map with NDVI-colored farm polygons, satellite date selector, municipality farm lists, regional health overview, NDVI scan jobs.")
    w("- **BAWI** (claim verification): Satellite-based before/after NDVI comparison, fraud detection, AI assessment, PDF reports with QR verification, PCIC claim workflow.")
    w("")
    w("The demo case study is **Typhoon Kristine** (October 22–24, 2024) flood damage to rice farms in **Naga City, Camarines Sur**.")
    w("")
    w("### 1.2 Architecture Diagram (Text-Based)")
    w("")
    w("```mermaid")
    w("flowchart TB")
    w("    subgraph clients [Clients - Stateless]")
    w("        Browser[Next.js 14 Frontend<br/>Port 3000]")
    w("    end")
    w("    subgraph aws [AWS Production]")
    w("        Amplify[AWS Amplify<br/>Static/SSR Frontend]")
    w("        EB[Elastic Beanstalk<br/>FastAPI Docker :8000]")
    w("    end")
    w("    subgraph stateful [Stateful / External]")
    w("        Supabase[(Supabase PostgreSQL)]")
    w("        EE[Google Earth Engine]")
    w("        SH[Sentinel Hub API]")
    w("        DS[DeepSeek API]")
    w("    end")
    w("    Browser -->|HTTPS JWT Bearer| Amplify")
    w("    Amplify -->|NEXT_PUBLIC_API_URL| EB")
    w("    EB -->|DATABASE_URL direct| Supabase")
    w("    EB -->|GOOGLE_APPLICATION_CREDENTIALS| EE")
    w("    EB -->|SENTINEL_HUB_*| SH")
    w("    EB -->|DEEPSEEK_API_KEY| DS")
    w("    Browser -->|Public /verify/BA-*| EB")
    w("```")
    w("")
    w("**Stateless components:** Next.js frontend (after build), FastAPI workers (JWT in request, in-memory job cache only).")
    w("")
    w("**Stateful components:** Supabase PostgreSQL (users, farms, claims, notifications, satellite_imagery), Earth Engine tile cache in `app.state.satellite_cache`, in-memory `_scan_jobs` and `_claim_verify_jobs` on backend.")
    w("")
    w("### 1.3 The Two Operating Modes")
    w("")
    w("The entire backend switches between **demo mode** and **production mode** based on a single environment variable.")
    w("")
    w("**Trigger:** `DATABASE_URL` set to `demo`, empty string, or `none` (default in `backend/.env.example` is `demo`).")
    w("")
    w("```python")
    w("# backend/utils/database.py")
    w("DATABASE_URL = os.getenv('DATABASE_URL', 'demo')")
    w("DEMO_MODE = DATABASE_URL in ('', 'demo', 'none')")
    w("```")
    w("")
    w("| Aspect | Demo Mode | Production Mode |")
    w("|--------|-----------|-----------------|")
    w("| Database | `data/farms.json`, `data/demo_claims.json`, `data/notifications.json` via `_execute_demo_query()` | PostgreSQL via psycopg2 |")
    w("| NDVI scan jobs | `_run_scan_job_demo()` — synthetic NDVI, writes to farms.json | `compute_ndvi_for_location()` via Earth Engine |")
    w("| Claim verify async | `_run_claim_verify_job_demo()` with staged progress | Full `verify_claim_with_satellite()` |")
    w("| Available satellite dates | Hardcoded `DEMO_AVAILABLE_DATES` in `api/satellite.py` | Earth Engine or Sentinel Hub catalog |")
    w("| Satellite imagery API | Static previews from `frontend/public/satellite-previews/` | Live EE/SH with static fallback |")
    w("| Health check | `mode: demo` | `mode: production` |")
    w("| Startup | `ensure_farms_data_integrity()` on farms.json | Earth Engine init from credentials |")
    w("")
    w("**All `is_demo_mode()` check locations:**")
    w("")
    w("- `backend/utils/database.py` — core switch")
    w("- `backend/main.py` — lifespan integrity check, health endpoint")
    w("- `backend/api/satellite.py` — available-dates, sentinel-dates")
    w("- `backend/services/satellite_service.py` — scan jobs, save NDVI records, is_date_scanned")
    w("- `backend/services/claim_service.py` — claims CRUD, verify jobs, notifications")
    w("- `backend/services/farm_service.py` — farm listing, add farm")
    w("- `backend/services/notification_service.py` — all notification paths")
    w("- `backend/services/chat_service.py` — NDVI history, claims for intents")
    w("- `backend/services/role_service.py` — regional municipalities fallback")
    w("- `backend/utils/polygon_placement.py` — existing farm lookup")
    w("")
    w("Additional check: `os.environ.get('DATABASE_URL', 'demo') == 'demo'` in `satellite.py` and `satellite_service._run_scan_job()`.")
    w("")
    w("### 1.4 User Roles and Access Boundaries")
    w("")
    w("| Role | Dashboard | Farms | Claims | Regional | PCIC | Mechanism |")
    w("|------|-----------|-------|--------|----------|------|-----------|")
    w("| MAO | Yes (redirect from /dashboard) | Own municipality only | Own municipality | No | No | `check_municipality_access()` |")
    w("| DA_REGIONAL | Redirects to /regional/overview | All municipalities in region | Regional summary | Yes | No | `_require_regional()` on regional endpoints |")
    w("| PCIC | Redirects to /pcic/claims-queue | Read via claims | All claims | Analytics only | Yes | `_require_pcic()` |")
    w("| ADMIN | Same as MAO in frontend | Code checks ADMIN like DA_REGIONAL for regional health | Not in DB schema | Yes in code | No | **Not seeded; schema CHECK excludes ADMIN** |")
    w("")
    w("**RBAC mechanism:** JWT Bearer token → `get_current_user()` decodes `user_id`, `email`, `role`, `municipality_id` → per-route checks:")
    w("")
    w("- `check_municipality_access(user, municipality_id)` — MAO must match municipality; DA_REGIONAL, PCIC, ADMIN bypass")
    w("- `_require_pcic(user)` — claims approve/reject/flag/reverse, analytics, payouts")
    w("- `_require_regional(user)` — `/api/farms/regional/health`, `/api/claims/regional/summary`")
    w("")
    w("### 1.5 Data Flow for Each Core Workflow")
    w("")
    w("#### MAO login and dashboard")
    w("1. `POST /api/login` → `authenticate_user()` → bcrypt verify → `create_access_token()` → frontend `saveToken()` + `saveUser()` to **localStorage**")
    w("2. Redirect to `/dashboard` (MAO role)")
    w("3. `GET /api/farms/municipality/{id}?satellite_date=...` → farm list with NDVI status for selected date")
    w("4. `GET /api/satellite/ndvi-tiles` → map overlay tile URL")
    w("5. Background: `start_background_ndvi_refresh()` may update NDVI via Earth Engine thread")
    w("")
    w("#### MAO NDVI scan")
    w("1. Dashboard or Sentinel panel → `POST /api/satellite/scan-ndvi` with `municipality_id` + `satellite_date`")
    w("2. `start_ndvi_scan_job()` creates in-memory job, starts daemon thread")
    w("3. Demo: `_run_scan_job_demo()` writes to farms.json; Production: `compute_ndvi_for_location()` per farm → `satellite_imagery` table")
    w("4. Frontend polls `GET /api/satellite/scan-status/{job_id}` until `completed`")
    w("")
    w("#### MAO filing claim via Claims page")
    w("1. `ClaimForm` → `POST /api/claims/verify` with RSBSA, disaster_date, damage_type, claimed_area")
    w("2. `verify_claim_with_satellite()` → Earth Engine `compute_multi_index()` before/after windows → fraud rules → AI assessment → INSERT claims")
    w("3. `VerificationResult` displays status, NDVI comparison, images")
    w("4. Optional: `POST /api/claims/{id}/submit` → notifies PCIC")
    w("")
    w("#### Chatbot-initiated claim")
    w("1. `POST /api/chat` → `classify_intent` → `file_claim` → confirmation card")
    w("2. User confirms → `POST /api/claims/verify-async` → background job")
    w("3. Poll `scan-status` endpoint (shared job store) → redirect to claims with prefilled data")
    w("")
    w("#### PCIC approving a claim")
    w("1. PCIC login → `/pcic/claims-queue`")
    w("2. `GET /api/claims` (all municipalities)")
    w("3. `POST /api/claims/{id}/approve` → `_require_pcic` → UPDATE status → `notify_mao_claim_status_change()`")
    w("")
    w("#### PDF report and QR verification")
    w("1. `POST /api/reports/generate` with `claim_id` → ReportLab PDF")
    w("2. QR encodes `{VERIFY_BASE_URL}/verify/BA-{claim_number}`")
    w("3. Public `GET /api/verify/{report_id}` — no auth, masks farmer name, returns `report_integrity` SHA256 hash")
    w("4. Frontend `/verify/[id]` page fetches API and renders verification UI")
    w("")
    w("### 1.6 Current Limitations and Technical Debt")
    w("")
    w("| Item | Risk | Production fix | Difficulty |")
    w("|------|------|----------------|------------|")
    w("| JWT in localStorage | XSS can steal tokens | httpOnly Secure SameSite cookies + CSRF token | Moderate |")
    w("| No refresh tokens | 24h sessions; re-login on expiry | Refresh token rotation | Moderate |")
    w("| VERIFY_SECRET default fallback | Anyone can forge integrity hashes | Require env var, remove `DEFAULT_VERIFY_SECRET` | Easy |")
    w("| In-memory background jobs | Lost on restart; no multi-instance | Redis/DB job queue (Celery, ARQ) | Complex |")
    w("| No migration runner | Schema changes manual | Alembic or similar | Moderate |")
    w("| No automated tests | Regressions undetected | pytest + Playwright | Moderate |")
    w("| No CI/CD | Manual deploy errors | GitHub Actions → Amplify + EB | Moderate |")
    w("| nested `frontend/.git` | Amplify cannot deploy monorepo correctly | Remove nested git; single root repo | Easy |")
    w("| openai package unused | Dependency bloat | Remove from requirements.txt | Easy |")
    w("| 120s API timeout in api.js | Masks slow failures; ties up connections | Per-endpoint timeouts; job polling | Easy |")
    w("| Synchronous FastAPI endpoints | Blocks worker under load | `async def` + async DB driver | Complex |")
    w("| Demo query handler fragility | New SQL patterns return None in demo | Integration tests for demo handler | Moderate |")
    w("")
    w("---")
    w("")

    # Section 2 - abbreviated tables; full content continues...
    w("## 2. Complete Codebase Reference")
    w("")
    w("### 2.1 Backend Module Map")
    w("")
    w("| File | Purpose | Key imports | Exports / routes | If removed |")
    w("|------|---------|-------------|------------------|------------|")
    backend_map = [
        ("main.py", "FastAPI app, CORS, lifespan, router mount, /api/health", "api.*, earth_engine, middleware", "app", "Entire API down"),
        ("api/auth.py", "POST /login, rate limiting", "auth_service, role_service", "router", "No authentication"),
        ("api/farms.py", "Farm CRUD, regional health, NDVI status", "farm_service, auth_service", "router", "No farm data"),
        ("api/claims.py", "Claim verify, list, PCIC actions", "claim_service", "router", "No claims module"),
        ("api/satellite.py", "Imagery, NDVI tiles, scan jobs", "satellite_service, sentinel_hub", "router", "No satellite features"),
        ("api/reports.py", "PDF generation", "claim_service, reportlab", "router", "No PDF reports"),
        ("api/verify.py", "Public verification", "claim_service", "router", "QR verification broken"),
        ("api/chat.py", "Chatbot endpoint", "chat_service", "router", "No AI chat"),
        ("api/notifications.py", "Notification list/read", "notification_service", "router", "No notifications"),
        ("services/auth_service.py", "JWT, bcrypt, rate limit, RBAC deps", "jose, passlib, database", "get_current_user, create_access_token", "All protected routes fail"),
        ("services/farm_service.py", "Farm queries, NDVI refresh, regional health", "database, satellite_service, ndvi", "get_farms_by_municipality, etc.", "Dashboard empty"),
        ("services/claim_service.py", "Claim verification, PCIC workflow, jobs", "satellite, ai, database", "verify_claim_with_satellite, etc.", "BAWI module broken"),
        ("services/satellite_service.py", "Earth Engine NDVI, scan jobs, tiles", "earth_engine, database", "start_ndvi_scan_job, compute_multi_index", "No live NDVI"),
        ("services/sentinel_hub_service.py", "SH OAuth2, imagery, black image detect", "httpx, PIL", "get_sentinel_image_png, compute_ndvi_for_polygon", "Sentinel View panel degraded"),
        ("services/chat_service.py", "Intent classification, DeepSeek", "ai_service, database", "process_chat", "Chatbot broken"),
        ("services/ai_service.py", "DeepSeek API calls", "httpx", "call_deepseek, generate_claim_assessment", "AI text → templates only"),
        ("services/ai_templates.py", "Fallback AI text", "—", "select_ai_recommendation", "Generic recommendations only"),
        ("services/notification_service.py", "In-app notifications", "database", "create_notification, etc.", "No alerts"),
        ("services/role_service.py", "Role-specific data for login", "database", "get_role_data", "Login missing municipalities list"),
        ("services/earth_engine.py", "EE initialization", "earthengine-api", "initialize_earth_engine, is_ee_available", "Live satellite disabled"),
        ("utils/database.py", "PostgreSQL + demo JSON handler", "psycopg2", "execute_query, is_demo_mode", "Total data layer failure"),
        ("utils/ndvi.py", "NDVI thresholds", "—", "classify_health_status", "Wrong health colors"),
        ("utils/polygon_placement.py", "Farm polygon generation", "database", "generate_field_polygon", "Add farm broken"),
        ("utils/edge_detection.py", "Edge detection utility", "—", "edge helpers", "Unused in main flows"),
        ("models/auth.py", "Login Pydantic models", "pydantic", "LoginRequest", "Validation errors"),
        ("models/claim.py", "Claim request models", "pydantic", "ClaimVerificationRequest", "Claim API validation broken"),
        ("models/farm.py", "Farm request models", "pydantic", "AddFarmRequest", "Add farm broken"),
        ("middleware/error_handler.py", "Unified error responses", "fastapi", "exception handlers", "Raw stack traces"),
    ]
    for row in backend_map:
        w(f"| `{row[0]}` | {row[1]} | {row[2]} | {row[3]} | {row[4]} |")
    w("")

    # 2.2 Frontend Module Map
    w("### 2.2 Frontend Module Map")
    w("")
    frontend_pages = [
        ("app/page.js", "Root redirect to login or dashboard", "auth check", "All", "—"),
        ("app/login/page.js", "Login form + demo credentials panel", "POST /login", "Public", "email, password, loading"),
        ("app/verify/[id]/page.js", "Public QR verification page", "GET /verify/{id}", "Public", "verification state"),
        ("app/(authenticated)/dashboard/page.js", "MAO map dashboard, NDVI scan", "farms/municipality, ndvi-tiles, scan-ndvi", "MAO, ADMIN", "farms, stats, map, scan job"),
        ("app/(authenticated)/farms/page.js", "Farm list", "GET farms/municipality", "MAO", "farms list"),
        ("app/(authenticated)/farms/[id]/page.js", "Farm detail", "GET farms/{id}", "MAO", "farm, NDVI history"),
        ("app/(authenticated)/claims/page.js", "Claim filing", "GET/POST claims", "MAO", "claims, form"),
        ("app/(authenticated)/reports/page.js", "Report list + PDF download", "GET claims, POST reports/generate", "MAO", "claims, PDF"),
        ("app/(authenticated)/cases/page.js", "Case list", "GET claims", "PCIC", "claims"),
        ("app/(authenticated)/case/[id]/page.js", "PCIC case detail + actions", "GET claims/{id}, approve/reject/flag", "PCIC", "claim, actions"),
        ("app/(authenticated)/pcic/claims-queue/page.js", "PCIC queue", "GET claims, PCIC actions", "PCIC", "claims, filters"),
        ("app/(authenticated)/pcic/analytics/page.js", "PCIC analytics", "GET claims/pcic/analytics", "PCIC", "analytics"),
        ("app/(authenticated)/pcic/payouts/page.js", "Estimated payouts", "GET claims/pcic/payouts", "PCIC", "payouts"),
        ("app/(authenticated)/pcic/map/page.js", "Claims map", "GET claims, farms", "PCIC", "map markers"),
        ("app/(authenticated)/regional/overview/page.js", "Regional overview", "GET farms/regional/health", "DA_REGIONAL", "municipalities"),
        ("app/(authenticated)/regional/health/page.js", "Regional health table", "GET farms/regional/health", "DA_REGIONAL", "health data"),
        ("app/(authenticated)/regional/damage-reports/page.js", "Damage summary", "GET claims/regional/summary", "DA_REGIONAL", "summary"),
        ("app/(authenticated)/regional/advisories/page.js", "Client-side advisories", "GET farms/regional/health", "DA_REGIONAL", "advisories"),
        ("app/(authenticated)/search/page.js", "Global search", "GET farms, claims", "All authenticated", "results"),
        ("app/(authenticated)/settings/page.js", "Satellite date settings", "SatelliteDateContext", "All", "date prefs"),
    ]
    w("| Page | Renders | API calls | Roles | State |")
    w("|------|---------|-----------|-------|-------|")
    for p in frontend_pages:
        w(f"| `{p[0]}` | {p[1]} | {p[2]} | {p[3]} | {p[4]} |")
    w("")
    components = [
        ("ChatWidget.js", "Floating chatbot", "POST /chat, scan-status", "MAO+", "messages, job polling"),
        ("ChatMarkdown.js", "Renders AI markdown", "—", "All", "parsed blocks — no HTML sanitization"),
        ("ClaimForm.js", "Claim verification form", "POST /claims/verify", "MAO", "form, result"),
        ("VerificationResult.js", "Post-verify UI", "POST submit", "MAO", "result, images"),
        ("MapView.js / GoogleMapView.js", "Leaflet/Google map", "ndvi-tiles", "MAO", "farms, selection"),
        ("SentinelImagePanel.js", "Satellite panel + scan", "sentinel-image, scan-ndvi", "MAO", "imagery, job"),
        ("Header.js", "Top bar + notifications", "GET notifications", "All", "notifications"),
        ("Sidebar.js", "Role-based nav", "—", "All", "nav items"),
        ("AddFarmerModal.js", "Add/edit farm", "POST/PUT farms", "MAO", "form"),
    ]
    w("| Component | Renders | API calls | Roles | State |")
    w("|-----------|---------|-----------|-------|-------|")
    for c in components:
        w(f"| `{c[0]}` | {c[1]} | {c[2]} | {c[3]} | {c[4]} |")
    w("")

    # 2.3 Environment Variables
    w("### 2.3 Environment Variables — Complete Reference")
    w("")
    env_vars = [
        ("DATABASE_URL", "backend", "PostgreSQL URL or demo trigger", "demo", "postgresql://postgres:PASS@db.REF.supabase.co:5432/postgres", "Demo JSON if demo/empty; connection errors if wrong URL", "Secret"),
        ("JWT_SECRET_KEY", "backend", "JWT signing key", "generate-with-python-secrets", "64-char hex from openssl rand -hex 32", "Startup refusal if default; 401 if mismatch", "Secret"),
        ("JWT_ALGORITHM", "backend", "JWT algorithm", "HS256", "HS256", "Token decode fails if changed", "Safe"),
        ("JWT_EXPIRATION_HOURS", "backend", "Token TTL hours", "24", "24 (reduce to 1 for prod hardening)", "Session length", "Safe"),
        ("CORS_ORIGINS", "backend", "Allowed frontend origins", "http://localhost:3000", "https://bantayani.cloud", "CORS errors if mismatch", "Safe"),
        ("DEEPSEEK_API_KEY", "backend", "DeepSeek chat/assessment", "empty", "From platform.deepseek.com", "Template fallback if empty", "Secret"),
        ("OPENROUTER_API_KEY", "backend", "Unused fallback key in .env.example", "empty", "Optional", "Not used in code paths", "Secret"),
        ("DEEPSEEK_MODEL", "backend", "Model name in ai_service", "deepseek-chat", "deepseek-chat", "Wrong model if invalid", "Safe"),
        ("SENTINEL_HUB_CLIENT_ID", "backend", "Sentinel Hub OAuth", "empty", "From sentinel-hub.com", "Static preview fallback", "Secret"),
        ("SENTINEL_HUB_CLIENT_SECRET", "backend", "Sentinel Hub OAuth", "empty", "From sentinel-hub.com", "Static preview fallback", "Secret"),
        ("GOOGLE_APPLICATION_CREDENTIALS", "backend", "EE service account JSON path", "./credentials/earth-engine-key.json", "/app/credentials/ee-key.json on server", "Demo/static satellite if missing", "Secret path"),
        ("GOOGLE_EE_PROJECT", "backend", "EE project ID override", "empty", "From service account project_id", "EE init may fail", "Safe"),
        ("VERIFY_BASE_URL", "backend", "QR link base in PDFs", "http://localhost:3000", "https://bantayani.cloud", "Wrong domain in QR codes", "Safe"),
        ("VERIFY_SECRET", "backend", "Report integrity hash salt", "hardcoded default in verify.py", "openssl rand -hex 32", "Predictable integrity if default", "Secret"),
        ("NEXT_PUBLIC_API_URL", "frontend", "API base URL", "http://localhost:8000/api", "https://api.bantayani.cloud/api", "All API calls fail if wrong", "Safe (public)"),
        ("NEXT_PUBLIC_GOOGLE_MAPS_KEY", "frontend", "Google Maps (optional)", "empty", "Google Cloud Console", "Map features limited", "Safe (public)"),
    ]
    w("| Variable | Read by | Controls | Local dev | Production | If wrong | Secret? |")
    w("|----------|---------|----------|-----------|------------|----------|---------|")
    for v in env_vars:
        w(f"| `{v[0]}` | {v[1]} | {v[2]} | {v[3]} | {v[4]} | {v[5]} | {v[6]} |")
    w("")

    # 2.4 API Endpoints
    w("### 2.4 API Endpoint Reference")
    w("")
    endpoints = [
        ("GET", "/api/health", "No", "—", "—", "{status, mode}", "main.py", "Shows demo/production", "Same"),
        ("POST", "/api/login", "No", "{email, password}", "{access_token, user, expires_in}", "auth_service", "Rate limited 5/15min", "Demo users from JSON/DB"),
        ("GET", "/api/farms/regional/health", "Yes", "DA_REGIONAL, ADMIN", "—", "municipalities + stats", "get_regional_health", "Regional aggregation", "PostgreSQL farms"),
        ("GET", "/api/farms/next-rsbsa", "Yes", "MAO+", "municipality_id query", "{rsbsa_number}", "get_next_rsbsa_number", "Sequential RSBSA", "Same logic"),
        ("POST", "/api/farms/add", "Yes", "MAO", "AddFarmRequest", "{parcel_id, rsbsa_number}", "add_farm_parcel", "Writes farms.json or DB", "PostgreSQL INSERT"),
        ("GET", "/api/farms/municipality/{id}", "Yes", "MAO+ (scoped)", "satellite_date, filters", "farms, stats, municipality", "get_farms_by_municipality", "Demo JSON LATERAL emulation", "SQL LATERAL join"),
        ("GET", "/api/farms/municipality/{id}/ndvi-status", "Yes", "MAO+", "—", "refresh status", "get_municipality_ndvi_status", "In-memory status", "Same"),
        ("GET", "/api/farms/by-rsbsa/{rsbsa}", "Yes", "MAO scoped", "—", "farm object", "execute_query", "Demo farm lookup", "DB lookup"),
        ("GET", "/api/farms/{parcel_id}", "Yes", "MAO scoped", "—", "farm + history + claims", "get_farm_detail", "Demo queries", "SQL joins"),
        ("PUT", "/api/farms/{parcel_id}", "Yes", "MAO", "AddFarmRequest", "updated farm", "update_farm_parcel", "Updates JSON or DB", "SQL UPDATE"),
        ("POST", "/api/claims/verify", "Yes", "MAO", "ClaimVerificationRequest", "verification result", "verify_claim_with_satellite", "Demo uses EE if configured", "Full EE multi-index"),
        ("POST", "/api/claims/verify-async", "Yes", "MAO", "ClaimVerificationRequest", "{job_id, status}", "verify_claim_async", "Demo staged job", "Thread job"),
        ("GET", "/api/claims", "Yes", "All auth", "filters, pagination", "claims list", "get_claims_list", "demo_claims.json", "SQL paginated"),
        ("GET", "/api/claims/{id}", "Yes", "All auth", "—", "claim detail", "get_claim_detail", "Demo claims", "SQL join"),
        ("POST", "/api/claims/{id}/submit", "Yes", "MAO", "—", "submitted claim", "submit_claim_to_pcic", "Updates demo/DB", "Same"),
        ("POST", "/api/claims/{id}/approve", "Yes", "PCIC", "—", "claim", "approve_claim", "Demo update", "SQL UPDATE"),
        ("POST", "/api/claims/{id}/reject", "Yes", "PCIC", "{reason}", "claim", "reject_claim", "Demo update", "SQL UPDATE"),
        ("POST", "/api/claims/{id}/flag", "Yes", "PCIC", "{reason}", "claim", "flag_claim", "Demo update", "SQL UPDATE"),
        ("POST", "/api/claims/{id}/reverse", "Yes", "PCIC", "—", "claim", "reverse_claim_decision", "Demo update", "SQL UPDATE"),
        ("GET", "/api/claims/regional/summary", "Yes", "DA_REGIONAL", "—", "damage summary", "get_regional_damage_summary", "From demo claims", "SQL aggregation"),
        ("GET", "/api/claims/pcic/analytics", "Yes", "PCIC", "—", "analytics", "get_pcic_analytics", "Demo claims", "SQL aggregation"),
        ("GET", "/api/claims/pcic/payouts", "Yes", "PCIC", "—", "payouts", "get_pcic_payouts", "Estimated amounts", "Same"),
        ("GET", "/api/satellite/available-dates", "Yes", "All", "lat, lng, dates", "available_dates", "get_available_sentinel_dates or demo list", "DEMO_AVAILABLE_DATES", "Earth Engine catalog"),
        ("GET", "/api/satellite/imagery", "Yes", "All", "lat, lng, date", "tile_url, bounds", "get_sentinel_imagery", "EE tiles", "EE tiles"),
        ("GET", "/api/satellite/ndvi-tiles", "Yes", "All", "lat, lng, date", "tile_url, expires_at", "get_ndvi_tiles_for_date", "Cached/demo", "EE/SH"),
        ("GET", "/api/satellite/sentinel-dates", "Yes", "All", "lat, lng, dates", "available_dates", "sentinel_hub or demo", "Demo dates", "SH catalog"),
        ("POST", "/api/satellite/scan-ndvi", "Yes", "MAO", "{municipality_id, satellite_date}", "202 job", "start_ndvi_scan_job", "Fast demo scan", "EE per farm"),
        ("GET", "/api/satellite/scan-status/{job_id}", "Yes", "All", "—", "job status", "get_ndvi_scan_status", "In-memory", "In-memory"),
        ("POST", "/api/satellite/compute-ndvi", "Yes", "All", "{parcel_id, date}", "ndvi", "compute_ndvi_for_polygon", "DB seeded values", "SH/DB"),
        ("GET", "/api/satellite/sar-tiles", "Yes", "All", "lat, dates", "flood tiles", "get_sentinel1_flood_tile_url", "EE SAR", "EE SAR"),
        ("GET", "/api/satellite/sentinel-image", "Yes", "All", "lat, lng, date, type", "PNG stream", "get_sentinel_image_png", "Static previews", "SH/EE/static"),
        ("POST", "/api/reports/generate", "Yes", "MAO+", "{claim_id}", "PDF stream", "generate_pcic_report", "Same", "Same"),
        ("GET", "/api/verify/{report_id}", "No", "—", "—", "verification payload", "get_claim_by_report_id", "Demo claims", "DB lookup"),
        ("POST", "/api/chat", "Yes", "All", "{message, history, satellite_date}", "response, action", "process_chat", "DeepSeek or templates", "Same"),
        ("GET", "/api/notifications", "Yes", "All", "—", "notifications", "get_notifications_for_user", "notifications.json", "DB"),
        ("POST", "/api/notifications/{id}/read", "Yes", "All", "—", "notification", "mark_notification_read", "JSON file", "DB UPDATE"),
    ]
    w("| Method | Path | Auth | Request | Response | Internal | Demo vs Prod |")
    w("|--------|------|------|---------|----------|----------|--------------|")
    def ep(e, i, default="—"):
        return e[i] if len(e) > i else default

    for e in endpoints:
        demo, prod = ep(e, 7), ep(e, 8)
        w(f"| {e[0]} | `{e[1]}` | {e[2]} | {ep(e,3)} | {ep(e,5)} | {ep(e,6)} | {demo} / {prod} |")
    w("")

    # 2.5 Database Schema
    w("### 2.5 Database Schema Reference")
    w("")
    w("Schema defined in `database/schema.sql`. Tables:")
    w("")
    w("**users** — `id` UUID PK, `email` UNIQUE, `password_hash`, `role` CHECK (MAO, DA_REGIONAL, PCIC only), `municipality_id`, names, timestamps. Indexes: email, municipality_id.")
    w("")
    w("**municipalities** — `id` VARCHAR PK, `name`, `province`, `region`, lat/lng, `total_farms`, `total_area_hectares`. Indexes: region, province.")
    w("")
    w("**farm_parcels** — `id` VARCHAR PK, `rsbsa_number` UNIQUE, `farmer_name`, `municipality_id` FK, `crop_type`, `area_hectares` > 0, lat/lng, `polygon` JSONB, dates, `is_insured`, `status` CHECK. Indexes: municipality, rsbsa, crop, location.")
    w("")
    w("**satellite_imagery** — `id` UUID PK, `parcel_id` FK, `capture_date`, `ndvi_value` -1..1, `image_url`, `cloud_cover_percentage`, `data_source`. UNIQUE (parcel_id, capture_date).")
    w("")
    w("**claims** — Full claim lifecycle: numbers, parcel FK, farmer, damage fields, NDVI before/after, images, AI text, `status` CHECK (PENDING, APPROVED, FLAGGED, REJECTED, SUBMITTED), verifier FK, timestamps, `rejection_reason`.")
    w("")
    w("**notifications** — `user_id` FK, `type`, `title`, `message`, optional `claim_id` FK, `is_read`. Indexes: user, unread partial, created.")
    w("")
    w("Note: `flag_reason` column used in code but **not** in schema.sql — add via migration before production PCIC flag workflow on PostgreSQL.")
    w("")

    # 2.6 Demo Data
    w("### 2.6 The Demo Data Reference")
    w("")
    w("**Demo password (all users):** `demo123`")
    w("")
    w("**Users:**")
    w("")
    w("| Email | Role | Municipality | Name |")
    w("|-------|------|--------------|------|")
    w("| mao.naga@da.gov.ph | MAO | camarine-naga | John Doe |")
    w("| regional.x@da.gov.ph | DA_REGIONAL | camarine-naga | Jane Doe |")
    w("| pcic.x@pcic.gov.ph | PCIC | camarine-naga | Juan Dela Cruz |")
    w("")
    w("**Farm parcels:**")
    w("")
    for f in farms["farms"]:
        w(f"- **{f['id']}** — {f['farmer_name']}, {f['rsbsa_number']}, {f['crop_type']}, {f['area_hectares']} ha, insured={f.get('is_insured', False)}")
    w("")
    w("**Satellite imagery:** 80 records (20 per parcel), dates 2024-09-01 through 2024-11-25, NDVI declines post-Typhoon Kristine (Oct 22).")
    w("")
    w("**Demo claims:** Stored in `data/demo_claims.json` (30+ records with varied statuses). `database/seed.sql` does **not** seed claims or satellite_imagery — only municipalities, users, and farm_parcels.")
    w("")
    w("---")
    w("")

    # Section 3
    w("## 3. Pre-Deployment Assessment")
    w("")
    w("### 3.1 Security Gaps")
    w("")
    w("| Item | Current State | Production Requirement | Effort |")
    w("|------|---------------|------------------------|--------|")
    w("| JWT storage | localStorage | httpOnly cookies | Medium |")
    w("| VERIFY_SECRET fallback | Hardcoded default | Required random env | Low |")
    w("| CORS | allow_methods/headers * | Explicit origins only | Low |")
    w("| Rate limiting | Login only | Extend to sensitive endpoints | Medium |")
    w("| ChatMarkdown sanitization | Custom markdown, no DOMPurify | Sanitize AI HTML/links | Low |")
    w("| EE credentials on disk | backend/credentials/ | Secrets Manager / env mount | Low |")
    w("| Docker Compose JWT default | change-me-in-production | Remove from compose file | Low |")
    w("")
    w("### 3.2 Infrastructure Gaps")
    w("")
    w("| Item | Current State | Production Requirement | Effort |")
    w("|------|---------------|------------------------|--------|")
    w("| CI/CD | None | GitHub Actions deploy | Medium |")
    w("| Migrations | Manual SQL | Migration runner | Medium |")
    w("| Health check | /api/health exists | Configure EB health check path | Low |")
    w("| Background jobs | In-memory | Persistent queue | High |")
    w("| Log aggregation | stdout only | CloudWatch Logs | Low |")
    w("| Error monitoring | None | Sentry | Low |")
    w("| Uptime monitoring | None | UptimeRobot/Pingdom | Low |")
    w("")
    w("### 3.3 Application Gaps")
    w("")
    w("| Item | Current State | Production Requirement | Effort |")
    w("|------|---------------|------------------------|--------|")
    w("| Notifications | In-app only | Email/SMS | High |")
    w("| Payouts | Estimated formulas | Real disbursement integration | High |")
    w("| Regional advisories | Client-side rules | Real advisory system | High |")
    w("| Admin user | Not in seed | ADMIN user + schema update | Low |")
    w("| File upload | None | Document attachments | Medium |")
    w("| Real-time | Polling only | WebSockets optional | High |")
    w("")
    w("### 3.4 What Can Be Deployed As-Is")
    w("")
    w("With correct env vars (no code changes):")
    w("- Login/logout JWT auth with rate limiting")
    w("- MAO dashboard, farm list, farm detail (PostgreSQL data)")
    w("- Claim filing and verification (requires Earth Engine credentials for live NDVI)")
    w("- PCIC approve/reject/flag workflow")
    w("- PDF report generation")
    w("- Public QR verification page")
    w("- In-app notifications")
    w("- Chatbot (with DeepSeek key; templates without)")
    w("- Sentinel View panel (with Sentinel Hub keys; static previews without)")
    w("")
    w("Caveats: seeded production DB has farms but no satellite_imagery rows until scans or manual import; demo claims not in seed.sql.")
    w("")
    w("### 3.5 What Must Be Changed Before Going Live")
    w("")
    w("**Blockers:**")
    w("1. Set strong `JWT_SECRET_KEY` and `VERIFY_SECRET` — remove default fallback in `verify.py`")
    w("2. Set `DATABASE_URL` to Supabase direct connection (not `demo`)")
    w("3. Set `CORS_ORIGINS` to exact production frontend URL")
    w("4. Set `VERIFY_BASE_URL` to production domain")
    w("5. Set `NEXT_PUBLIC_API_URL` to production API URL")
    w("6. Remove or gate demo credentials on login page")
    w("7. Resolve `frontend/.git` nested repo for Amplify")
    w("8. Add `flag_reason` column to claims table if using PCIC flag")
    w("")
    w("---")
    w("")

    # Sections 4-12 - deployment playbook
    w("## 4. Domain Setup")
    w("")
    w("### 4.1 DNS Configuration")
    w("")
    w("Assume domain `bantayani.cloud` (replace with your domain):")
    w("")
    w("| Record | Type | Name | Value | TTL |")
    w("|--------|------|------|-------|-----|")
    w("| Frontend | CNAME or ALIAS | `@` or `app` | Amplify CloudFront distribution | 300 |")
    w("| API | CNAME | `api` | Elastic Beanstalk environment URL | 300 |")
    w("| Verification | Same as frontend | `@` or `app` | `/verify/*` routes on Next.js — no separate record | — |")
    w("")
    w("QR codes use `VERIFY_BASE_URL` (frontend domain) + `/verify/BA-{claim_number}`.")
    w("")
    w("Propagation: 5 minutes to 48 hours. Verify: `dig api.bantayani.cloud`, `curl -I https://bantayani.cloud`.")
    w("")
    w("### 4.2 SSL/TLS")
    w("")
    w("- **Amplify:** Automatic ACM certificate when custom domain connected.")
    w("- **Elastic Beanstalk:** ACM certificate on load balancer — create cert in `ap-southeast-1`, attach to HTTPS listener on port 443.")
    w("- **Simplest path:** Amplify handles frontend SSL automatically; EB + ACM for API. Avoid manual Certbot unless using raw EC2.")
    w("")
    w("---")
    w("")

    w("## 5. Supabase Setup (Database)")
    w("")
    w("### 5.1 Create the Supabase Project")
    w("1. Go to [supabase.com](https://supabase.com) → New Project")
    w("2. Region: **Southeast Asia (Singapore)** — `ap-southeast-1`")
    w("3. Database password: min 12 chars, mixed case, numbers, symbols — save in password manager")
    w("4. Project URL: `https://[PROJECT-REF].supabase.co` (for dashboard only — backend uses DATABASE_URL)")
    w("5. Anon key: not needed for this architecture (backend uses direct postgres connection)")
    w("")
    w("### 5.2 Get the Connection String")
    w("- **Direct** (use this): `postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`")
    w("- **Pooler** (port 6543): for serverless — **do not use** with current psycopg2 per-request connections")
    w("- Replace `[PASSWORD]` with your database password; URL-encode special characters")
    w("")
    w("### 5.3 Run the Schema")
    w("1. Supabase → SQL Editor → New query")
    w("2. Paste entire `database/schema.sql` → Run")
    w("3. Verify in Table Editor: users, municipalities, farm_parcels, satellite_imagery, claims, notifications")
    w("")
    w("### 5.4 Run the Seed Data")
    w("1. Paste `database/seed.sql` → Run")
    w("2. Verify: 1 municipality, 3 users, 4 farm parcels")
    w("3. Optionally import satellite_imagery from demo data or run NDVI scans in production")
    w("")
    w("### 5.5 Supabase Row Level Security")
    w("- Tables created via SQL Editor do **not** auto-enable RLS")
    w("- Backend connects as `postgres` superuser — RLS not required; authorization is in FastAPI JWT layer")
    w("- Verify: Table Editor → each table → RLS should show **disabled** (acceptable for this architecture)")
    w("")
    w("### 5.6 Supabase Environment Variable")
    w("```bash")
    w("DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres")
    w("```")
    w("")
    w("### 5.7 Connection Pooling Considerations")
    w("- Current: new psycopg2 connection per `execute_query()` — no pool")
    w("- Supabase free tier: ~60 direct connections")
    w("- Risk: connection exhaustion under concurrent load")
    w("- Fix: add `psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=10)` in `database.py` — **Medium effort**")
    w("")
    w("---")
    w("")

    w("## 6. AWS Services Setup")
    w("")
    w("### 6.1 AWS Account and IAM Setup")
    w("1. Create AWS account")
    w("2. IAM → Users → Create `bantayani-deploy`")
    w("3. Attach: `AmazonEC2FullAccess`, `AmazonS3FullAccess`, `CloudFrontFullAccess`, `AWSCertificateManagerFullAccess`, `AdministratorAccess-AWSElasticBeanstalk`")
    w("4. Create access key → `aws configure` → region `ap-southeast-1`")
    w("")
    w("### 6.2 Decision: Which AWS Services to Use")
    w("")
    w("**Option A: Elastic Beanstalk (Recommended)** — Docker deploy, managed LB, health checks, ~$8-15/mo t3.micro")
    w("")
    w("**Option B: EC2 Manual** — cheaper sustained, more ops work (Nginx, Certbot, Docker)")
    w("")
    w("**Recommendation:** Amplify + Elastic Beanstalk for minimal ops experience.")
    w("")
    w("### 6.3 Frontend: AWS Amplify Hosting")
    w("1. Remove nested git: `rm -rf frontend/.git` — single root repository")
    w("2. Amplify → Host web app → Connect GitHub")
    w("3. Root directory: `frontend`")
    w("4. Build: `npm run build` / Output: `.next` (Amplify Next.js 14 SSR preset)")
    w("5. Env: `NEXT_PUBLIC_API_URL=https://api.bantayani.cloud/api`")
    w("6. Custom domain: `bantayani.cloud` → automatic SSL")
    w("")
    w("### 6.4 Backend: AWS Elastic Beanstalk")
    w("1. Zip backend (exclude venv, __pycache__, .env):")
    w("```bash")
    w("cd backend && zip -r ../backend-deploy.zip . -x 'venv/*' -x '__pycache__/*' -x '.env'")
    w("```")
    w("2. EB → Create application → Docker platform → Upload zip")
    w("3. Environment properties — set all vars from Section 8")
    w("4. Health check: `/api/health`, port 8000")
    w("5. Custom domain: Route 53 or CNAME `api.bantayani.cloud` → EB environment URL")
    w("")
    w("### 6.5 Google Earth Engine Service Account")
    w("1. Google Cloud Console → IAM → Service account → Create key JSON")
    w("2. Register for Earth Engine access at earthengine.google.com")
    w("3. Upload JSON to EB instance at `/app/credentials/earth-engine-key.json` (not in git)")
    w("4. Set `GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/earth-engine-key.json`")
    w("")
    w("### 6.6 AWS S3 for Static Assets (Optional)")
    w("- Bucket `bantayani-assets` in ap-southeast-1")
    w("- Public read on `satellite-previews/*` prefix")
    w("- Code change needed in `sentinel_hub_service.py` to return S3 URLs instead of `/satellite-previews/` paths")
    w("")
    w("### 6.7 CloudFront (Optional)")
    w("- CDN in front of EB for API caching — cache only static paths, never `/api/*` mutations")
    w("- Amplify already includes CloudFront for frontend")
    w("")
    w("---")
    w("")

    w("## 7. Step-by-Step Deployment Sequence")
    w("")
    steps = [
        "Resolve git structure: root repo only, delete `frontend/.git`",
        "Remove VERIFY_SECRET hardcoded fallback in `backend/api/verify.py` — require env var",
        "Set CORS_ORIGINS to production frontend URL only",
        "Document VERIFY_BASE_URL in deployment env (production domain)",
        "Gate demo credentials on login page behind `NEXT_PUBLIC_SHOW_DEMO_CREDENTIALS=false`",
        "Set NEXT_PUBLIC_API_URL in Amplify to production API",
        "Create Supabase project → connection string → run schema.sql → run seed.sql",
        "Verify tables and seed data in Supabase Table Editor",
        "Create AWS IAM user and configure CLI (ap-southeast-1)",
        "Deploy frontend to Amplify → connect git → env vars → custom domain",
        "Deploy backend to Elastic Beanstalk → env vars → verify GET /api/health returns 200",
        "Configure DNS: api CNAME → EB, apex CNAME → Amplify",
        "Wait for DNS propagation and SSL provisioning",
        "Test login as mao.naga@da.gov.ph on production URL",
        "Confirm VERIFY_BASE_URL in EB env for PDF QR codes",
        "Generate PDF report → scan QR → verify /verify/BA-* page loads",
        "Test PCIC login and approve/reject on production",
        "Test chatbot claim filing flow on production",
    ]
    for i, s in enumerate(steps, 1):
        w(f"{i}. {s}")
    w("")
    w("---")
    w("")

    w("## 8. Environment Variable Production Values")
    w("")
    w("| Variable | Service | Production Value | How to Generate | Secret? |")
    w("|----------|---------|------------------|-----------------|---------|")
    w("| DATABASE_URL | Backend | postgresql://postgres:...@db.REF.supabase.co:5432/postgres | Supabase Dashboard → Database | Yes |")
    w("| JWT_SECRET_KEY | Backend | 64-char hex string | `openssl rand -hex 32` | Yes |")
    w("| JWT_ALGORITHM | Backend | HS256 | Fixed | No |")
    w("| JWT_EXPIRATION_HOURS | Backend | 24 | Fixed | No |")
    w("| CORS_ORIGINS | Backend | https://bantayani.cloud | Your frontend URL | No |")
    w("| DEEPSEEK_API_KEY | Backend | sk-... | platform.deepseek.com | Yes |")
    w("| SENTINEL_HUB_CLIENT_ID | Backend | UUID from SH dashboard | sentinel-hub.com | Yes |")
    w("| SENTINEL_HUB_CLIENT_SECRET | Backend | secret from SH | sentinel-hub.com | Yes |")
    w("| GOOGLE_APPLICATION_CREDENTIALS | Backend | /app/credentials/earth-engine-key.json | GCP service account | Yes |")
    w("| VERIFY_BASE_URL | Backend | https://bantayani.cloud | Your frontend URL | No |")
    w("| VERIFY_SECRET | Backend | 64-char hex | `openssl rand -hex 32` | Yes |")
    w("| NEXT_PUBLIC_API_URL | Frontend | https://api.bantayani.cloud/api | Your API URL | No |")
    w("| NEXT_PUBLIC_GOOGLE_MAPS_KEY | Frontend | AIza... (optional) | Google Cloud Console | No |")
    w("")
    w("---")
    w("")

    w("## 9. What the Team Needs to Do Right Now vs Later")
    w("")
    w("### 9.1 Minimum to Go Live (Can Be Done Today)")
    w("- Supabase project + schema + seed")
    w("- Strong JWT_SECRET_KEY and VERIFY_SECRET")
    w("- Amplify frontend deploy with NEXT_PUBLIC_API_URL")
    w("- Elastic Beanstalk backend with DATABASE_URL and CORS_ORIGINS")
    w("- DNS for frontend and api subdomains")
    w("- Remove demo credentials from production login")
    w("- Fix nested frontend/.git")
    w("")
    w("### 9.2 Should Be Done Within One Week of Launch")
    w("- Connection pooling for Supabase")
    w("- CloudWatch logging + basic alarms")
    w("- Sentry error tracking")
    w("- Migrate VERIFY_SECRET fallback removal")
    w("- Import or scan satellite_imagery for production farms")
    w("- Add flag_reason column migration")
    w("")
    w("### 9.3 Can Be Done Over Time")
    w("- httpOnly cookie auth + refresh tokens")
    w("- CI/CD pipeline")
    w("- Automated tests")
    w("- Redis job queue")
    w("- Email notifications")
    w("- S3 for satellite previews")
    w("- TypeScript migration")
    w("")
    w("---")
    w("")

    w("## 10. Troubleshooting Reference")
    w("")
    troubles = [
        ("Backend 500 on all requests", "DATABASE_URL wrong or Supabase unreachable", "Test connection from EB SSH; verify password URL-encoding"),
        ("CORS errors in browser", "CORS_ORIGINS mismatch", "Must include exact protocol + domain, no trailing slash on API"),
        ("JWT errors on protected routes", "JWT_SECRET_KEY mismatch", "Re-login after key change; verify EB env"),
        ("Satellite imagery black", "EE/SH credentials missing", "System falls back to static previews in frontend/public"),
        ("PDF QR wrong domain", "VERIFY_BASE_URL unset", "Set to https://your-frontend-domain"),
        ("Login OK but empty data", "Seed not run", "Run seed.sql; check farm_parcels table"),
        ("Claims page empty for MAO", "Municipality scoping", "MAO user municipality_id must match farm municipality_id"),
        ("NDVI scan never completes", "EE not configured in production", "Confirm DATABASE_URL is postgres URL not demo"),
    ]
    for title, cause, fix in troubles:
        w(f"**{title}**")
        w(f"- Cause: {cause}")
        w(f"- Fix: {fix}")
        w("")
    w("---")
    w("")

    w("## 11. Cost Estimate")
    w("")
    w("| Service | Plan | Monthly Cost (USD) | Notes |")
    w("|---------|------|-------------------|-------|")
    w("| Supabase | Free tier | $0 | 500MB DB, 2GB bandwidth |")
    w("| AWS Amplify | Pay-per-use | ~$1-5 | Build minutes + transfer |")
    w("| AWS Elastic Beanstalk (t3.micro) | On-demand | ~$8-15 | Single instance |")
    w("| AWS Certificate Manager | Free | $0 | SSL certificates |")
    w("| Google Earth Engine | Non-commercial | $0 | Requires approved project |")
    w("| DeepSeek API | Pay-per-token | ~$1-5 | Chat volume dependent |")
    w("| Domain registration | Annual | ~$12/year | Already owned |")
    w("| **Total** | | **~$10-25/month** | At minimal scale |")
    w("")
    w("Costs increase with: traffic, Amplify build frequency, multiple EB instances, Supabase Pro ($25/mo) when exceeding 500MB or 60 connections.")
    w("")
    w("---")
    w("")

    w("## 12. Security Checklist Before Going Live")
    w("")
    checklist = [
        ("VERIFY_SECRET is randomly generated with no hardcoded fallback", "Prevents forged report integrity hashes", "Set env var; patch verify.py"),
        ("JWT_SECRET_KEY is 64+ character random string", "Prevents token forgery", "openssl rand -hex 32"),
        ("CORS_ORIGINS lists only exact production frontend domain", "Prevents cross-site API abuse", "No wildcards"),
        ("Earth Engine JSON not in git repository", "Prevents credential leak", "Use .gitignore; rotate if committed"),
        ("Docker Compose default JWT secret removed", "Repo hygiene", "Remove change-me-in-production default"),
        ("Demo credentials not on production login page", "Prevents unauthorized access", "Gate with env var"),
        ("All secrets in Amplify/Beanstalk env, not committed", "Prevents leak", "Never commit .env"),
        ("backend/.env in .gitignore", "Local secret protection", "Verify git history"),
        ("frontend/.env.local in .gitignore", "Local secret protection", "Verify git history"),
        ("HTTPS enforced on all endpoints", "Prevents MITM", "Amplify + EB HTTPS listeners"),
        ("/api/health does not expose sensitive info", "Reduces reconnaissance", "Only returns status and mode"),
    ]
    for item, why, fix in checklist:
        w(f"- [ ] {item}")
        w(f"  - Why: {why}. If no: {fix}")
    w("")
    w("---")
    w("")
    w("*End of Bantay Ani Production Deployment Guide.*")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(lines)} lines to {OUT}")

if __name__ == "__main__":
    main()