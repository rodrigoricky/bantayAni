-- Bantay Ani Database Schema
-- Run in Supabase SQL Editor

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('MAO', 'DA_REGIONAL', 'PCIC')),
    municipality_id VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_municipality ON users(municipality_id);

CREATE TABLE municipalities (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    province VARCHAR(255) NOT NULL,
    region VARCHAR(255) NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    total_farms INTEGER DEFAULT 0,
    total_area_hectares DECIMAL(12, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_municipalities_region ON municipalities(region);
CREATE INDEX idx_municipalities_province ON municipalities(province);

CREATE TABLE farm_parcels (
    id VARCHAR(50) PRIMARY KEY,
    rsbsa_number VARCHAR(100) UNIQUE NOT NULL,
    farmer_name VARCHAR(255) NOT NULL,
    municipality_id VARCHAR(50) NOT NULL REFERENCES municipalities(id) ON DELETE CASCADE,
    crop_type VARCHAR(100) NOT NULL,
    area_hectares DECIMAL(10, 2) NOT NULL CHECK (area_hectares > 0),
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    polygon JSONB NOT NULL,
    planting_date DATE,
    expected_harvest_date DATE,
    is_insured BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'HARVESTED', 'ABANDONED')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_farms_municipality ON farm_parcels(municipality_id);
CREATE INDEX idx_farms_rsbsa ON farm_parcels(rsbsa_number);
CREATE INDEX idx_farms_crop_type ON farm_parcels(crop_type);
CREATE INDEX idx_farms_location ON farm_parcels(latitude, longitude);

CREATE TABLE satellite_imagery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id VARCHAR(50) NOT NULL REFERENCES farm_parcels(id) ON DELETE CASCADE,
    capture_date DATE NOT NULL,
    ndvi_value DECIMAL(5, 3) NOT NULL CHECK (ndvi_value BETWEEN -1 AND 1),
    image_url TEXT,
    cloud_cover_percentage DECIMAL(5, 2) DEFAULT 5.0,
    data_source VARCHAR(50) DEFAULT 'Sentinel-2',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_satellite_parcel ON satellite_imagery(parcel_id);
CREATE INDEX idx_satellite_date ON satellite_imagery(capture_date DESC);
CREATE UNIQUE INDEX idx_satellite_parcel_date ON satellite_imagery(parcel_id, capture_date);

CREATE TABLE claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_number VARCHAR(100) UNIQUE NOT NULL,
    parcel_id VARCHAR(50) NOT NULL REFERENCES farm_parcels(id),
    farmer_name VARCHAR(255) NOT NULL,
    rsbsa_number VARCHAR(100) NOT NULL,
    damage_type VARCHAR(50) NOT NULL CHECK (damage_type IN ('flood', 'drought', 'typhoon', 'pest', 'disease', 'other')),
    claimed_area_hectares DECIMAL(10, 2) NOT NULL,
    disaster_date DATE NOT NULL,
    filed_date DATE NOT NULL DEFAULT CURRENT_DATE,
    ndvi_before DECIMAL(5, 3),
    ndvi_after DECIMAL(5, 3),
    damage_percentage DECIMAL(5, 2),
    before_image_url TEXT,
    after_image_url TEXT,
    ai_recommendation TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'FLAGGED', 'REJECTED', 'SUBMITTED')),
    verified_by_user_id UUID REFERENCES users(id),
    verified_at TIMESTAMP,
    submitted_at TIMESTAMP,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_claims_parcel ON claims(parcel_id);
CREATE INDEX idx_claims_rsbsa ON claims(rsbsa_number);
CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_claims_disaster_date ON claims(disaster_date DESC);
CREATE INDEX idx_claims_filed_date ON claims(filed_date DESC);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    claim_id UUID REFERENCES claims(id) ON DELETE SET NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_unread ON notifications(user_id, is_read) WHERE is_read = FALSE;
CREATE INDEX idx_notifications_created ON notifications(created_at DESC);