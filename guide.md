# Bantay Ani — Production Deployment Guide

**Document purpose:** Complete codebase comprehension reference and step-by-step production deployment playbook for AWS + Supabase.

**Last updated:** June 26, 2026

---

## Table of Contents

- [1. System Architecture Overview](#1-system-architecture-overview)
  - [1.1 What Bantay Ani Is](#11-what-bantay-ani-is)
  - [1.2 Architecture Diagram](#12-architecture-diagram)
  - [1.3 The Two Operating Modes](#13-the-two-operating-modes)
  - [1.4 User Roles and Access Boundaries](#14-user-roles-and-access-boundaries)
  - [1.5 Data Flow for Each Core Workflow](#15-data-flow-for-each-core-workflow)
  - [1.6 Current Limitations and Technical Debt](#16-current-limitations-and-technical-debt)
- [2. Complete Codebase Reference](#2-complete-codebase-reference)
  - [2.1 Backend Module Map](#21-backend-module-map)
  - [2.2 Frontend Module Map](#22-frontend-module-map)
  - [2.3 Environment Variables — Complete Reference](#23-environment-variables--complete-reference)
  - [2.4 API Endpoint Reference](#24-api-endpoint-reference)
  - [2.5 Database Schema Reference](#25-database-schema-reference)
  - [2.6 The Demo Data Reference](#26-the-demo-data-reference)
- [3. Pre-Deployment Assessment](#3-pre-deployment-assessment)
  - [3.1 Security Gaps](#31-security-gaps)
  - [3.2 Infrastructure Gaps](#32-infrastructure-gaps)
  - [3.3 Application Gaps](#33-application-gaps)
  - [3.4 What Can Be Deployed As-Is](#34-what-can-be-deployed-as-is)
  - [3.5 What Must Be Changed Before Going Live](#35-what-must-be-changed-before-going-live)
- [4. Domain Setup](#4-domain-setup)
  - [4.1 DNS Configuration](#41-dns-configuration)
  - [4.2 SSL/TLS](#42-ssl/tls)
- [5. Supabase Setup (Database)](#5-supabase-setup-database)
  - [5.1 Create the Supabase Project](#51-create-the-supabase-project)
  - [5.2 Get the Connection String](#52-get-the-connection-string)
  - [5.3 Run the Schema](#53-run-the-schema)
  - [5.4 Run the Seed Data](#54-run-the-seed-data)
  - [5.5 Supabase Row Level Security](#55-supabase-row-level-security)
  - [5.6 Supabase Environment Variable](#56-supabase-environment-variable)
  - [5.7 Connection Pooling Considerations](#57-connection-pooling-considerations)
- [6. AWS Services Setup](#6-aws-services-setup)
  - [6.1 AWS Account and IAM Setup](#61-aws-account-and-iam-setup)
  - [6.2 Decision: Which AWS Services to Use](#62-decision:-which-aws-services-to-use)
  - [6.3 Frontend: AWS Amplify Hosting](#63-frontend:-aws-amplify-hosting)
  - [6.4 Backend: AWS Elastic Beanstalk](#64-backend:-aws-elastic-beanstalk)
  - [6.5 Google Earth Engine Service Account](#65-google-earth-engine-service-account)
  - [6.6 AWS S3 for Static Assets (Optional)](#66-aws-s3-for-static-assets-(optional))
  - [6.7 CloudFront (Optional but Recommended)](#67-cloudfront-(optional-but-recommended))
- [7. Step-by-Step Deployment Sequence](#7-step-by-step-deployment-sequence)
- [8. Environment Variable Production Values](#8-environment-variable-production-values)
- [9. What the Team Needs to Do Right Now vs Later](#9-what-the-team-needs-to-do-right-now-vs-later)
  - [9.1 Minimum to Go Live](#91-minimum-to-go-live)
  - [9.2 Should Be Done Within One Week](#92-should-be-done-within-one-week)
  - [9.3 Can Be Done Over Time](#93-can-be-done-over-time)
- [10. Troubleshooting Reference](#10-troubleshooting-reference)
- [11. Cost Estimate](#11-cost-estimate)
- [12. Security Checklist Before Going Live](#12-security-checklist-before-going-live)

---

## 1. System Architecture Overview

### 1.1 What Bantay Ani Is

Bantay Ani is a satellite crop monitoring and crop insurance claims verification platform for the Philippine Department of Agriculture ecosystem. It serves three primary user types:

| Role | Organization | Primary use |
|------|--------------|-------------|
| **MAO** | Municipal Agricultural Officer | Monitors farm health in their municipality, runs NDVI scans, files and verifies insurance claims |
| **DA Regional** | Department of Agriculture Regional Office | Views regional crop health, damage summaries, and advisories across municipalities |
| **PCIC** | Philippine Crop Insurance Corporation | Reviews submitted claims, approves/rejects/flags, views analytics and estimated payouts |

The system has two core modules:

- **TANAW** (crop health monitoring): Dashboard map with NDVI-colored farm polygons, satellite date selector, municipality farm lists, regional health overview, NDVI scan jobs.
- **BAWI** (claim verification): Satellite-based before/after NDVI comparison, fraud detection, AI assessment, PDF reports with QR verification, PCIC claim workflow.

The demo case study is **Typhoon Kristine** (October 22–24, 2024) flood damage to rice farms in **Naga City, Camarines Sur**.

### 1.2 Architecture Diagram (Text-Based)

```mermaid
flowchart TB
    subgraph clients [Clients - Stateless]
        Browser[Next.js 14 Frontend<br/>Port 3000]
    end
    subgraph aws [AWS Production]
        Amplify[AWS Amplify<br/>Static/SSR Frontend]
        EB[Elastic Beanstalk<br/>FastAPI Docker :8000]
    end
    subgraph stateful [Stateful / External]
        Supabase[(Supabase PostgreSQL)]
        EE[Google Earth Engine]
        SH[Sentinel Hub API]
        DS[DeepSeek API]
    end
    Browser -->|HTTPS JWT Bearer| Amplify
    Amplify -->|NEXT_PUBLIC_API_URL| EB
    EB -->|DATABASE_URL direct| Supabase
    EB -->|GOOGLE_APPLICATION_CREDENTIALS| EE
    EB -->|SENTINEL_HUB_*| SH
    EB -->|DEEPSEEK_API_KEY| DS
    Browser -->|Public /verify/BA-*| EB
```

**Stateless components:** Next.js frontend (after build), FastAPI workers (JWT in request, in-memory job cache only).

**Stateful components:** Supabase PostgreSQL (users, farms, claims, notifications, satellite_imagery), Earth Engine tile cache in `app.state.satellite_cache`, in-memory `_scan_jobs` and `_claim_verify_jobs` on backend.

### 1.3 The Two Operating Modes

The entire backend switches between **demo mode** and **production mode** based on a single environment variable.

**Trigger:** `DATABASE_URL` set to `demo`, empty string, or `none` (default in `backend/.env.example` is `demo`).

```python
# backend/utils/database.py
DATABASE_URL = os.getenv('DATABASE_URL', 'demo')
DEMO_MODE = DATABASE_URL in ('', 'demo', 'none')
```

| Aspect | Demo Mode | Production Mode |
|--------|-----------|-----------------|
| Database | `data/farms.json`, `data/demo_claims.json`, `data/notifications.json` via `_execute_demo_query()` | PostgreSQL via psycopg2 |
| NDVI scan jobs | `_run_scan_job_demo()` — synthetic NDVI, writes to farms.json | `compute_ndvi_for_location()` via Earth Engine |
| Claim verify async | `_run_claim_verify_job_demo()` with staged progress | Full `verify_claim_with_satellite()` |
| Available satellite dates | Hardcoded `DEMO_AVAILABLE_DATES` in `api/satellite.py` | Earth Engine or Sentinel Hub catalog |
| Satellite imagery API | Static previews from `frontend/public/satellite-previews/` | Live EE/SH with static fallback |
| Health check | `mode: demo` | `mode: production` |
| Startup | `ensure_farms_data_integrity()` on farms.json | Earth Engine init from credentials |

**All `is_demo_mode()` check locations:**

- `backend/utils/database.py` — core switch
- `backend/main.py` — lifespan integrity check, health endpoint
- `backend/api/satellite.py` — available-dates, sentinel-dates
- `backend/services/satellite_service.py` — scan jobs, save NDVI records, is_date_scanned
- `backend/services/claim_service.py` — claims CRUD, verify jobs, notifications
- `backend/services/farm_service.py` — farm listing, add farm
- `backend/services/notification_service.py` — all notification paths
- `backend/services/chat_service.py` — NDVI history, claims for intents
- `backend/services/role_service.py` — regional municipalities fallback
- `backend/utils/polygon_placement.py` — existing farm lookup

Additional check: `os.environ.get('DATABASE_URL', 'demo') == 'demo'` in `satellite.py` and `satellite_service._run_scan_job()`.

### 1.4 User Roles and Access Boundaries

| Role | Dashboard | Farms | Claims | Regional | PCIC | Mechanism |
|------|-----------|-------|--------|----------|------|-----------|
| MAO | Yes (redirect from /dashboard) | Own municipality only | Own municipality | No | No | `check_municipality_access()` |
| DA_REGIONAL | Redirects to /regional/overview | All municipalities in region | Regional summary | Yes | No | `_require_regional()` on regional endpoints |
| PCIC | Redirects to /pcic/claims-queue | Read via claims | All claims | Analytics only | Yes | `_require_pcic()` |
| ADMIN | Same as MAO in frontend | Code checks ADMIN like DA_REGIONAL for regional health | Not in DB schema | Yes in code | No | **Not seeded; schema CHECK excludes ADMIN** |

**RBAC mechanism:** JWT Bearer token → `get_current_user()` decodes `user_id`, `email`, `role`, `municipality_id` → per-route checks:

- `check_municipality_access(user, municipality_id)` — MAO must match municipality; DA_REGIONAL, PCIC, ADMIN bypass
- `_require_pcic(user)` — claims approve/reject/flag/reverse, analytics, payouts
- `_require_regional(user)` — `/api/farms/regional/health`, `/api/claims/regional/summary`

### 1.5 Data Flow for Each Core Workflow

#### MAO login and dashboard
1. `POST /api/login` → `authenticate_user()` → bcrypt verify → `create_access_token()` → frontend `saveToken()` + `saveUser()` to **localStorage**
2. Redirect to `/dashboard` (MAO role)
3. `GET /api/farms/municipality/{id}?satellite_date=...` → farm list with NDVI status for selected date
4. `GET /api/satellite/ndvi-tiles` → map overlay tile URL
5. Background: `start_background_ndvi_refresh()` may update NDVI via Earth Engine thread

#### MAO NDVI scan
1. Dashboard or Sentinel panel → `POST /api/satellite/scan-ndvi` with `municipality_id` + `satellite_date`
2. `start_ndvi_scan_job()` creates in-memory job, starts daemon thread
3. Demo: `_run_scan_job_demo()` writes to farms.json; Production: `compute_ndvi_for_location()` per farm → `satellite_imagery` table
4. Frontend polls `GET /api/satellite/scan-status/{job_id}` until `completed`

#### MAO filing claim via Claims page
1. `ClaimForm` → `POST /api/claims/verify` with RSBSA, disaster_date, damage_type, claimed_area
2. `verify_claim_with_satellite()` → Earth Engine `compute_multi_index()` before/after windows → fraud rules → AI assessment → INSERT claims
3. `VerificationResult` displays status, NDVI comparison, images
4. Optional: `POST /api/claims/{id}/submit` → notifies PCIC

#### Chatbot-initiated claim
1. `POST /api/chat` → `classify_intent` → `file_claim` → confirmation card
2. User confirms → `POST /api/claims/verify-async` → background job
3. Poll `scan-status` endpoint (shared job store) → redirect to claims with prefilled data

#### PCIC approving a claim
1. PCIC login → `/pcic/claims-queue`
2. `GET /api/claims` (all municipalities)
3. `POST /api/claims/{id}/approve` → `_require_pcic` → UPDATE status → `notify_mao_claim_status_change()`

#### PDF report and QR verification
1. `POST /api/reports/generate` with `claim_id` → ReportLab PDF
2. QR encodes `{VERIFY_BASE_URL}/verify/BA-{claim_number}`
3. Public `GET /api/verify/{report_id}` — no auth, masks farmer name, returns `report_integrity` SHA256 hash
4. Frontend `/verify/[id]` page fetches API and renders verification UI

### 1.6 Current Limitations and Technical Debt

| Item | Risk | Production fix | Difficulty |
|------|------|----------------|------------|
| JWT in localStorage | XSS can steal tokens | httpOnly Secure SameSite cookies + CSRF token | Moderate |
| No refresh tokens | 24h sessions; re-login on expiry | Refresh token rotation | Moderate |
| VERIFY_SECRET default fallback | Anyone can forge integrity hashes | Require env var, remove `DEFAULT_VERIFY_SECRET` | Easy |
| In-memory background jobs | Lost on restart; no multi-instance | Redis/DB job queue (Celery, ARQ) | Complex |
| No migration runner | Schema changes manual | Alembic or similar | Moderate |
| No automated tests | Regressions undetected | pytest + Playwright | Moderate |
| No CI/CD | Manual deploy errors | GitHub Actions → Amplify + EB | Moderate |
| nested `frontend/.git` | Amplify cannot deploy monorepo correctly | Remove nested git; single root repo | Easy |
| openai package unused | Dependency bloat | Remove from requirements.txt | Easy |
| 120s API timeout in api.js | Masks slow failures; ties up connections | Per-endpoint timeouts; job polling | Easy |
| Synchronous FastAPI endpoints | Blocks worker under load | `async def` + async DB driver | Complex |
| Demo query handler fragility | New SQL patterns return None in demo | Integration tests for demo handler | Moderate |

---

## 2. Complete Codebase Reference

### 2.1 Backend Module Map

| File | Purpose | Key imports | Exports / routes | If removed |
|------|---------|-------------|------------------|------------|
| `main.py` | FastAPI app, CORS, lifespan, router mount, /api/health | api.*, earth_engine, middleware | app | Entire API down |
| `api/auth.py` | POST /login, rate limiting | auth_service, role_service | router | No authentication |
| `api/farms.py` | Farm CRUD, regional health, NDVI status | farm_service, auth_service | router | No farm data |
| `api/claims.py` | Claim verify, list, PCIC actions | claim_service | router | No claims module |
| `api/satellite.py` | Imagery, NDVI tiles, scan jobs | satellite_service, sentinel_hub | router | No satellite features |
| `api/reports.py` | PDF generation | claim_service, reportlab | router | No PDF reports |
| `api/verify.py` | Public verification | claim_service | router | QR verification broken |
| `api/chat.py` | Chatbot endpoint | chat_service | router | No AI chat |
| `api/notifications.py` | Notification list/read | notification_service | router | No notifications |
| `services/auth_service.py` | JWT, bcrypt, rate limit, RBAC deps | jose, passlib, database | get_current_user, create_access_token | All protected routes fail |
| `services/farm_service.py` | Farm queries, NDVI refresh, regional health | database, satellite_service, ndvi | get_farms_by_municipality, etc. | Dashboard empty |
| `services/claim_service.py` | Claim verification, PCIC workflow, jobs | satellite, ai, database | verify_claim_with_satellite, etc. | BAWI module broken |
| `services/satellite_service.py` | Earth Engine NDVI, scan jobs, tiles | earth_engine, database | start_ndvi_scan_job, compute_multi_index | No live NDVI |
| `services/sentinel_hub_service.py` | SH OAuth2, imagery, black image detect | httpx, PIL | get_sentinel_image_png, compute_ndvi_for_polygon | Sentinel View panel degraded |
| `services/chat_service.py` | Intent classification, DeepSeek | ai_service, database | process_chat | Chatbot broken |
| `services/ai_service.py` | DeepSeek API calls | httpx | call_deepseek, generate_claim_assessment | AI text → templates only |
| `services/ai_templates.py` | Fallback AI text | — | select_ai_recommendation | Generic recommendations only |
| `services/notification_service.py` | In-app notifications | database | create_notification, etc. | No alerts |
| `services/role_service.py` | Role-specific data for login | database | get_role_data | Login missing municipalities list |
| `services/earth_engine.py` | EE initialization | earthengine-api | initialize_earth_engine, is_ee_available | Live satellite disabled |
| `utils/database.py` | PostgreSQL + demo JSON handler | psycopg2 | execute_query, is_demo_mode | Total data layer failure |
| `utils/ndvi.py` | NDVI thresholds | — | classify_health_status | Wrong health colors |
| `utils/polygon_placement.py` | Farm polygon generation | database | generate_field_polygon | Add farm broken |
| `utils/edge_detection.py` | Edge detection utility | — | edge helpers | Unused in main flows |
| `models/auth.py` | Login Pydantic models | pydantic | LoginRequest | Validation errors |
| `models/claim.py` | Claim request models | pydantic | ClaimVerificationRequest | Claim API validation broken |
| `models/farm.py` | Farm request models | pydantic | AddFarmRequest | Add farm broken |
| `middleware/error_handler.py` | Unified error responses | fastapi | exception handlers | Raw stack traces |

### 2.2 Frontend Module Map

| Page | Renders | API calls | Roles | State |
|------|---------|-----------|-------|-------|
| `app/page.js` | Root redirect to login or dashboard | auth check | All | — |
| `app/login/page.js` | Login form + demo credentials panel | POST /login | Public | email, password, loading |
| `app/verify/[id]/page.js` | Public QR verification page | GET /verify/{id} | Public | verification state |
| `app/(authenticated)/dashboard/page.js` | MAO map dashboard, NDVI scan | farms/municipality, ndvi-tiles, scan-ndvi | MAO, ADMIN | farms, stats, map, scan job |
| `app/(authenticated)/farms/page.js` | Farm list | GET farms/municipality | MAO | farms list |
| `app/(authenticated)/farms/[id]/page.js` | Farm detail | GET farms/{id} | MAO | farm, NDVI history |
| `app/(authenticated)/claims/page.js` | Claim filing | GET/POST claims | MAO | claims, form |
| `app/(authenticated)/reports/page.js` | Report list + PDF download | GET claims, POST reports/generate | MAO | claims, PDF |
| `app/(authenticated)/cases/page.js` | Case list | GET claims | PCIC | claims |
| `app/(authenticated)/case/[id]/page.js` | PCIC case detail + actions | GET claims/{id}, approve/reject/flag | PCIC | claim, actions |
| `app/(authenticated)/pcic/claims-queue/page.js` | PCIC queue | GET claims, PCIC actions | PCIC | claims, filters |
| `app/(authenticated)/pcic/analytics/page.js` | PCIC analytics | GET claims/pcic/analytics | PCIC | analytics |
| `app/(authenticated)/pcic/payouts/page.js` | Estimated payouts | GET claims/pcic/payouts | PCIC | payouts |
| `app/(authenticated)/pcic/map/page.js` | Claims map | GET claims, farms | PCIC | map markers |
| `app/(authenticated)/regional/overview/page.js` | Regional overview | GET farms/regional/health | DA_REGIONAL | municipalities |
| `app/(authenticated)/regional/health/page.js` | Regional health table | GET farms/regional/health | DA_REGIONAL | health data |
| `app/(authenticated)/regional/damage-reports/page.js` | Damage summary | GET claims/regional/summary | DA_REGIONAL | summary |
| `app/(authenticated)/regional/advisories/page.js` | Client-side advisories | GET farms/regional/health | DA_REGIONAL | advisories |
| `app/(authenticated)/search/page.js` | Global search | GET farms, claims | All authenticated | results |
| `app/(authenticated)/settings/page.js` | Satellite date settings | SatelliteDateContext | All | date prefs |

| Component | Renders | API calls | Roles | State |
|-----------|---------|-----------|-------|-------|
| `ChatWidget.js` | Floating chatbot | POST /chat, scan-status | MAO+ | messages, job polling |
| `ChatMarkdown.js` | Renders AI markdown | — | All | parsed blocks — no HTML sanitization |
| `ClaimForm.js` | Claim verification form | POST /claims/verify | MAO | form, result |
| `VerificationResult.js` | Post-verify UI | POST submit | MAO | result, images |
| `MapView.js / GoogleMapView.js` | Leaflet/Google map | ndvi-tiles | MAO | farms, selection |
| `SentinelImagePanel.js` | Satellite panel + scan | sentinel-image, scan-ndvi | MAO | imagery, job |
| `Header.js` | Top bar + notifications | GET notifications | All | notifications |
| `Sidebar.js` | Role-based nav | — | All | nav items |
| `AddFarmerModal.js` | Add/edit farm | POST/PUT farms | MAO | form |

### 2.3 Environment Variables — Complete Reference

| Variable | Read by | Controls | Local dev | Production | If wrong | Secret? |
|----------|---------|----------|-----------|------------|----------|---------|
| `DATABASE_URL` | backend | PostgreSQL URL or demo trigger | demo | postgresql://postgres:PASS@db.REF.supabase.co:5432/postgres | Demo JSON if demo/empty; connection errors if wrong URL | Secret |
| `JWT_SECRET_KEY` | backend | JWT signing key | generate-with-python-secrets | 64-char hex from openssl rand -hex 32 | Startup refusal if default; 401 if mismatch | Secret |
| `JWT_ALGORITHM` | backend | JWT algorithm | HS256 | HS256 | Token decode fails if changed | Safe |
| `JWT_EXPIRATION_HOURS` | backend | Token TTL hours | 24 | 24 (reduce to 1 for prod hardening) | Session length | Safe |
| `CORS_ORIGINS` | backend | Allowed frontend origins | http://localhost:3000 | https://bantayani.cloud | CORS errors if mismatch | Safe |
| `DEEPSEEK_API_KEY` | backend | DeepSeek chat/assessment | empty | From platform.deepseek.com | Template fallback if empty | Secret |
| `OPENROUTER_API_KEY` | backend | Unused fallback key in .env.example | empty | Optional | Not used in code paths | Secret |
| `DEEPSEEK_MODEL` | backend | Model name in ai_service | deepseek-chat | deepseek-chat | Wrong model if invalid | Safe |
| `SENTINEL_HUB_CLIENT_ID` | backend | Sentinel Hub OAuth | empty | From sentinel-hub.com | Static preview fallback | Secret |
| `SENTINEL_HUB_CLIENT_SECRET` | backend | Sentinel Hub OAuth | empty | From sentinel-hub.com | Static preview fallback | Secret |
| `GOOGLE_APPLICATION_CREDENTIALS` | backend | EE service account JSON path | ./credentials/earth-engine-key.json | /app/credentials/ee-key.json on server | Demo/static satellite if missing | Secret path |
| `GOOGLE_EE_PROJECT` | backend | EE project ID override | empty | From service account project_id | EE init may fail | Safe |
| `VERIFY_BASE_URL` | backend | QR link base in PDFs | http://localhost:3000 | https://bantayani.cloud | Wrong domain in QR codes | Safe |
| `VERIFY_SECRET` | backend | Report integrity hash salt | hardcoded default in verify.py | openssl rand -hex 32 | Predictable integrity if default | Secret |
| `NEXT_PUBLIC_API_URL` | frontend | API base URL | http://localhost:8000/api | https://api.bantayani.cloud/api | All API calls fail if wrong | Safe (public) |
| `NEXT_PUBLIC_GOOGLE_MAPS_KEY` | frontend | Google Maps (optional) | empty | Google Cloud Console | Map features limited | Safe (public) |

### 2.4 API Endpoint Reference

| Method | Path | Auth | Request | Response | Internal | Demo vs Prod |
|--------|------|------|---------|----------|----------|--------------|
| GET | `/api/health` | No | — | {status, mode} | main.py | Shows demo/production / Same |
| POST | `/api/login` | No | {email, password} | auth_service | Rate limited 5/15min | Demo users from JSON/DB / — |
| GET | `/api/farms/regional/health` | Yes | DA_REGIONAL, ADMIN | municipalities + stats | get_regional_health | Regional aggregation / PostgreSQL farms |
| GET | `/api/farms/next-rsbsa` | Yes | MAO+ | {rsbsa_number} | get_next_rsbsa_number | Sequential RSBSA / Same logic |
| POST | `/api/farms/add` | Yes | MAO | {parcel_id, rsbsa_number} | add_farm_parcel | Writes farms.json or DB / PostgreSQL INSERT |
| GET | `/api/farms/municipality/{id}` | Yes | MAO+ (scoped) | farms, stats, municipality | get_farms_by_municipality | Demo JSON LATERAL emulation / SQL LATERAL join |
| GET | `/api/farms/municipality/{id}/ndvi-status` | Yes | MAO+ | refresh status | get_municipality_ndvi_status | In-memory status / Same |
| GET | `/api/farms/by-rsbsa/{rsbsa}` | Yes | MAO scoped | farm object | execute_query | Demo farm lookup / DB lookup |
| GET | `/api/farms/{parcel_id}` | Yes | MAO scoped | farm + history + claims | get_farm_detail | Demo queries / SQL joins |
| PUT | `/api/farms/{parcel_id}` | Yes | MAO | updated farm | update_farm_parcel | Updates JSON or DB / SQL UPDATE |
| POST | `/api/claims/verify` | Yes | MAO | verification result | verify_claim_with_satellite | Demo uses EE if configured / Full EE multi-index |
| POST | `/api/claims/verify-async` | Yes | MAO | {job_id, status} | verify_claim_async | Demo staged job / Thread job |
| GET | `/api/claims` | Yes | All auth | claims list | get_claims_list | demo_claims.json / SQL paginated |
| GET | `/api/claims/{id}` | Yes | All auth | claim detail | get_claim_detail | Demo claims / SQL join |
| POST | `/api/claims/{id}/submit` | Yes | MAO | submitted claim | submit_claim_to_pcic | Updates demo/DB / Same |
| POST | `/api/claims/{id}/approve` | Yes | PCIC | claim | approve_claim | Demo update / SQL UPDATE |
| POST | `/api/claims/{id}/reject` | Yes | PCIC | claim | reject_claim | Demo update / SQL UPDATE |
| POST | `/api/claims/{id}/flag` | Yes | PCIC | claim | flag_claim | Demo update / SQL UPDATE |
| POST | `/api/claims/{id}/reverse` | Yes | PCIC | claim | reverse_claim_decision | Demo update / SQL UPDATE |
| GET | `/api/claims/regional/summary` | Yes | DA_REGIONAL | damage summary | get_regional_damage_summary | From demo claims / SQL aggregation |
| GET | `/api/claims/pcic/analytics` | Yes | PCIC | analytics | get_pcic_analytics | Demo claims / SQL aggregation |
| GET | `/api/claims/pcic/payouts` | Yes | PCIC | payouts | get_pcic_payouts | Estimated amounts / Same |
| GET | `/api/satellite/available-dates` | Yes | All | available_dates | get_available_sentinel_dates or demo list | DEMO_AVAILABLE_DATES / Earth Engine catalog |
| GET | `/api/satellite/imagery` | Yes | All | tile_url, bounds | get_sentinel_imagery | EE tiles / EE tiles |
| GET | `/api/satellite/ndvi-tiles` | Yes | All | tile_url, expires_at | get_ndvi_tiles_for_date | Cached/demo / EE/SH |
| GET | `/api/satellite/sentinel-dates` | Yes | All | available_dates | sentinel_hub or demo | Demo dates / SH catalog |
| POST | `/api/satellite/scan-ndvi` | Yes | MAO | 202 job | start_ndvi_scan_job | Fast demo scan / EE per farm |
| GET | `/api/satellite/scan-status/{job_id}` | Yes | All | job status | get_ndvi_scan_status | In-memory / In-memory |
| POST | `/api/satellite/compute-ndvi` | Yes | All | ndvi | compute_ndvi_for_polygon | DB seeded values / SH/DB |
| GET | `/api/satellite/sar-tiles` | Yes | All | flood tiles | get_sentinel1_flood_tile_url | EE SAR / EE SAR |
| GET | `/api/satellite/sentinel-image` | Yes | All | PNG stream | get_sentinel_image_png | Static previews / SH/EE/static |
| POST | `/api/reports/generate` | Yes | MAO+ | PDF stream | generate_pcic_report | Same / Same |
| GET | `/api/verify/{report_id}` | No | — | verification payload | get_claim_by_report_id | Demo claims / DB lookup |
| POST | `/api/chat` | Yes | All | response, action | process_chat | DeepSeek or templates / Same |
| GET | `/api/notifications` | Yes | All | notifications | get_notifications_for_user | notifications.json / DB |
| POST | `/api/notifications/{id}/read` | Yes | All | notification | mark_notification_read | JSON file / DB UPDATE |

### 2.5 Database Schema Reference

Schema defined in `database/schema.sql`. Tables:

**users** — `id` UUID PK, `email` UNIQUE, `password_hash`, `role` CHECK (MAO, DA_REGIONAL, PCIC only), `municipality_id`, names, timestamps. Indexes: email, municipality_id.

**municipalities** — `id` VARCHAR PK, `name`, `province`, `region`, lat/lng, `total_farms`, `total_area_hectares`. Indexes: region, province.

**farm_parcels** — `id` VARCHAR PK, `rsbsa_number` UNIQUE, `farmer_name`, `municipality_id` FK, `crop_type`, `area_hectares` > 0, lat/lng, `polygon` JSONB, dates, `is_insured`, `status` CHECK. Indexes: municipality, rsbsa, crop, location.

**satellite_imagery** — `id` UUID PK, `parcel_id` FK, `capture_date`, `ndvi_value` -1..1, `image_url`, `cloud_cover_percentage`, `data_source`. UNIQUE (parcel_id, capture_date).

**claims** — Full claim lifecycle: numbers, parcel FK, farmer, damage fields, NDVI before/after, images, AI text, `status` CHECK (PENDING, APPROVED, FLAGGED, REJECTED, SUBMITTED), verifier FK, timestamps, `rejection_reason`.

**notifications** — `user_id` FK, `type`, `title`, `message`, optional `claim_id` FK, `is_read`. Indexes: user, unread partial, created.

Note: `flag_reason` column used in code but **not** in schema.sql — add via migration before production PCIC flag workflow on PostgreSQL.

### 2.6 The Demo Data Reference

**Demo password (all users):** `demo123`

**Users:**

| Email | Role | Municipality | Name |
|-------|------|--------------|------|
| mao.naga@da.gov.ph | MAO | camarine-naga | John Doe |
| regional.x@da.gov.ph | DA_REGIONAL | camarine-naga | Jane Doe |
| pcic.x@pcic.gov.ph | PCIC | camarine-naga | Juan Dela Cruz |

**Farm parcels:**

- **BUK-001** — Juan Dela Cruz, RSBSA-BUK-2024-00412, Rice, 1.5 ha, insured=True
- **BUK-002** — Maria Santos, RSBSA-BUK-2024-00413, Rice, 2.0 ha, insured=True
- **BUK-003** — Pedro Reyes, RSBSA-BUK-2024-00999, Rice, 1.2 ha, insured=False
- **BUK-004** — Ana Mendoza, RSBSA-BUK-2024-00415, Corn, 1.8 ha, insured=True

**Satellite imagery:** 80 records (20 per parcel), dates 2024-09-01 through 2024-11-25, NDVI declines post-Typhoon Kristine (Oct 22).

**Demo claims:** Stored in `data/demo_claims.json` (30+ records with varied statuses). `database/seed.sql` does **not** seed claims or satellite_imagery — only municipalities, users, and farm_parcels.

---

## 3. Pre-Deployment Assessment

### 3.1 Security Gaps

| Item | Current State | Production Requirement | Effort |
|------|---------------|------------------------|--------|
| JWT storage | localStorage | httpOnly cookies | Medium |
| VERIFY_SECRET fallback | Hardcoded default | Required random env | Low |
| CORS | allow_methods/headers * | Explicit origins only | Low |
| Rate limiting | Login only | Extend to sensitive endpoints | Medium |
| ChatMarkdown sanitization | Custom markdown, no DOMPurify | Sanitize AI HTML/links | Low |
| EE credentials on disk | backend/credentials/ | Secrets Manager / env mount | Low |
| Docker Compose JWT default | change-me-in-production | Remove from compose file | Low |

### 3.2 Infrastructure Gaps

| Item | Current State | Production Requirement | Effort |
|------|---------------|------------------------|--------|
| CI/CD | None | GitHub Actions deploy | Medium |
| Migrations | Manual SQL | Migration runner | Medium |
| Health check | /api/health exists | Configure EB health check path | Low |
| Background jobs | In-memory | Persistent queue | High |
| Log aggregation | stdout only | CloudWatch Logs | Low |
| Error monitoring | None | Sentry | Low |
| Uptime monitoring | None | UptimeRobot/Pingdom | Low |

### 3.3 Application Gaps

| Item | Current State | Production Requirement | Effort |
|------|---------------|------------------------|--------|
| Notifications | In-app only | Email/SMS | High |
| Payouts | Estimated formulas | Real disbursement integration | High |
| Regional advisories | Client-side rules | Real advisory system | High |
| Admin user | Not in seed | ADMIN user + schema update | Low |
| File upload | None | Document attachments | Medium |
| Real-time | Polling only | WebSockets optional | High |

### 3.4 What Can Be Deployed As-Is

With correct env vars (no code changes):
- Login/logout JWT auth with rate limiting
- MAO dashboard, farm list, farm detail (PostgreSQL data)
- Claim filing and verification (requires Earth Engine credentials for live NDVI)
- PCIC approve/reject/flag workflow
- PDF report generation
- Public QR verification page
- In-app notifications
- Chatbot (with DeepSeek key; templates without)
- Sentinel View panel (with Sentinel Hub keys; static previews without)

Caveats: seeded production DB has farms but no satellite_imagery rows until scans or manual import; demo claims not in seed.sql.

### 3.5 What Must Be Changed Before Going Live

**Blockers:**
1. Set strong `JWT_SECRET_KEY` and `VERIFY_SECRET` — remove default fallback in `verify.py`
2. Set `DATABASE_URL` to Supabase direct connection (not `demo`)
3. Set `CORS_ORIGINS` to exact production frontend URL
4. Set `VERIFY_BASE_URL` to production domain
5. Set `NEXT_PUBLIC_API_URL` to production API URL
6. Remove or gate demo credentials on login page
7. Resolve `frontend/.git` nested repo for Amplify
8. Add `flag_reason` column to claims table if using PCIC flag

---

## 4. Domain Setup

### 4.1 DNS Configuration

Assume domain `bantayani.cloud` (replace with your domain):

| Record | Type | Name | Value | TTL |
|--------|------|------|-------|-----|
| Frontend | CNAME or ALIAS | `@` or `app` | Amplify CloudFront distribution | 300 |
| API | CNAME | `api` | Elastic Beanstalk environment URL | 300 |
| Verification | Same as frontend | `@` or `app` | `/verify/*` routes on Next.js — no separate record | — |

QR codes use `VERIFY_BASE_URL` (frontend domain) + `/verify/BA-{claim_number}`.

Propagation: 5 minutes to 48 hours. Verify: `dig api.bantayani.cloud`, `curl -I https://bantayani.cloud`.

### 4.2 SSL/TLS

- **Amplify:** Automatic ACM certificate when custom domain connected.
- **Elastic Beanstalk:** ACM certificate on load balancer — create cert in `ap-southeast-1`, attach to HTTPS listener on port 443.
- **Simplest path:** Amplify handles frontend SSL automatically; EB + ACM for API. Avoid manual Certbot unless using raw EC2.

---

## 5. Supabase Setup (Database)

### 5.1 Create the Supabase Project
1. Go to [supabase.com](https://supabase.com) → New Project
2. Region: **Southeast Asia (Singapore)** — `ap-southeast-1`
3. Database password: min 12 chars, mixed case, numbers, symbols — save in password manager
4. Project URL: `https://[PROJECT-REF].supabase.co` (for dashboard only — backend uses DATABASE_URL)
5. Anon key: not needed for this architecture (backend uses direct postgres connection)

### 5.2 Get the Connection String
- **Direct** (use this): `postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`
- **Pooler** (port 6543): for serverless — **do not use** with current psycopg2 per-request connections
- Replace `[PASSWORD]` with your database password; URL-encode special characters

### 5.3 Run the Schema
1. Supabase → SQL Editor → New query
2. Paste entire `database/schema.sql` → Run
3. Verify in Table Editor: users, municipalities, farm_parcels, satellite_imagery, claims, notifications

### 5.4 Run the Seed Data
1. Paste `database/seed.sql` → Run
2. Verify: 1 municipality, 3 users, 4 farm parcels
3. Optionally import satellite_imagery from demo data or run NDVI scans in production

### 5.5 Supabase Row Level Security
- Tables created via SQL Editor do **not** auto-enable RLS
- Backend connects as `postgres` superuser — RLS not required; authorization is in FastAPI JWT layer
- Verify: Table Editor → each table → RLS should show **disabled** (acceptable for this architecture)

### 5.6 Supabase Environment Variable
```bash
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
```

### 5.7 Connection Pooling Considerations
- Current: new psycopg2 connection per `execute_query()` — no pool
- Supabase free tier: ~60 direct connections
- Risk: connection exhaustion under concurrent load
- Fix: add `psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=10)` in `database.py` — **Medium effort**

---

## 6. AWS Services Setup

### 6.1 AWS Account and IAM Setup
1. Create AWS account
2. IAM → Users → Create `bantayani-deploy`
3. Attach: `AmazonEC2FullAccess`, `AmazonS3FullAccess`, `CloudFrontFullAccess`, `AWSCertificateManagerFullAccess`, `AdministratorAccess-AWSElasticBeanstalk`
4. Create access key → `aws configure` → region `ap-southeast-1`

### 6.2 Decision: Which AWS Services to Use

**Option A: Elastic Beanstalk (Recommended)** — Docker deploy, managed LB, health checks, ~$8-15/mo t3.micro

**Option B: EC2 Manual** — cheaper sustained, more ops work (Nginx, Certbot, Docker)

**Recommendation:** Amplify + Elastic Beanstalk for minimal ops experience.

### 6.3 Frontend: AWS Amplify Hosting
1. Remove nested git: `rm -rf frontend/.git` — single root repository
2. Amplify → Host web app → Connect GitHub
3. Root directory: `frontend`
4. Build: `npm run build` / Output: `.next` (Amplify Next.js 14 SSR preset)
5. Env: `NEXT_PUBLIC_API_URL=https://api.bantayani.cloud/api`
6. Custom domain: `bantayani.cloud` → automatic SSL

### 6.4 Backend: AWS Elastic Beanstalk
1. Zip backend (exclude venv, __pycache__, .env):
```bash
cd backend && zip -r ../backend-deploy.zip . -x 'venv/*' -x '__pycache__/*' -x '.env'
```
2. EB → Create application → Docker platform → Upload zip
3. Environment properties — set all vars from Section 8
4. Health check: `/api/health`, port 8000
5. Custom domain: Route 53 or CNAME `api.bantayani.cloud` → EB environment URL

### 6.5 Google Earth Engine Service Account
1. Google Cloud Console → IAM → Service account → Create key JSON
2. Register for Earth Engine access at earthengine.google.com
3. Upload JSON to EB instance at `/app/credentials/earth-engine-key.json` (not in git)
4. Set `GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/earth-engine-key.json`

### 6.6 AWS S3 for Static Assets (Optional)
- Bucket `bantayani-assets` in ap-southeast-1
- Public read on `satellite-previews/*` prefix
- Code change needed in `sentinel_hub_service.py` to return S3 URLs instead of `/satellite-previews/` paths

### 6.7 CloudFront (Optional)
- CDN in front of EB for API caching — cache only static paths, never `/api/*` mutations
- Amplify already includes CloudFront for frontend

---

## 7. Step-by-Step Deployment Sequence

1. Resolve git structure: root repo only, delete `frontend/.git`
2. Remove VERIFY_SECRET hardcoded fallback in `backend/api/verify.py` — require env var
3. Set CORS_ORIGINS to production frontend URL only
4. Document VERIFY_BASE_URL in deployment env (production domain)
5. Gate demo credentials on login page behind `NEXT_PUBLIC_SHOW_DEMO_CREDENTIALS=false`
6. Set NEXT_PUBLIC_API_URL in Amplify to production API
7. Create Supabase project → connection string → run schema.sql → run seed.sql
8. Verify tables and seed data in Supabase Table Editor
9. Create AWS IAM user and configure CLI (ap-southeast-1)
10. Deploy frontend to Amplify → connect git → env vars → custom domain
11. Deploy backend to Elastic Beanstalk → env vars → verify GET /api/health returns 200
12. Configure DNS: api CNAME → EB, apex CNAME → Amplify
13. Wait for DNS propagation and SSL provisioning
14. Test login as mao.naga@da.gov.ph on production URL
15. Confirm VERIFY_BASE_URL in EB env for PDF QR codes
16. Generate PDF report → scan QR → verify /verify/BA-* page loads
17. Test PCIC login and approve/reject on production
18. Test chatbot claim filing flow on production

---

## 8. Environment Variable Production Values

| Variable | Service | Production Value | How to Generate | Secret? |
|----------|---------|------------------|-----------------|---------|
| DATABASE_URL | Backend | postgresql://postgres:...@db.REF.supabase.co:5432/postgres | Supabase Dashboard → Database | Yes |
| JWT_SECRET_KEY | Backend | 64-char hex string | `openssl rand -hex 32` | Yes |
| JWT_ALGORITHM | Backend | HS256 | Fixed | No |
| JWT_EXPIRATION_HOURS | Backend | 24 | Fixed | No |
| CORS_ORIGINS | Backend | https://bantayani.cloud | Your frontend URL | No |
| DEEPSEEK_API_KEY | Backend | sk-... | platform.deepseek.com | Yes |
| SENTINEL_HUB_CLIENT_ID | Backend | UUID from SH dashboard | sentinel-hub.com | Yes |
| SENTINEL_HUB_CLIENT_SECRET | Backend | secret from SH | sentinel-hub.com | Yes |
| GOOGLE_APPLICATION_CREDENTIALS | Backend | /app/credentials/earth-engine-key.json | GCP service account | Yes |
| VERIFY_BASE_URL | Backend | https://bantayani.cloud | Your frontend URL | No |
| VERIFY_SECRET | Backend | 64-char hex | `openssl rand -hex 32` | Yes |
| NEXT_PUBLIC_API_URL | Frontend | https://api.bantayani.cloud/api | Your API URL | No |
| NEXT_PUBLIC_GOOGLE_MAPS_KEY | Frontend | AIza... (optional) | Google Cloud Console | No |

---

## 9. What the Team Needs to Do Right Now vs Later

### 9.1 Minimum to Go Live (Can Be Done Today)
- Supabase project + schema + seed
- Strong JWT_SECRET_KEY and VERIFY_SECRET
- Amplify frontend deploy with NEXT_PUBLIC_API_URL
- Elastic Beanstalk backend with DATABASE_URL and CORS_ORIGINS
- DNS for frontend and api subdomains
- Remove demo credentials from production login
- Fix nested frontend/.git

### 9.2 Should Be Done Within One Week of Launch
- Connection pooling for Supabase
- CloudWatch logging + basic alarms
- Sentry error tracking
- Migrate VERIFY_SECRET fallback removal
- Import or scan satellite_imagery for production farms
- Add flag_reason column migration

### 9.3 Can Be Done Over Time
- httpOnly cookie auth + refresh tokens
- CI/CD pipeline
- Automated tests
- Redis job queue
- Email notifications
- S3 for satellite previews
- TypeScript migration

---

## 10. Troubleshooting Reference

**Backend 500 on all requests**
- Cause: DATABASE_URL wrong or Supabase unreachable
- Fix: Test connection from EB SSH; verify password URL-encoding

**CORS errors in browser**
- Cause: CORS_ORIGINS mismatch
- Fix: Must include exact protocol + domain, no trailing slash on API

**JWT errors on protected routes**
- Cause: JWT_SECRET_KEY mismatch
- Fix: Re-login after key change; verify EB env

**Satellite imagery black**
- Cause: EE/SH credentials missing
- Fix: System falls back to static previews in frontend/public

**PDF QR wrong domain**
- Cause: VERIFY_BASE_URL unset
- Fix: Set to https://your-frontend-domain

**Login OK but empty data**
- Cause: Seed not run
- Fix: Run seed.sql; check farm_parcels table

**Claims page empty for MAO**
- Cause: Municipality scoping
- Fix: MAO user municipality_id must match farm municipality_id

**NDVI scan never completes**
- Cause: EE not configured in production
- Fix: Confirm DATABASE_URL is postgres URL not demo

---

## 11. Cost Estimate

| Service | Plan | Monthly Cost (USD) | Notes |
|---------|------|-------------------|-------|
| Supabase | Free tier | $0 | 500MB DB, 2GB bandwidth |
| AWS Amplify | Pay-per-use | ~$1-5 | Build minutes + transfer |
| AWS Elastic Beanstalk (t3.micro) | On-demand | ~$8-15 | Single instance |
| AWS Certificate Manager | Free | $0 | SSL certificates |
| Google Earth Engine | Non-commercial | $0 | Requires approved project |
| DeepSeek API | Pay-per-token | ~$1-5 | Chat volume dependent |
| Domain registration | Annual | ~$12/year | Already owned |
| **Total** | | **~$10-25/month** | At minimal scale |

Costs increase with: traffic, Amplify build frequency, multiple EB instances, Supabase Pro ($25/mo) when exceeding 500MB or 60 connections.

---

## 12. Security Checklist Before Going Live

- [ ] VERIFY_SECRET is randomly generated with no hardcoded fallback
  - Why: Prevents forged report integrity hashes. If no: Set env var; patch verify.py
- [ ] JWT_SECRET_KEY is 64+ character random string
  - Why: Prevents token forgery. If no: openssl rand -hex 32
- [ ] CORS_ORIGINS lists only exact production frontend domain
  - Why: Prevents cross-site API abuse. If no: No wildcards
- [ ] Earth Engine JSON not in git repository
  - Why: Prevents credential leak. If no: Use .gitignore; rotate if committed
- [ ] Docker Compose default JWT secret removed
  - Why: Repo hygiene. If no: Remove change-me-in-production default
- [ ] Demo credentials not on production login page
  - Why: Prevents unauthorized access. If no: Gate with env var
- [ ] All secrets in Amplify/Beanstalk env, not committed
  - Why: Prevents leak. If no: Never commit .env
- [ ] backend/.env in .gitignore
  - Why: Local secret protection. If no: Verify git history
- [ ] frontend/.env.local in .gitignore
  - Why: Local secret protection. If no: Verify git history
- [ ] HTTPS enforced on all endpoints
  - Why: Prevents MITM. If no: Amplify + EB HTTPS listeners
- [ ] /api/health does not expose sensitive info
  - Why: Reduces reconnaissance. If no: Only returns status and mode

---

*End of Bantay Ani Production Deployment Guide.*