-- Bantay Ani Demo Seed Data — Naga City, Camarines Sur (Typhoon Kristine)
-- Password for all demo users: demo123

INSERT INTO municipalities (id, name, province, region, latitude, longitude, total_farms, total_area_hectares)
VALUES (
    'camarines-naga',
    'Naga City',
    'Camarines Sur',
    'Region V (Bicol)',
    13.6192,
    123.1814,
    4,
    6.5
);

INSERT INTO users (email, password_hash, role, municipality_id, first_name, last_name)
VALUES
(
    'mao.naga@da.gov.ph',
    '$2b$12$QuXUxDownoKX6I77sBTapefK2Ivq8MKBYIlchFQ2QoGCoQwHJqsSC',
    'MAO',
    'camarines-naga',
    'John',
    'Doe'
),
(
    'regional.x@da.gov.ph',
    '$2b$12$QuXUxDownoKX6I77sBTapefK2Ivq8MKBYIlchFQ2QoGCoQwHJqsSC',
    'DA_REGIONAL',
    'camarines-naga',
    'Jane',
    'Doe'
),
(
    'pcic.x@pcic.gov.ph',
    '$2b$12$QuXUxDownoKX6I77sBTapefK2Ivq8MKBYIlchFQ2QoGCoQwHJqsSC',
    'PCIC',
    'camarines-naga',
    'Juan',
    'Dela Cruz'
);

INSERT INTO farm_parcels (id, rsbsa_number, farmer_name, municipality_id, crop_type, area_hectares, latitude, longitude, polygon, planting_date, expected_harvest_date)
VALUES
(
    'BUK-001',
    'RSBSA-BUK-2024-00412',
    'Juan Dela Cruz',
    'camarines-naga',
    'Rice',
    1.5,
    13.6150,
    123.1750,
    '[[123.1720, 13.6120], [123.1780, 13.6120], [123.1780, 13.6180], [123.1720, 13.6180], [123.1720, 13.6120]]'::jsonb,
    '2024-06-15',
    '2024-11-28'
),
(
    'BUK-002',
    'RSBSA-BUK-2024-00413',
    'Maria Santos',
    'camarines-naga',
    'Rice',
    2.0,
    13.6220,
    123.1890,
    '[[123.1860, 13.6190], [123.1920, 13.6190], [123.1920, 13.6250], [123.1860, 13.6250], [123.1860, 13.6190]]'::jsonb,
    '2024-06-20',
    '2024-12-01'
),
(
    'BUK-003',
    'RSBSA-BUK-2024-00999',
    'Pedro Reyes',
    'camarines-naga',
    'Rice',
    1.2,
    13.6080,
    123.1820,
    '[[123.1790, 13.6050], [123.1850, 13.6050], [123.1850, 13.6110], [123.1790, 13.6110], [123.1790, 13.6050]]'::jsonb,
    '2024-06-10',
    '2024-11-20'
),
(
    'BUK-004',
    'RSBSA-BUK-2024-00415',
    'Ana Mendoza',
    'camarines-naga',
    'Corn',
    1.8,
    13.6300,
    123.1760,
    '[[123.1730, 13.6270], [123.1790, 13.6270], [123.1790, 13.6330], [123.1730, 13.6330], [123.1730, 13.6270]]'::jsonb,
    '2024-07-01',
    '2024-12-15'
);