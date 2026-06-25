# Bantay Ani Demo Script

**Duration:** ~5 minutes  
**Audience:** DA Regional Officers, PCIC, Municipal Agricultural Officers

## Setup
1. Start backend: `uvicorn main:app --reload --port 8000`
2. Start frontend: `npm run dev`
3. Open http://localhost:3000

## Act 1: Login (30 seconds)
- Show login page
- Enter: `mao.naga@da.gov.ph` / `demo123`
- Highlight: "Replaces 20-day field verification with 90-second satellite analysis"

## Act 2: Dashboard (1 minute)
- Point out stats: 0 Healthy, 1 Watch, 2 Critical
- Click farm polygons on map — show NDVI values
- Explain color coding: green/yellow/red = crop health post-Typhoon Kristine

## Act 3: Claims Verification (2 minutes)
- Navigate to "Verify Claims"
- Pre-filled demo RSBSA: `RSBSA-05-NAGA-2024-00123`
- Disaster date: `2024-10-23` (Typhoon Kristine)
- Click "Run Satellite Verification"
- Show results:
  - NDVI: 0.682 → 0.094 (86% damage)
  - Status: APPROVED
  - AI recommendation
  - Before/after satellite images

## Act 4: Report (1 minute)
- Click "Download PDF Report"
- Show PCIC-compliant verification document
- Mention: payout accelerated from 3 weeks to 2 days

## Talking Points
- Cost reduction: 88–95% vs physical adjusters
- Data source: Sentinel-2 (10m resolution, 5-day revisit)
- Case study: Real Naga City rice farms, October 2024 flood event