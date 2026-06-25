# Bantay Ani API Documentation

Base URL: `http://localhost:8000/api`

All responses follow: `{ success, data, error }`

## Authentication

### POST /login
```json
{ "email": "mao.naga@da.gov.ph", "password": "demo123" }
```

## Farms

### GET /farms/municipality/{municipality_id}
Requires JWT. Returns farms with latest NDVI and health stats.

### GET /farms/{parcel_id}
Requires JWT. Returns farm detail, NDVI history, recent claims.

## Claims

### POST /claims/verify
```json
{
  "rsbsa_number": "RSBSA-05-NAGA-2024-00123",
  "disaster_date": "2024-10-23",
  "damage_type": "flood",
  "claimed_area_hectares": 2.5
}
```

### GET /claims
Query params: `municipality_id`, `status`, `limit`, `offset`

## Reports

### POST /reports/generate
```json
{ "claim_id": "uuid" }
```
Returns PDF file download.