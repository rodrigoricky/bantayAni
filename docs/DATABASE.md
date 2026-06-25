# Database Schema

PostgreSQL 15+ (Supabase)

## Tables

| Table | Purpose |
|-------|---------|
| `users` | MAO, DA Regional, PCIC accounts |
| `municipalities` | Philippine municipality master list |
| `farm_parcels` | Registered farms with JSONB polygons |
| `satellite_imagery` | NDVI time-series per parcel |
| `claims` | Insurance claim verification records |

## Key Relationships

- `farm_parcels.municipality_id` → `municipalities.id`
- `satellite_imagery.parcel_id` → `farm_parcels.id`
- `claims.parcel_id` → `farm_parcels.id`

## NDVI Classification

| NDVI Range | Status |
|------------|--------|
| ≥ 0.6 | HEALTHY |
| 0.4 – 0.6 | WATCH |
| < 0.4 | CRITICAL |

See `database/schema.sql` and `database/seed.sql` for full definitions.